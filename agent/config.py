"""Конфигурация агента: env-переменные + необязательный aegis.env рядом с бинарём."""
from __future__ import annotations

import os
import pathlib
import platform
import socket
import sys
from dataclasses import dataclass, field


def _app_root() -> pathlib.Path:
    # PyInstaller-onefile распаковывается во временную _MEIxxx и туда указывает __file__.
    # Сертификаты и aegis.env лежат рядом с exe, а не внутри архива.
    if getattr(sys, "frozen", False):
        return pathlib.Path(sys.executable).resolve().parent
    return pathlib.Path(__file__).resolve().parents[1]


def _load_env_file(path: pathlib.Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


ROOT = _app_root()
_load_env_file(ROOT / "aegis.env")
CERTS = ROOT / "certs"


def _env_path(name: str, default: pathlib.Path) -> pathlib.Path:
    raw = os.environ.get(name, str(default))
    p = pathlib.Path(raw)
    return p if p.is_absolute() else (ROOT / p)


@dataclass(frozen=True)
class Config:
    server_host: str = os.environ.get("AEGIS_SERVER_HOST", "localhost")
    server_port: int = int(os.environ.get("AEGIS_SERVER_PORT", "1222"))

    agent_id: str = os.environ.get("AEGIS_AGENT_ID", socket.gethostname())
    agent_version: str = "0.1.0"

    ca_cert: pathlib.Path = _env_path("AEGIS_CA_CERT", CERTS / "ca.crt")
    client_cert: pathlib.Path = _env_path("AEGIS_AGENT_CERT", CERTS / "agent.crt")
    client_key: pathlib.Path = _env_path("AEGIS_AGENT_KEY", CERTS / "agent.key")

    metrics_interval_sec: int = int(os.environ.get("AEGIS_METRICS_INTERVAL", "30"))
    heartbeat_interval_sec: int = int(os.environ.get("AEGIS_HEARTBEAT_INTERVAL", "30"))
    rpc_timeout_sec: int = int(os.environ.get("AEGIS_RPC_TIMEOUT", "10"))

    # По умолчанию dry-run: реально править firewall — только AEGIS_POLICY_APPLY=1,
    # чтобы отладка не оставляла машину без сети.
    policy_apply: bool = os.environ.get("AEGIS_POLICY_APPLY", "0").lower() in ("1", "true", "yes")

    # demo-safe: не менять глобальную default-policy firewall (только свои ACCEPT-правила),
    # чтобы при выходе агента хост гарантированно вернулся к исходному состоянию.
    policy_demo_safe: bool = os.environ.get("AEGIS_POLICY_DEMO_SAFE", "1").lower() in (
        "1", "true", "yes",
    )

    # На выходе агента снимать применённые правила Aegis (SIGINT/SIGTERM/закрытие окна).
    cleanup_on_exit: bool = os.environ.get("AEGIS_CLEANUP_ON_EXIT", "1").lower() in (
        "1", "true", "yes",
    )

    drift_interval_sec: int = int(os.environ.get("AEGIS_DRIFT_INTERVAL", "60"))
    drift_autorollback: bool = os.environ.get("AEGIS_DRIFT_ROLLBACK", "1").lower() in (
        "1", "true", "yes",
    )

    buffer_path: pathlib.Path = _env_path(
        "AEGIS_BUFFER", ROOT / "agent" / "buffer" / "metrics.jsonl"
    )
    buffer_max: int = int(os.environ.get("AEGIS_BUFFER_MAX", "10000"))

    os_name: str = field(default_factory=lambda: platform.system().lower())
    arch: str = field(default_factory=lambda: platform.machine().lower())

    @property
    def target(self) -> str:
        return f"{self.server_host}:{self.server_port}"

    def read_pem(self) -> tuple[bytes, bytes, bytes]:
        missing = [p for p in (self.ca_cert, self.client_cert, self.client_key) if not p.exists()]
        if missing:
            raise FileNotFoundError(
                "Нет сертификатов агента: "
                + ", ".join(str(p) for p in missing)
                + ". Сначала запусти: bash scripts/gen-certs.sh"
            )
        return (
            self.ca_cert.read_bytes(),
            self.client_cert.read_bytes(),
            self.client_key.read_bytes(),
        )


config = Config()
