"""Aegis ingest — gRPC-сервис приёма метрик, событий и heartbeat от агентов."""
from __future__ import annotations

import logging
import pathlib
import sys
from concurrent import futures
from datetime import datetime, timezone

import grpc

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "proto" / "gen"))
import monitor_pb2 as pb  # noqa: E402
import monitor_pb2_grpc as pb_grpc  # noqa: E402

from alerts import TelegramNotifier  # noqa: E402
from config import config  # noqa: E402
from storage import MetricsStore, StateStore  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
)
log = logging.getLogger("ingest")


def _now():
    from google.protobuf.timestamp_pb2 import Timestamp

    ts = Timestamp()
    ts.FromDatetime(datetime.now(timezone.utc))
    return ts


def _policy_dict_to_pb(policy: dict) -> "pb.Policy":
    fw = []
    for r in policy.get("firewall", []) or []:
        fw.append(
            pb.FirewallRule(
                chain=r.get("chain", ""),
                action=r.get("action", ""),
                protocol=r.get("protocol", ""),
                direction=r.get("direction", ""),
                remote=r.get("remote", ""),
                port=int(r.get("port", 0) or 0),
                comment=r.get("comment", ""),
            )
        )
    return pb.Policy(
        firewall=fw,
        allowed_domains=list(policy.get("allowed_domains", []) or []),
        monitored_services=list(policy.get("monitored_services", []) or []),
        metrics_interval_sec=int(policy.get("metrics_interval_sec", 30) or 30),
    )


def _peer_identity(context: grpc.ServicerContext) -> str:
    try:
        ac = context.auth_context()
        for key in (b"x509_common_name", "x509_common_name"):
            if key in ac and ac[key]:
                val = ac[key][0]
                return val.decode() if isinstance(val, bytes) else str(val)
    except Exception:  # noqa: BLE001
        pass
    return "<unknown>"


class MonitorServicer(pb_grpc.MonitorServicer):
    def __init__(
        self, metrics: MetricsStore, state: StateStore, notifier: TelegramNotifier
    ) -> None:
        self._metrics = metrics
        self._state = state
        self._notifier = notifier

    def Enroll(self, request: "pb.EnrollRequest", context):
        log.warning(
            "Enroll запрошен (host=%s, os=%s) — выдача сертификатов ещё не реализована",
            request.hostname,
            request.os,
        )
        context.abort(grpc.StatusCode.UNIMPLEMENTED, "enrollment появится на следующем этапе")

    def Heartbeat(self, request: "pb.HeartbeatRequest", context):
        cn = _peer_identity(context)
        # peer() у grpc возвращает "ipv4:1.2.3.4:5678" или "ipv6:[::1]:1234"
        peer_ip = ""
        peer = context.peer() or ""
        if peer.startswith("ipv4:"):
            peer_ip = peer[5:].rsplit(":", 1)[0]
        elif peer.startswith("ipv6:"):
            peer_ip = peer[5:].rsplit(":", 1)[0].strip("[]")

        self._state.upsert_machine(
            request.agent_id,
            status="online",
            agent_version=request.agent_version,
            config_version=request.config_version,
            hostname=request.hostname,
            os=request.os,
            arch=request.arch,
            ip=peer_ip,
            last_seen=datetime.now(timezone.utc),
        )
        record = self._state.get_policy_for_agent(request.agent_id)
        config_outdated = bool(record and record["version"] != request.config_version)
        log.info(
            "heartbeat agent_id=%s cn=%s version=%s cfg=%s outdated=%s",
            request.agent_id,
            cn,
            request.agent_version,
            request.config_version,
            config_outdated,
        )
        return pb.HeartbeatResponse(
            server_time=_now(),
            config_outdated=config_outdated,
            next_interval_sec=30,
        )

    def ReportMetrics(self, request_iterator, context):
        cn = _peer_identity(context)
        accepted = 0
        stored = 0
        agent_id = "<unknown>"
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        for batch in request_iterator:
            agent_id = batch.agent_id or agent_id
            accepted += len(batch.samples)
            tuples = []
            for s in batch.samples:
                ts_ms = s.ts.ToMilliseconds() if s.HasField("ts") else now_ms
                tuples.append((s.name, s.value, dict(s.labels), ts_ms))
            try:
                stored += self._metrics.write(batch.agent_id, tuples)
            except Exception as e:  # noqa: BLE001
                log.error("ошибка записи в VictoriaMetrics: %s", e)
        self._state.upsert_machine(agent_id, status="online", last_seen=datetime.now(timezone.utc))
        log.info(
            "метрики agent_id=%s cn=%s: принято=%d сохранено=%d", agent_id, cn, accepted, stored
        )
        return pb.ReportAck(accepted=accepted, message="ok")

    def ReportEvent(self, request: "pb.Event", context):
        sev = pb.Severity.Name(request.severity)
        self._state.record_event(
            request.agent_id,
            type_=request.type,
            severity=sev,
            message=request.message,
            payload=dict(request.payload),
        )
        log.warning(
            "EVENT agent_id=%s type=%s severity=%s msg=%s payload=%s",
            request.agent_id,
            request.type,
            sev,
            request.message,
            dict(request.payload),
        )
        if self._notifier.should_alert(sev):
            self._notifier.notify(request.agent_id, request.type, sev, request.message)
        return pb.ReportAck(accepted=1, message="event accepted")

    def GetConfig(self, request: "pb.ConfigRequest", context):
        record = self._state.get_policy_for_agent(request.agent_id)
        if record:
            log.info(
                "GetConfig agent_id=%s -> профиль версии %s", request.agent_id, record["version"]
            )
            policy = _policy_dict_to_pb(record["policy"])
            return pb.ConfigResponse(version=record["version"], policy=policy, signature=b"")

        log.info("GetConfig agent_id=%s -> профиль не назначен", request.agent_id)
        return pb.ConfigResponse(
            version="none", policy=pb.Policy(metrics_interval_sec=30), signature=b""
        )


def serve() -> None:
    ca_pem, server_cert_pem, server_key_pem = config.read_pem()

    server_credentials = grpc.ssl_server_credentials(
        private_key_certificate_chain_pairs=[(server_key_pem, server_cert_pem)],
        root_certificates=ca_pem,
        require_client_auth=config.require_client_auth,
    )

    metrics = MetricsStore(config.vm_url)
    state = StateStore(config.pg_dsn)
    notifier = TelegramNotifier(
        config.telegram_token, config.telegram_chat_id, config.alert_min_severity
    )

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=config.max_workers))
    pb_grpc.add_MonitorServicer_to_server(
        MonitorServicer(metrics, state, notifier), server
    )

    addr = f"{config.host}:{config.port}"
    server.add_secure_port(addr, server_credentials)
    server.start()
    log.info("ingest слушает %s (mTLS, require_client_auth=%s)", addr, config.require_client_auth)
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        log.info("остановка ingest")
        server.stop(grace=2)


if __name__ == "__main__":
    serve()
