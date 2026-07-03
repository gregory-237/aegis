"""Windows firewall backend на netsh advfirewall. Правила помечаются именем
'Aegis-*' и группой, чтобы их можно было найти/снять и не трогать чужие."""
from __future__ import annotations

import re

from agent.policy.backends.base import Command, FirewallBackend
from agent.policy.model import FirewallRule

_NETSH = ["netsh", "advfirewall", "firewall"]
GROUP = "Aegis"
NAME_PREFIX = "Aegis-"
# Имена правил Aegis не локализуются (в отличие от меток netsh), поэтому дрейф на
# Windows сверяем по именам — это устойчиво к языку ОС.
_NAME_RE = re.compile(r"Aegis-\S+")


def _rule_name(index: int, rule: FirewallRule) -> str:
    # без пробелов, чтобы имя целиком ловилось одним токеном при разборе вывода
    suffix = ("-" + rule.comment.replace(" ", "_")) if rule.comment else ""
    return f"{NAME_PREFIX}{index}{suffix}"


def _action(a: str) -> str:
    # ACCEPT -> allow; DROP/REJECT -> block
    return "allow" if a.upper() == "ACCEPT" else "block"


def _dir(rule: FirewallRule) -> str:
    if rule.chain.upper() == "INPUT" or rule.direction.lower() == "in":
        return "in"
    return "out"


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
                _NETSH + ["delete", "rule", f"name=all", f"group={GROUP}"],
                allow_fail=True,
                note="remove old Aegis rules",
            )
        )

        for i, r in enumerate(rules):
            name = _rule_name(i, r)
            argv = _NETSH + [
                "add",
                "rule",
                f"name={name}",
                f"dir={_dir(r)}",
                f"action={_action(r.action)}",
                f"group={GROUP}",
                "enable=yes",
            ]
            proto = r.protocol.lower()
            argv.append(f"protocol={proto if proto and proto != 'all' else 'any'}")
            if r.remote:
                argv.append(f"remoteip={r.remote}")
            if r.port and proto in ("tcp", "udp"):
                argv.append(f"remoteport={r.port}")
            cmds.append(Command(argv, note=r.comment))

        if default_drop_output:
            # запрет всего исходящего по умолчанию (разрешённое — добавлено выше allow-правилами)
            cmds.append(
                Command(
                    ["netsh", "advfirewall", "set", "allprofiles", "firewallpolicy",
                     "blockinbound,blockoutbound"],
                    note="default deny egress",
                )
            )
        return cmds

    def list_commands(self) -> list[Command]:
        return [
            Command(_NETSH + ["show", "rule", f"name=all", f"group={GROUP}"], allow_fail=True),
        ]

    def desired_keys(self, rules, default_drop_output):
        # эталон = имена правил, которые мы создадим
        return {_rule_name(i, r) for i, r in enumerate(rules)}

    def parse_current(self, outputs):
        names: set[str] = set()
        for out in outputs:
            for m in _NAME_RE.findall(out):
                names.add(m.rstrip(",;."))
        return names

    def cleanup_commands(self) -> list[Command]:
        return [
            Command(
                _NETSH + ["delete", "rule", "name=all", f"group={GROUP}"],
                allow_fail=True,
                note="remove all Aegis rules",
            ),
        ]
