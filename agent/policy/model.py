"""Модель политики безопасности машины (firewall + whitelist доменов + что мониторить)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FirewallRule:
    chain: str = "OUTPUT"        # INPUT | OUTPUT | FORWARD
    action: str = "ACCEPT"       # ACCEPT | DROP | REJECT
    protocol: str = "all"        # tcp | udp | icmp | all
    direction: str = "out"       # in | out
    remote: str = ""             # CIDR/host, "" = любой
    port: int = 0                # 0 = любой
    comment: str = ""

    @staticmethod
    def from_pb(pb_rule: Any) -> "FirewallRule":
        return FirewallRule(
            chain=pb_rule.chain or "OUTPUT",
            action=pb_rule.action or "ACCEPT",
            protocol=pb_rule.protocol or "all",
            direction=pb_rule.direction or "out",
            remote=pb_rule.remote,
            port=int(pb_rule.port),
            comment=pb_rule.comment,
        )

    @staticmethod
    def from_dict(d: dict) -> "FirewallRule":
        return FirewallRule(
            chain=d.get("chain", "OUTPUT"),
            action=d.get("action", "ACCEPT"),
            protocol=d.get("protocol", "all"),
            direction=d.get("direction", "out"),
            remote=d.get("remote", ""),
            port=int(d.get("port", 0)),
            comment=d.get("comment", ""),
        )

    def to_dict(self) -> dict:
        return {
            "chain": self.chain,
            "action": self.action,
            "protocol": self.protocol,
            "direction": self.direction,
            "remote": self.remote,
            "port": self.port,
            "comment": self.comment,
        }


@dataclass
class Policy:
    firewall: list[FirewallRule] = field(default_factory=list)
    allowed_domains: list[str] = field(default_factory=list)
    monitored_services: list[str] = field(default_factory=list)
    metrics_interval_sec: int = 30
    version: str = "v0"

    @staticmethod
    def from_pb(pb_policy: Any, version: str = "v0") -> "Policy":
        return Policy(
            firewall=[FirewallRule.from_pb(r) for r in pb_policy.firewall],
            allowed_domains=list(pb_policy.allowed_domains),
            monitored_services=list(pb_policy.monitored_services),
            metrics_interval_sec=int(pb_policy.metrics_interval_sec) or 30,
            version=version,
        )

    @staticmethod
    def from_dict(d: dict) -> "Policy":
        return Policy(
            firewall=[FirewallRule.from_dict(r) for r in d.get("firewall", [])],
            allowed_domains=list(d.get("allowed_domains", [])),
            monitored_services=list(d.get("monitored_services", [])),
            metrics_interval_sec=int(d.get("metrics_interval_sec", 30)),
            version=d.get("version", "v0"),
        )

    def to_dict(self) -> dict:
        return {
            "firewall": [r.to_dict() for r in self.firewall],
            "allowed_domains": self.allowed_domains,
            "monitored_services": self.monitored_services,
            "metrics_interval_sec": self.metrics_interval_sec,
            "version": self.version,
        }
