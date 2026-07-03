"""Контроль дрейфа: сверка правил firewall с эталоном и откат отклонений."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable

from agent.policy.backends.base import Command, FirewallBackend
from agent.policy.model import FirewallRule
from agent.policy.runner import run as default_run

log = logging.getLogger("agent.policy.drift")

# Раннер команды -> (returncode, stdout, stderr). Инъекция упрощает тесты.
Runner = Callable[[Command], "tuple[int, str, str]"]


@dataclass
class DriftReport:
    drifted: bool
    missing: list[str] = field(default_factory=list)      # эталонные правила, которых нет
    unexpected: list[str] = field(default_factory=list)   # лишние (добавленные вручную)

    def summary(self) -> str:
        return f"missing={len(self.missing)} unexpected={len(self.unexpected)}"


def detect_drift(desired: set, current: set) -> DriftReport:
    missing = desired - current
    unexpected = current - desired
    return DriftReport(
        drifted=bool(missing or unexpected),
        missing=sorted(str(x) for x in missing),
        unexpected=sorted(str(x) for x in unexpected),
    )


class DriftMonitor:
    def __init__(self, backend: FirewallBackend, runner: Runner | None = None) -> None:
        self._backend = backend
        self._run = runner or default_run
        self._rules: list[FirewallRule] = []
        self._default_drop = False
        self._desired: set = set()

    def set_reference(self, rules: list[FirewallRule], default_drop_output: bool) -> None:
        """Запомнить эталон (то, что было применено)."""
        self._rules = list(rules)
        self._default_drop = default_drop_output
        self._desired = self._backend.desired_keys(rules, default_drop_output)

    def read_current(self) -> set:
        outputs: list[str] = []
        for cmd in self._backend.list_commands():
            _rc, out, _err = self._run(cmd)
            outputs.append(out)
        return self._backend.parse_current(outputs)

    def check(self) -> DriftReport:
        return detect_drift(self._desired, self.read_current())

    def rollback(self) -> list[str]:
        """Повторно применить эталонные правила. Возвращает список ошибок."""
        failures: list[str] = []
        for cmd in self._backend.build_commands(self._rules, self._default_drop):
            rc, out, err = self._run(cmd)
            if rc != 0 and not cmd.allow_fail:
                msg = (err.strip() or out.strip() or "<no output>").splitlines()[-1][:200]
                failures.append(f"rc={rc}: {cmd} :: {msg}")
        if failures:
            log.error("откат с ошибками: %s", failures)
        else:
            log.info("эталон восстановлен (%d правил)", len(self._rules))
        return failures
