"""Тест формата строк для импорта в VictoriaMetrics (Prometheus exposition)."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "server" / "ingest"))

from storage.vm import to_prometheus_lines  # noqa: E402


def test_basic_line_with_agent_id_label():
    lines = to_prometheus_lines("agent-1", [("cpu_usage_percent", 12.5, {}, 1700000000000)])
    assert lines == ['cpu_usage_percent{agent_id="agent-1"} 12.5 1700000000000']


def test_labels_sorted_and_merged():
    lines = to_prometheus_lines(
        "a", [("disk_used_percent", 90.0, {"mount": "/", "fs": "ext4"}, 1)]
    )
    # labels отсортированы по ключу, agent_id добавлен
    assert lines == ['disk_used_percent{agent_id="a",fs="ext4",mount="/"} 90.0 1']


def test_escaping_quotes_and_backslashes():
    lines = to_prometheus_lines("a", [("m", 1.0, {"path": 'C:\\x "y"'}, 1)])
    assert lines == ['m{agent_id="a",path="C:\\\\x \\"y\\""} 1.0 1']
