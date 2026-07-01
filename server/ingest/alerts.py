"""Telegram-уведомления при событиях с важностью >= порога."""
from __future__ import annotations

import logging

import requests

log = logging.getLogger("ingest.alerts")

_SEVERITY_ORDER = {"INFO": 1, "WARNING": 2, "CRITICAL": 3}
_EMOJI = {"INFO": "ℹ️", "WARNING": "⚠️", "CRITICAL": "🔴"}


def severity_at_least(severity: str, threshold: str) -> bool:
    return _SEVERITY_ORDER.get(severity, 0) >= _SEVERITY_ORDER.get(threshold, 99)


def format_message(agent_id: str, type_: str, severity: str, message: str) -> str:
    emoji = _EMOJI.get(severity, "")
    return (
        f"{emoji} <b>AEGIS · {severity}</b>\n"
        f"машина: <code>{agent_id}</code>\n"
        f"событие: <code>{type_}</code>\n"
        f"{message}"
    )


class TelegramNotifier:
    def __init__(self, token: str, chat_id: str, min_severity: str = "WARNING") -> None:
        self._token = token
        self._chat_id = chat_id
        self._min = min_severity
        self.enabled = bool(token and chat_id)
        if not self.enabled:
            log.info("Telegram-алерты выключены (нет AEGIS_TELEGRAM_TOKEN/CHAT_ID)")

    def should_alert(self, severity: str) -> bool:
        return self.enabled and severity_at_least(severity, self._min)

    def notify(self, agent_id: str, type_: str, severity: str, message: str) -> bool:
        if not self.should_alert(severity):
            return False
        url = f"https://api.telegram.org/bot{self._token}/sendMessage"
        payload = {
            "chat_id": self._chat_id,
            "text": format_message(agent_id, type_, severity, message),
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        try:
            resp = requests.post(url, json=payload, timeout=10)
            resp.raise_for_status()
            return True
        except requests.RequestException as e:
            log.error("не удалось отправить Telegram-алерт: %s", e)
            return False
