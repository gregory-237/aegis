"""Тесты модуля политики: модель, генерация правил, безопасный dry-run."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import agent.policy.manager as manager_mod  # noqa: E402
from agent.policy import Policy, PolicyManager  # noqa: E402
from agent.policy.backends.linux import OUT_CHAIN, IptablesBackend  # noqa: E402
from agent.policy.backends.windows import WindowsFirewallBackend  # noqa: E402
from agent.policy.model import FirewallRule  # noqa: E402


def test_policy_dict_roundtrip():
    p = Policy(
        firewall=[FirewallRule(action="DROP", protocol="tcp", port=22, remote="10.0.0.0/8")],
        allowed_domains=["example.com"],
        monitored_services=["sshd"],
        metrics_interval_sec=15,
        version="v2",
    )
    assert Policy.from_dict(p.to_dict()) == p


def test_iptables_rule_generation():
    b = IptablesBackend()
    cmds = b.build_commands(
        [FirewallRule(chain="OUTPUT", action="ACCEPT", protocol="tcp", port=443, remote="1.2.3.4")],
        default_drop_output=True,
    )
    flat = [c.argv for c in cmds]
    assert ["iptables", "-N", OUT_CHAIN] in flat          # цепочка создаётся
    assert ["iptables", "-A", "OUTPUT", "-j", OUT_CHAIN] in flat  # и прицепляется
    assert [
        "iptables", "-A", OUT_CHAIN, "-p", "tcp", "-d", "1.2.3.4", "--dport", "443", "-j", "ACCEPT"
    ] in flat
    assert flat[-1] == ["iptables", "-A", OUT_CHAIN, "-j", "DROP"]  # default deny в конце


def test_windows_rule_generation():
    b = WindowsFirewallBackend()
    cmds = b.build_commands(
        [FirewallRule(action="DROP", protocol="tcp", port=445, remote="0.0.0.0/0")],
        default_drop_output=False,
    )
    text = [str(c) for c in cmds]
    assert any("delete rule" in x for x in text)          # снос старых правил Aegis
    assert any("action=block" in x and "remoteport=445" in x for x in text)


def test_manager_compiles_whitelist_to_accepts(monkeypatch):
    monkeypatch.setattr(manager_mod, "resolve_domain", lambda d: ["9.9.9.9"])
    mgr = PolicyManager(backend=IptablesBackend(), server_host="srv")
    rules, resolved = mgr.compile_rules(Policy(allowed_domains=["example.com"]))
    assert resolved["example.com"] == ["9.9.9.9"]
    assert any(r.remote == "9.9.9.9" and r.action == "ACCEPT" for r in rules)


def test_manager_dry_run_does_not_execute(monkeypatch):
    monkeypatch.setattr(manager_mod, "resolve_domain", lambda d: ["9.9.9.9"])
    calls = {"n": 0}
    monkeypatch.setattr(
        PolicyManager, "_run", staticmethod(lambda cmd: calls.__setitem__("n", calls["n"] + 1))
    )
    mgr = PolicyManager(backend=IptablesBackend(), server_host="srv")
    res = mgr.apply(Policy(allowed_domains=["example.com"]), dry_run=True)
    assert res.executed is False
    assert calls["n"] == 0                  # ни одна команда не выполнена
    assert res.default_drop_output is True  # whitelist => default deny


def test_manager_apply_without_privilege_fails_safely(monkeypatch):
    monkeypatch.setattr(manager_mod, "resolve_domain", lambda d: [])
    monkeypatch.setattr(manager_mod, "is_privileged", lambda: False)
    ran = {"n": 0}
    monkeypatch.setattr(
        PolicyManager, "_run", staticmethod(lambda cmd: ran.__setitem__("n", ran["n"] + 1))
    )
    mgr = PolicyManager(backend=IptablesBackend(), server_host="")
    res = mgr.apply(Policy(firewall=[FirewallRule(action="DROP")]), dry_run=False)
    assert res.executed is False
    assert ran["n"] == 0
    assert res.failures  # сообщил, что нет прав
