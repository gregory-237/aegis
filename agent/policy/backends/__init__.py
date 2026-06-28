"""Платформенные бэкенды firewall."""
from __future__ import annotations

import platform

from agent.policy.backends.base import Command, FirewallBackend


def get_backend() -> FirewallBackend:
    """Выбирает бэкенд по ОС: Linux -> iptables, Windows -> Windows Firewall."""
    system = platform.system().lower()
    if system == "linux":
        from agent.policy.backends.linux import IptablesBackend

        return IptablesBackend()
    if system == "windows":
        from agent.policy.backends.windows import WindowsFirewallBackend

        return WindowsFirewallBackend()
    from agent.policy.backends.noop import NoopBackend

    return NoopBackend(system)


__all__ = ["Command", "FirewallBackend", "get_backend"]
