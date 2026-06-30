"""Запросы свежих значений метрик из VictoriaMetrics для веб-страниц."""
from __future__ import annotations

import logging

import requests
from django.conf import settings

log = logging.getLogger("aegis.web.metrics")

# Метрики, которые показываем на карточке машины.
LATEST_METRICS = [
    ("cpu_usage_percent", "CPU, %"),
    ("mem_used_percent", "RAM, %"),
    ("swap_used_percent", "Swap, %"),
]


def _instant(query: str) -> list[dict]:
    url = settings.AEGIS_VM_URL.rstrip("/") + "/api/v1/query"
    try:
        resp = requests.get(url, params={"query": query}, timeout=5)
        resp.raise_for_status()
        return resp.json().get("data", {}).get("result", [])
    except (requests.RequestException, ValueError) as e:
        log.warning("VM query failed (%s): %s", query, e)
        return []


def latest_for_agent(agent_id: str) -> dict[str, float]:
    """Последние значения базовых метрик по машине. Пустой dict если VM недоступна."""
    out: dict[str, float] = {}
    safe = agent_id.replace('"', '\\"')
    for name, _label in LATEST_METRICS:
        result = _instant(f'{name}{{agent_id="{safe}"}}')
        if result:
            try:
                out[name] = round(float(result[0]["value"][1]), 1)
            except (KeyError, IndexError, ValueError):
                continue
    return out


def disk_for_agent(agent_id: str) -> list[tuple[str, float]]:
    """Заполненность дисков по точкам монтирования: [(mount, percent), ...]."""
    safe = agent_id.replace('"', '\\"')
    result = _instant(f'disk_used_percent{{agent_id="{safe}"}}')
    disks: list[tuple[str, float]] = []
    for series in result:
        mount = series.get("metric", {}).get("mount", "?")
        try:
            disks.append((mount, round(float(series["value"][1]), 1)))
        except (KeyError, IndexError, ValueError):
            continue
    return sorted(disks)
