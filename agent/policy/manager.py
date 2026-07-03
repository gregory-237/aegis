"""Менеджер политики: компиляция Policy -> команды firewall и их применение."""
from __future__ import annotations

import ctypes
import logging
import os
import platform
import socket
import threading
from dataclasses import dataclass, field

from agent.policy.backends import Command, FirewallBackend, get_backend
from agent.policy.model import FirewallRule, Policy
from agent.policy.runner import run as run_command

log = logging.getLogger("agent.policy")


def is_privileged() -> bool:
    if platform.system().lower() == "windows":
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            return False
    return hasattr(os, "geteuid") and os.geteuid() == 0


def resolve_domain(domain: str, timeout: float = 3.0) -> list[str]:
    # Резолв в daemon-потоке: несуществующие .local через mDNS/LLMNR на Windows
    # умеют висеть по 15-30 секунд и подвешивать агента.
    result: list[str] = []

    def _resolve() -> None:
        nonlocal result
        try:
            infos = socket.getaddrinfo(domain, None)
            result = sorted({info[4][0] for info in infos})
        except (socket.gaierror, OSError):
            result = []

    t = threading.Thread(target=_resolve, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        log.warning("резолв %s превысил %.0f c — пропускаю", domain, timeout)
        return []
    return result


@dataclass
class PlanResult:
    backend: str
    commands: list[str]
    default_drop_output: bool
    resolved: dict[str, list[str]] = field(default_factory=dict)
    executed: bool = False
    failures: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failures


class PolicyManager:
    def __init__(self, backend: FirewallBackend | None = None, server_host: str = "") -> None:
        self._backend = backend or get_backend()
        self._server_host = server_host
        self._last_rules: list[FirewallRule] = []
        self._last_default_drop = False

    @property
    def backend(self) -> FirewallBackend:
        return self._backend

    @property
    def last_reference(self) -> tuple[list[FirewallRule], bool]:
        return self._last_rules, self._last_default_drop

    def compile_rules(self, policy: Policy) -> tuple[list[FirewallRule], dict[str, list[str]]]:
        rules: list[FirewallRule] = list(policy.firewall)
        resolved: dict[str, list[str]] = {}

        for domain in policy.allowed_domains:
            ips = resolve_domain(domain)
            resolved[domain] = ips
            for ip in ips:
                rules.append(
                    FirewallRule(
                        chain="OUTPUT", action="ACCEPT", protocol="tcp",
                        remote=ip, comment=f"allow {domain}",
                    )
                )

        for ip in resolve_domain(self._server_host) if self._server_host else []:
            rules.append(
                FirewallRule(
                    chain="OUTPUT", action="ACCEPT", remote=ip, comment="aegis server"
                )
            )
        return rules, resolved

    def plan(self, policy: Policy, *, demo_safe: bool = False) -> tuple[list[Command], PlanResult]:
        rules, resolved = self.compile_rules(policy)
        # В demo-safe режиме не трогаем глобальную default-policy: возврат к исходному
        # состоянию хоста при выходе агента упирается в сохранение чужой конфигурации,
        # поэтому проще не менять её вовсе. Свои ACCEPT-правила при этом остаются.
        default_drop = bool(policy.allowed_domains) and not demo_safe
        self._last_rules, self._last_default_drop = rules, default_drop
        cmds = self._backend.build_commands(rules, default_drop_output=default_drop)
        result = PlanResult(
            backend=self._backend.name,
            commands=[str(c) for c in cmds],
            default_drop_output=default_drop,
            resolved=resolved,
        )
        return cmds, result

    def apply(self, policy: Policy, dry_run: bool = True, demo_safe: bool = False) -> PlanResult:
        cmds, result = self.plan(policy, demo_safe=demo_safe)
        log.info(
            "политика v=%s backend=%s: %d команд, default_drop=%s, dry_run=%s",
            policy.version, result.backend, len(cmds), result.default_drop_output, dry_run,
        )
        for d, ips in result.resolved.items():
            log.info("  whitelist %s -> %s", d, ips or "(не резолвится)")

        if dry_run:
            for c in cmds:
                log.info("  [dry-run] %s", c)
            return result

        if not is_privileged():
            msg = "нет прав root/Administrator — правила не применены"
            log.error(msg)
            result.failures.append(msg)
            return result

        for c in cmds:
            rc = self._run(c)
            if rc != 0 and not c.allow_fail:
                result.failures.append(f"rc={rc}: {c}")
        result.executed = True
        if result.ok:
            log.info("политика применена успешно (%d команд)", len(cmds))
        else:
            log.error("политика применена с ошибками: %s", result.failures)
        return result

    @staticmethod
    def _run(cmd: Command) -> int:
        rc, _out, err = run_command(cmd)
        if rc != 0 and not cmd.allow_fail:
            log.warning("команда не удалась (%s): %s", rc, err.strip())
        return rc

    def cleanup(self, dry_run: bool = False) -> list[str]:
        """Снять применённые правила Aegis. Возвращает список ошибок (пустой = ок)."""
        cmds = self._backend.cleanup_commands()
        if not cmds:
            return []
        log.info("снимаю правила Aegis (%d команд, dry_run=%s)", len(cmds), dry_run)
        failures: list[str] = []
        if dry_run:
            for c in cmds:
                log.info("  [dry-run cleanup] %s", c)
            return failures
        if not is_privileged():
            log.warning("нет прав root/Administrator — cleanup пропущен")
            return ["no privileges"]
        for c in cmds:
            rc = self._run(c)
            if rc != 0 and not c.allow_fail:
                failures.append(f"rc={rc}: {c}")
        if failures:
            log.error("cleanup с ошибками: %s", failures)
        else:
            log.info("правила Aegis сняты, состояние восстановлено")
        return failures
