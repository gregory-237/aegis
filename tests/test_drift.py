"""Тесты контроля дрейфа: чистое сравнение, симметрия парсера iptables, монитор."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from agent.policy import DriftMonitor, detect_drift  # noqa: E402
from agent.policy.backends.base import Command  # noqa: E402
from agent.policy.backends.linux import IptablesBackend  # noqa: E402
from agent.policy.backends.windows import WindowsFirewallBackend  # noqa: E402
from agent.policy.model import FirewallRule  # noqa: E402

# Реалистичный вывод `iptables -S AEGIS_OUT` (с -m модулями и /32, как делает iptables).
_IPT_OUT = """-N AEGIS_OUT
-A AEGIS_OUT -o lo -j ACCEPT
-A AEGIS_OUT -m state --state ESTABLISHED,RELATED -j ACCEPT
-A AEGIS_OUT -p udp -m udp --dport 53 -j ACCEPT
-A AEGIS_OUT -p tcp -m tcp --dport 53 -j ACCEPT
-A AEGIS_OUT -d 1.2.3.4/32 -p tcp -j ACCEPT
"""
_IPT_IN = "-N AEGIS_IN\n"

RULES = [FirewallRule(chain="OUTPUT", action="ACCEPT", protocol="tcp", remote="1.2.3.4")]


def test_detect_drift_pure():
    assert detect_drift({"a", "b"}, {"a", "b"}).drifted is False
    r = detect_drift({"a", "b"}, {"a", "c"})
    assert r.drifted is True
    assert r.missing == ["b"] and r.unexpected == ["c"]


def test_iptables_desired_matches_real_output():
    """Эталон из build_commands совпадает с разбором реального `iptables -S` -> нет дрейфа."""
    b = IptablesBackend()
    desired = b.desired_keys(RULES, default_drop_output=False)
    current = b.parse_current([_IPT_OUT, _IPT_IN])
    assert detect_drift(desired, current).drifted is False


def test_iptables_detects_missing_and_extra():
    b = IptablesBackend()
    desired = b.desired_keys(RULES, default_drop_output=False)

    tampered_missing = _IPT_OUT.replace("-A AEGIS_OUT -d 1.2.3.4/32 -p tcp -j ACCEPT\n", "")
    rep = detect_drift(desired, b.parse_current([tampered_missing, _IPT_IN]))
    assert rep.drifted and len(rep.missing) == 1

    tampered_extra = _IPT_OUT + "-A AEGIS_OUT -d 9.9.9.9/32 -j DROP\n"
    rep2 = detect_drift(desired, b.parse_current([tampered_extra, _IPT_IN]))
    assert rep2.drifted and len(rep2.unexpected) == 1


def test_windows_drift_by_name():
    b = WindowsFirewallBackend()
    rules = [FirewallRule(action="ACCEPT", protocol="tcp", remote="1.2.3.4", comment="allow x")]
    desired = b.desired_keys(rules, default_drop_output=False)
    # имитируем вывод `netsh ... show rule` с локализованными метками, но нашим именем
    netsh_out = "Имя правила:  Aegis-0-allow_x\nВключено:  Да\nДействие:  Allow\n"
    assert detect_drift(desired, b.parse_current([netsh_out])).drifted is False
    # правило удалили вручную -> дрейф
    assert detect_drift(desired, b.parse_current(["(пусто)"])).drifted is True


def _fake_runner(out_text: str, in_text: str):
    calls = {"build": 0}

    def run(cmd: Command):
        argv = cmd.argv
        if argv[:2] == ["iptables", "-S"]:
            return 0, (out_text if argv[-1] == "AEGIS_OUT" else in_text), ""
        calls["build"] += 1  # это команда применения (-N/-F/-A ...)
        return 0, "", ""

    return run, calls


def test_monitor_check_and_rollback():
    b = IptablesBackend()
    run, calls = _fake_runner(_IPT_OUT, _IPT_IN)
    mon = DriftMonitor(b, runner=run)
    mon.set_reference(RULES, default_drop_output=False)

    assert mon.check().drifted is False  # факт совпадает с эталоном

    # эмулируем удаление правила -> дрейф -> откат
    run2, calls2 = _fake_runner(_IPT_OUT.replace("-A AEGIS_OUT -d 1.2.3.4/32 -p tcp -j ACCEPT\n", ""), _IPT_IN)
    mon2 = DriftMonitor(b, runner=run2)
    mon2.set_reference(RULES, default_drop_output=False)
    assert mon2.check().drifted is True
    failures = mon2.rollback()
    assert failures == []
    assert calls2["build"] > 0  # эталонные команды были выполнены заново
