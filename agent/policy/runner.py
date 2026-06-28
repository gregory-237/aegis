"""Выполнение команд firewall (argv, без shell). Общий для применения и контроля дрейфа."""
from __future__ import annotations

import logging
import subprocess

from agent.policy.backends.base import Command

log = logging.getLogger("agent.policy.runner")


def run(cmd: Command, timeout: float = 15.0) -> tuple[int, str, str]:
    """Запускает команду, возвращает (returncode, stdout, stderr)."""
    try:
        proc = subprocess.run(cmd.argv, capture_output=True, text=True, timeout=timeout)
        return proc.returncode, proc.stdout, proc.stderr
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        log.warning("ошибка выполнения %s: %s", cmd, e)
        return 1, "", str(e)
