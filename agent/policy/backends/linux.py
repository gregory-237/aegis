"""Linux firewall backend на iptables. Правила живут в выделенных цепочках
AEGIS_OUT / AEGIS_IN, чтобы не затрагивать чужие правила и быть идемпотентными."""
from __future__ import annotations

from agent.policy.backends.base import Command, FirewallBackend
from agent.policy.model import FirewallRule

OUT_CHAIN = "AEGIS_OUT"
IN_CHAIN = "AEGIS_IN"
_IPT = "iptables"


def _action(a: str) -> str:
    a = a.upper()
    return a if a in ("ACCEPT", "DROP", "REJECT") else "ACCEPT"


def _strip_mask(remote: str) -> str:
    for suffix in ("/32", "/128"):
        if remote.endswith(suffix):
            return remote[: -len(suffix)]
    return remote


def _ipt_rule_key(chain: str, tokens: list[str]):
    """Токены правила (после '-A CHAIN') -> канонический ключ или None (не правило).

    Нормализует вывод так, чтобы наши команды (-A ...) и вывод `iptables -S`
    давали одинаковый ключ: пропускает '-m <module>', снимает /32 и /128, и т.п.
    """
    feats: dict[str, str] = {}
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t == "-p" and i + 1 < len(tokens):
            feats["proto"] = tokens[i + 1].lower(); i += 2
        elif t in ("-d", "-s") and i + 1 < len(tokens):
            feats["remote"] = _strip_mask(tokens[i + 1]); i += 2
        elif t in ("-o", "-i") and i + 1 < len(tokens):
            feats["iface"] = tokens[i + 1]; i += 2
        elif t in ("--dport", "--sport") and i + 1 < len(tokens):
            feats["dport"] = tokens[i + 1]; i += 2
        elif t == "--state" and i + 1 < len(tokens):
            feats["state"] = tokens[i + 1]; i += 2
        elif t == "-m":
            i += 2  # пропускаем имя модуля (state/tcp/udp/...)
        elif t == "-j" and i + 1 < len(tokens):
            feats["action"] = tokens[i + 1].upper(); i += 2
        else:
            i += 1
    if "action" not in feats:
        return None  # строки -N/-F и т.п.
    scope = "out" if "OUT" in chain.upper() else "in"
    return (scope, frozenset(feats.items()))


class IptablesBackend(FirewallBackend):
    name = "iptables"

    def _rule_to_argv(self, chain: str, r: FirewallRule) -> list[str]:
        argv = [_IPT, "-A", chain]
        proto = r.protocol.lower()
        if proto and proto != "all":
            argv += ["-p", proto]
        if r.remote:
            argv += (["-s", r.remote] if chain == IN_CHAIN else ["-d", r.remote])
        if r.port and proto in ("tcp", "udp"):
            argv += ["--dport", str(r.port)]
        argv += ["-j", _action(r.action)]
        return argv

    def _setup_chain(self, chain: str, base_chain: str) -> list[Command]:
        # создать-или-очистить цепочку и однократно прицепить её к базовой
        return [
            Command([_IPT, "-N", chain], allow_fail=True, note=f"create {chain}"),
            Command([_IPT, "-F", chain], note=f"flush {chain}"),
            Command([_IPT, "-D", base_chain, "-j", chain], allow_fail=True, note="detach old"),
            Command([_IPT, "-A", base_chain, "-j", chain], note=f"attach {chain}"),
        ]

    def build_commands(
        self,
        rules: list[FirewallRule],
        default_drop_output: bool,
    ) -> list[Command]:
        cmds: list[Command] = []
        cmds += self._setup_chain(OUT_CHAIN, "OUTPUT")
        cmds += self._setup_chain(IN_CHAIN, "INPUT")

        # базовые разрешения, чтобы машина не «ослепла» при default drop
        for argv in (
            [_IPT, "-A", OUT_CHAIN, "-o", "lo", "-j", "ACCEPT"],
            [_IPT, "-A", OUT_CHAIN, "-m", "state", "--state", "ESTABLISHED,RELATED", "-j", "ACCEPT"],
            [_IPT, "-A", OUT_CHAIN, "-p", "udp", "--dport", "53", "-j", "ACCEPT"],
            [_IPT, "-A", OUT_CHAIN, "-p", "tcp", "--dport", "53", "-j", "ACCEPT"],
        ):
            cmds.append(Command(argv, note="baseline allow"))

        for r in rules:
            chain = IN_CHAIN if r.chain.upper() == "INPUT" else OUT_CHAIN
            cmds.append(Command(self._rule_to_argv(chain, r), note=r.comment))

        if default_drop_output:
            cmds.append(Command([_IPT, "-A", OUT_CHAIN, "-j", "DROP"], note="default deny egress"))
        return cmds

    def list_commands(self) -> list[Command]:
        return [
            Command([_IPT, "-S", OUT_CHAIN], allow_fail=True),
            Command([_IPT, "-S", IN_CHAIN], allow_fail=True),
        ]

    def desired_keys(self, rules, default_drop_output):
        keys = set()
        for c in self.build_commands(rules, default_drop_output):
            a = c.argv
            if len(a) >= 3 and a[1] == "-A" and a[2] in (OUT_CHAIN, IN_CHAIN):
                k = _ipt_rule_key(a[2], a[3:])
                if k:
                    keys.add(k)
        return keys

    def parse_current(self, outputs):
        keys = set()
        for out in outputs:
            for line in out.splitlines():
                toks = line.split()
                if len(toks) >= 2 and toks[0] == "-A":
                    k = _ipt_rule_key(toks[1], toks[2:])
                    if k:
                        keys.add(k)
        return keys

    def cleanup_commands(self) -> list[Command]:
        return [
            Command([_IPT, "-D", "OUTPUT", "-j", OUT_CHAIN], allow_fail=True, note="detach out"),
            Command([_IPT, "-D", "INPUT", "-j", IN_CHAIN], allow_fail=True, note="detach in"),
            Command([_IPT, "-F", OUT_CHAIN], allow_fail=True, note="flush out"),
            Command([_IPT, "-F", IN_CHAIN], allow_fail=True, note="flush in"),
            Command([_IPT, "-X", OUT_CHAIN], allow_fail=True, note="drop out chain"),
            Command([_IPT, "-X", IN_CHAIN], allow_fail=True, note="drop in chain"),
        ]
