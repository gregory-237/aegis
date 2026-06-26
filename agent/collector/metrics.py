"""Снятие метрик хоста через psutil."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

import psutil


@dataclass
class Sample:
    name: str
    value: float
    ts: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    labels: dict[str, str] = field(default_factory=dict)


def collect() -> list[Sample]:
    out: list[Sample] = []
    now = datetime.now(timezone.utc)

    def add(name: str, value: float, **labels: str) -> None:
        out.append(Sample(name=name, value=float(value), ts=now, labels=labels))

    add("cpu_usage_percent", psutil.cpu_percent(interval=None))
    try:
        load1, load5, load15 = psutil.getloadavg()
        add("load_avg_1m", load1)
        add("load_avg_5m", load5)
        add("load_avg_15m", load15)
    except (OSError, AttributeError):
        pass

    vm = psutil.virtual_memory()
    add("mem_total_bytes", vm.total)
    add("mem_used_bytes", vm.used)
    add("mem_used_percent", vm.percent)
    sw = psutil.swap_memory()
    add("swap_used_percent", sw.percent)

    for part in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except (PermissionError, OSError):
            continue
        add("disk_used_percent", usage.percent, mount=part.mountpoint)
        add("disk_used_bytes", usage.used, mount=part.mountpoint)
        add("disk_total_bytes", usage.total, mount=part.mountpoint)

    net = psutil.net_io_counters()
    add("net_bytes_sent", net.bytes_sent)
    add("net_bytes_recv", net.bytes_recv)

    return out
