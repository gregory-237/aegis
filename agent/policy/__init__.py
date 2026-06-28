"""Модуль политики: применение firewall/доступов при старте и контроль дрейфа.

Linux -> iptables, Windows -> Windows Firewall. По умолчанию dry-run (безопасно).
"""
from agent.policy.drift import DriftMonitor, DriftReport, detect_drift
from agent.policy.manager import PlanResult, PolicyManager, is_privileged
from agent.policy.model import FirewallRule, Policy

__all__ = [
    "FirewallRule",
    "Policy",
    "PolicyManager",
    "PlanResult",
    "is_privileged",
    "DriftMonitor",
    "DriftReport",
    "detect_drift",
]
