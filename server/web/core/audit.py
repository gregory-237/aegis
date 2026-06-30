"""Запись действий администратора в таблицу audit_log."""
from __future__ import annotations

import logging

from core.models import AuditLog

log = logging.getLogger("aegis.audit")


def log_action(actor: str, action: str, target: str = "", payload: dict | None = None) -> None:
    try:
        AuditLog.objects.create(
            actor=actor or "system", action=action, target=target, payload=payload or {}
        )
    except Exception as e:  # noqa: BLE001 - аудит не должен ломать основное действие
        log.error("не удалось записать аудит (%s): %s", action, e)
