"""Тесты локального буфера метрик агента."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from agent.collector import Sample
from agent.transport import MetricsBuffer


def test_add_and_drain_roundtrip(tmp_path: pathlib.Path):
    buf = MetricsBuffer(tmp_path / "m.jsonl", max_items=100)
    assert buf.is_empty()

    buf.add([Sample(name="cpu_usage_percent", value=12.5, labels={"host": "a"})])
    assert not buf.is_empty()

    drained = buf.drain()
    assert len(drained) == 1
    assert drained[0].name == "cpu_usage_percent"
    assert drained[0].value == 12.5
    assert drained[0].labels == {"host": "a"}
    # после drain буфер пуст
    assert buf.is_empty()
    assert buf.drain() == []


def test_trim_keeps_last_items(tmp_path: pathlib.Path):
    buf = MetricsBuffer(tmp_path / "m.jsonl", max_items=5)
    buf.add([Sample(name="x", value=float(i)) for i in range(20)])
    drained = buf.drain()
    assert len(drained) == 5
    # остались последние пять (15..19)
    assert [int(s.value) for s in drained] == [15, 16, 17, 18, 19]
