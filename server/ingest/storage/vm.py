"""Запись метрик в VictoriaMetrics через HTTP import (Prometheus exposition format).

Формат строки: `name{label="v",agent_id="id"} value timestamp_ms`
Эндпоинт VM: POST {vm_url}/api/v1/import/prometheus
"""
from __future__ import annotations

import logging
from typing import Iterable, Sequence

import requests

log = logging.getLogger("ingest.vm")


def _escape(value: str) -> str:
    """Экранирование значения label по правилам Prometheus."""
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def to_prometheus_lines(
    agent_id: str,
    samples: Iterable[tuple[str, float, dict[str, str], int]],
) -> list[str]:
    """samples: (name, value, labels, ts_ms). agent_id добавляется как label."""
    lines: list[str] = []
    for name, value, labels, ts_ms in samples:
        all_labels = {**labels, "agent_id": agent_id}
        label_str = ",".join(f'{k}="{_escape(str(v))}"' for k, v in sorted(all_labels.items()))
        lines.append(f"{name}{{{label_str}}} {value} {ts_ms}")
    return lines


class MetricsStore:
    """Тонкий клиент VictoriaMetrics. Пустой url -> выключен (метрики только в лог)."""

    def __init__(self, url: str, timeout: float = 10.0) -> None:
        self._url = url.rstrip("/")
        self._timeout = timeout
        self.enabled = bool(self._url)
        if not self.enabled:
            log.warning("VictoriaMetrics не настроен (AEGIS_VM_URL пуст) — метрики не сохраняются")

    def write(
        self,
        agent_id: str,
        samples: Sequence[tuple[str, float, dict[str, str], int]],
    ) -> int:
        """Возвращает число записанных метрик. При ошибке логирует и кидает исключение."""
        if not self.enabled or not samples:
            return 0
        lines = to_prometheus_lines(agent_id, samples)
        body = "\n".join(lines).encode("utf-8")
        resp = requests.post(
            f"{self._url}/api/v1/import/prometheus",
            data=body,
            headers={"Content-Type": "text/plain"},
            timeout=self._timeout,
        )
        resp.raise_for_status()
        return len(lines)
