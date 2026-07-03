"""Windows firewall backend через PowerShell (модуль NetSecurity).

Почему PowerShell, а не netsh: netsh advfirewall firewall add rule НЕ поддерживает
параметр group=, из-за чего команда возвращает rc=1 без внятной ошибки. New-NetFirewallRule
принимает -Group нормально, плюс лучше работает с IPv6 и позволяет чистой командой
Remove-NetFirewallRule -Group снять все наши правила разом.
"""
from __future__ import annotations

import re

from agent.policy.backends.base import Command, FirewallBackend
from agent.policy.model import FirewallRule

GROUP = "Aegis"
NAME_PREFIX = "Aegis-"
_NAME_RE = re.compile(r"Aegis-\S+")


def _rule_name(index: int, rule: FirewallRule) -> str:
    suffix = ("-" + rule.comment.replace(" ", "_")) if rule.comment else ""
    return f"{NAME_PREFIX}{index}{suffix}"


def _action(a: str) -> str:
    return "Allow" if a.upper() == "ACCEPT" else "Block"


def _direction(rule: FirewallRule) -> str:
    if rule.chain.upper() == "INPUT" or rule.direction.lower() == "in":
        return "Inbound"
    return "Outbound"


def _protocol(proto: str) -> str:
    p = (proto or "").lower()
    if p in ("tcp", "udp"):
        return p.upper()
    if p in ("icmp", "icmpv4"):
        return "ICMPv4"
    if p == "icmpv6":
        return "ICMPv6"
    return "Any"


def _ps(cmdlet: str, params: dict[str, str]) -> Command:
    """PowerShell-команда как argv: powershell -NoProfile -Command "cmdlet ...".

    Значения оборачиваем в '...' и экранируем внутренние апострофы удвоением.
    """
    parts = [cmdlet]
    for key, value in params.items():
        if value is None:
            continue
        parts.append(f"-{key} '{str(value).replace(chr(39), chr(39) * 2)}'")
    return Command(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", " ".join(parts)]
    )


class WindowsFirewallBackend(FirewallBackend):
    name = "windows-firewall"

    def build_commands(
        self,
        rules: list[FirewallRule],
        default_drop_output: bool,
    ) -> list[Command]:
        cmds: list[Command] = []

        # снять прежние правила группы Aegis (идемпотентность)
        cmds.append(
            Command(
                [
                    "powershell", "-NoProfile", "-NonInteractive", "-Command",
                    f"Remove-NetFirewallRule -Group '{GROUP}' -ErrorAction SilentlyContinue",
                ],
                allow_fail=True,
                note="remove old Aegis rules",
            )
        )

        for i, r in enumerate(rules):
            name = _rule_name(i, r)
            params: dict[str, str] = {
                "DisplayName": name,
                "Group": GROUP,
                "Direction": _direction(r),
                "Action": _action(r.action),
                "Protocol": _protocol(r.protocol),
                "Enabled": "True",
            }
            if r.remote:
                params["RemoteAddress"] = r.remote
            if r.port and r.protocol.lower() in ("tcp", "udp"):
                params["RemotePort"] = str(r.port)
            cmds.append(Command(_ps("New-NetFirewallRule", params).argv, note=r.comment))

        if default_drop_output:
            cmds.append(
                Command(
                    [
                        "powershell", "-NoProfile", "-NonInteractive", "-Command",
                        "Set-NetFirewallProfile -All -DefaultOutboundAction Block",
                    ],
                    note="default deny egress",
                )
            )
        return cmds

    def list_commands(self) -> list[Command]:
        return [
            Command(
                [
                    "powershell", "-NoProfile", "-NonInteractive", "-Command",
                    f"Get-NetFirewallRule -Group '{GROUP}' -ErrorAction SilentlyContinue "
                    "| Select-Object -ExpandProperty DisplayName",
                ],
                allow_fail=True,
            ),
        ]

    def desired_keys(self, rules, default_drop_output):
        return {_rule_name(i, r) for i, r in enumerate(rules)}

    def parse_current(self, outputs):
        names: set[str] = set()
        for out in outputs:
            for line in out.splitlines():
                m = _NAME_RE.match(line.strip())
                if m:
                    names.add(m.group(0))
        return names

    def cleanup_commands(self) -> list[Command]:
        return [
            Command(
                [
                    "powershell", "-NoProfile", "-NonInteractive", "-Command",
                    f"Remove-NetFirewallRule -Group '{GROUP}' -ErrorAction SilentlyContinue",
                ],
                allow_fail=True,
                note="remove all Aegis rules",
            ),
        ]
