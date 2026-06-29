"""Тесты Telegram-алертов ingest."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "server" / "ingest"))

import alerts  # noqa: E402
from alerts import TelegramNotifier, format_message, severity_at_least  # noqa: E402


def test_severity_threshold():
    assert severity_at_least("CRITICAL", "WARNING")
    assert severity_at_least("WARNING", "WARNING")
    assert not severity_at_least("INFO", "WARNING")


def test_format_message_contains_fields():
    msg = format_message("agent-1", "drift", "CRITICAL", "правила изменены")
    assert "agent-1" in msg and "drift" in msg and "CRITICAL" in msg and "правила изменены" in msg


def test_disabled_without_token():
    n = TelegramNotifier("", "", "WARNING")
    assert n.enabled is False
    assert n.should_alert("CRITICAL") is False


def test_notify_sends_when_enabled(monkeypatch):
    captured = {}

    class Resp:
        def raise_for_status(self):
            return None

    def fake_post(url, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        return Resp()

    monkeypatch.setattr(alerts.requests, "post", fake_post)
    n = TelegramNotifier("tok123", "42", "WARNING")
    assert n.should_alert("WARNING") is True
    assert n.notify("a1", "service_down", "CRITICAL", "sshd упал") is True
    assert "bottok123/sendMessage" in captured["url"]
    assert captured["json"]["chat_id"] == "42"
    assert captured["json"]["parse_mode"] == "HTML"


def test_notify_skips_below_threshold(monkeypatch):
    called = {"n": 0}
    monkeypatch.setattr(
        alerts.requests, "post", lambda *a, **k: called.__setitem__("n", called["n"] + 1)
    )
    n = TelegramNotifier("tok", "42", "WARNING")
    assert n.notify("a1", "noise", "INFO", "ничего") is False
    assert called["n"] == 0
