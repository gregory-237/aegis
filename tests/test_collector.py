"""Тесты сборщика метрик (psutil)."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from agent.collector import Sample, collect


def test_collect_returns_core_metrics():
    samples = collect()
    assert samples, "collect() не вернул ни одной метрики"
    assert all(isinstance(s, Sample) for s in samples)

    names = {s.name for s in samples}
    # базовые метрики должны присутствовать на любой ОС
    for required in ("cpu_usage_percent", "mem_used_percent", "net_bytes_sent"):
        assert required in names, f"нет метрики {required}"


def test_percent_metrics_in_range():
    for s in collect():
        if s.name.endswith("_percent"):
            assert 0.0 <= s.value <= 100.0, f"{s.name}={s.value} вне диапазона"
