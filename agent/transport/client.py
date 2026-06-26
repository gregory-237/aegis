"""gRPC-клиент к ingest с mTLS."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import grpc

from agent._pb import pb, pb_grpc
from agent.collector import Sample
from agent.config import Config

log = logging.getLogger("agent.transport")


def _to_pb_timestamp(dt: datetime):
    from google.protobuf.timestamp_pb2 import Timestamp

    ts = Timestamp()
    ts.FromDatetime(dt.astimezone(timezone.utc))
    return ts


def _to_pb_sample(s: Sample) -> "pb.Sample":
    return pb.Sample(name=s.name, value=s.value, ts=_to_pb_timestamp(s.ts), labels=s.labels)


class IngestClient:
    def __init__(self, cfg: Config) -> None:
        self._cfg = cfg
        self.config_version = "v0"
        ca_pem, cert_pem, key_pem = cfg.read_pem()
        creds = grpc.ssl_channel_credentials(
            root_certificates=ca_pem,
            private_key=key_pem,
            certificate_chain=cert_pem,
        )
        self._channel = grpc.secure_channel(cfg.target, creds)
        self._stub = pb_grpc.MonitorStub(self._channel)

    def wait_ready(self, timeout: float = 10.0) -> bool:
        try:
            grpc.channel_ready_future(self._channel).result(timeout=timeout)
            return True
        except grpc.FutureTimeoutError:
            return False

    def heartbeat(self) -> "pb.HeartbeatResponse | None":
        req = pb.HeartbeatRequest(
            agent_id=self._cfg.agent_id,
            sent_at=_to_pb_timestamp(datetime.now(timezone.utc)),
            agent_version=self._cfg.agent_version,
            config_version=self.config_version,
        )
        return self._stub.Heartbeat(req, timeout=self._cfg.rpc_timeout_sec)

    def report_metrics(self, samples: list[Sample]) -> int:
        if not samples:
            return 0

        def _gen():
            yield pb.MetricsBatch(
                agent_id=self._cfg.agent_id,
                samples=[_to_pb_sample(s) for s in samples],
            )

        ack = self._stub.ReportMetrics(_gen(), timeout=self._cfg.rpc_timeout_sec)
        return ack.accepted

    def report_event(self, type_: str, message: str, severity: int, payload: dict | None = None):
        ev = pb.Event(
            agent_id=self._cfg.agent_id,
            type=type_,
            severity=severity,
            message=message,
            payload=payload or {},
            occurred_at=_to_pb_timestamp(datetime.now(timezone.utc)),
        )
        return self._stub.ReportEvent(ev, timeout=self._cfg.rpc_timeout_sec)

    def get_config(self, current_version: str = "") -> "pb.ConfigResponse":
        req = pb.ConfigRequest(agent_id=self._cfg.agent_id, current_version=current_version)
        return self._stub.GetConfig(req, timeout=self._cfg.rpc_timeout_sec)

    def close(self) -> None:
        self._channel.close()
