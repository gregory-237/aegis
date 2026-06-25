"""Конфигурация ingest-сервиса."""
from __future__ import annotations

import os
import pathlib
from dataclasses import dataclass

ROOT = pathlib.Path(__file__).resolve().parents[2]
CERTS = ROOT / "certs"


def _env_path(name: str, default: pathlib.Path) -> pathlib.Path:
    return pathlib.Path(os.environ.get(name, str(default)))


@dataclass(frozen=True)
class Config:
    host: str = os.environ.get("AEGIS_INGEST_HOST", "0.0.0.0")
    port: int = int(os.environ.get("AEGIS_INGEST_PORT", "1222"))

    ca_cert: pathlib.Path = _env_path("AEGIS_CA_CERT", CERTS / "ca.crt")
    server_cert: pathlib.Path = _env_path("AEGIS_SERVER_CERT", CERTS / "server.crt")
    server_key: pathlib.Path = _env_path("AEGIS_SERVER_KEY", CERTS / "server.key")

    require_client_auth: bool = True

    max_workers: int = int(os.environ.get("AEGIS_INGEST_WORKERS", "10"))

    # Пустой URL/DSN — хранилище выключено, метрики пишутся только в лог.
    vm_url: str = os.environ.get("AEGIS_VM_URL", "")
    pg_dsn: str = os.environ.get("AEGIS_PG_DSN", "")

    telegram_token: str = os.environ.get("AEGIS_TELEGRAM_TOKEN", "")
    telegram_chat_id: str = os.environ.get("AEGIS_TELEGRAM_CHAT_ID", "")
    alert_min_severity: str = os.environ.get("AEGIS_ALERT_MIN_SEVERITY", "WARNING")

    def read_pem(self) -> tuple[bytes, bytes, bytes]:
        missing = [p for p in (self.ca_cert, self.server_cert, self.server_key) if not p.exists()]
        if missing:
            raise FileNotFoundError(
                "Нет сертификатов: "
                + ", ".join(str(p) for p in missing)
                + ". Сначала запусти: bash scripts/gen-certs.sh"
            )
        return (
            self.ca_cert.read_bytes(),
            self.server_cert.read_bytes(),
            self.server_key.read_bytes(),
        )


config = Config()
