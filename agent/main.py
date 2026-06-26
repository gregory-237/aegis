"""Точка входа агента."""
from __future__ import annotations

import logging
import pathlib
import signal
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from agent.collector import collect  # noqa: E402
from agent.config import config  # noqa: E402
from agent.policy import DriftMonitor, Policy, PolicyManager  # noqa: E402
from agent.transport import IngestClient, MetricsBuffer  # noqa: E402

from agent._pb import pb  # noqa: E402
import grpc  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
)
log = logging.getLogger("agent")

_running = True


def _stop(*_args) -> None:
    global _running
    _running = False
    log.info("получен сигнал остановки")


def apply_policy_at_start(client: IngestClient) -> "PolicyManager | None":
    try:
        resp = client.get_config()
    except grpc.RpcError as e:
        log.warning("GetConfig не прошёл (%s) — политика не применена", e.code())
        return None

    policy = Policy.from_pb(resp.policy, version=resp.version)
    manager = PolicyManager(server_host=config.server_host)
    result = manager.apply(policy, dry_run=not config.policy_apply)
    client.config_version = resp.version

    severity = pb.Severity.INFO if result.ok else pb.Severity.WARNING
    mode = "applied" if config.policy_apply else "dry-run"
    try:
        client.report_event(
            "policy_applied",
            f"политика {policy.version} ({mode}), backend={result.backend}, "
            f"команд={len(result.commands)}, default_drop={result.default_drop_output}",
            severity,
            {
                "backend": result.backend,
                "mode": mode,
                "commands": str(len(result.commands)),
                "default_drop": str(result.default_drop_output),
            },
        )
    except grpc.RpcError as e:
        log.warning("не удалось отправить событие policy_applied: %s", e.code())
    return manager


def check_drift(client: IngestClient, monitor: DriftMonitor) -> None:
    report = monitor.check()
    if not report.drifted:
        return

    log.warning("ДРЕЙФ: %s", report.summary())
    rolled_back = False
    if config.drift_autorollback:
        failures = monitor.rollback()
        rolled_back = not failures

    try:
        client.report_event(
            "drift",
            f"обнаружен дрейф firewall ({report.summary()}), "
            f"откат={'выполнен' if rolled_back else 'нет'}",
            pb.Severity.WARNING,
            {
                "missing": str(len(report.missing)),
                "unexpected": str(len(report.unexpected)),
                "rolled_back": str(rolled_back),
            },
        )
    except grpc.RpcError as e:
        log.warning("не удалось отправить событие drift: %s", e.code())


def run() -> None:
    log.info(
        "запуск агента id=%s os=%s arch=%s -> %s",
        config.agent_id,
        config.os_name,
        config.arch,
        config.target,
    )
    buffer = MetricsBuffer(config.buffer_path, config.buffer_max)
    client = IngestClient(config)

    if client.wait_ready(timeout=config.rpc_timeout_sec):
        log.info("соединение с ingest установлено (mTLS)")
        try:
            client.heartbeat()
        except grpc.RpcError as e:
            log.warning("heartbeat не прошёл: %s", e.code())

    manager = apply_policy_at_start(client)

    monitor: DriftMonitor | None = None
    if manager is not None and config.policy_apply:
        monitor = DriftMonitor(manager.backend)
        rules, default_drop = manager.last_reference
        monitor.set_reference(rules, default_drop)
        log.info("контроль дрейфа включён (интервал %d c)", config.drift_interval_sec)

    last_heartbeat = 0.0
    last_drift_check = 0.0
    while _running:
        cycle_start = time.monotonic()

        samples = collect()
        buffer.add(samples)

        pending = buffer.drain()
        try:
            accepted = client.report_metrics(pending)
            log.info("отправлено метрик: %d", accepted)
        except grpc.RpcError as e:
            log.warning("отправка метрик не удалась (%s) — возвращаю в буфер", e.code())
            buffer.add(pending)

        now = time.monotonic()
        if now - last_heartbeat >= config.heartbeat_interval_sec:
            try:
                resp = client.heartbeat()
                if resp and resp.config_outdated:
                    log.info("сервер сообщает: конфиг устарел — нужно GetConfig")
                last_heartbeat = now
            except grpc.RpcError as e:
                log.warning("heartbeat не прошёл: %s", e.code())

        if monitor is not None and now - last_drift_check >= config.drift_interval_sec:
            try:
                check_drift(client, monitor)
            except Exception as e:  # noqa: BLE001
                log.error("ошибка контроля дрейфа: %s", e)
            last_drift_check = now

        elapsed = time.monotonic() - cycle_start
        time.sleep(max(1.0, config.metrics_interval_sec - elapsed))

    client.close()
    log.info("агент остановлен")


if __name__ == "__main__":
    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)
    run()
