"""Заглушка-бэкенд для неподдерживаемых ОС: ничего не применяет, только сообщает."""
from __future__ import annotations

from agent.policy.backends.base import Command, FirewallBackend
from agent.policy.model import FirewallRule


class NoopBackend(FirewallBackend):
    name = "noop"

    def __init__(self, system: str) -> None:
        self._system = system

    def build_commands(self, rules: list[FirewallRule], default_drop_output: bool) -> list[Command]:
        return []

    def list_commands(self) -> list[Command]:
        return []

    def desired_keys(self, rules: list[FirewallRule], default_drop_output: bool) -> set:
        return set()

    def parse_current(self, outputs: list[str]) -> set:
        return set()
