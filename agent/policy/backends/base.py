"""Базовый интерфейс firewall-бэкенда. Бэкенд лишь СТРОИТ команды (argv),
выполнение и проверки прав — в менеджере. Это делает генерацию правил чистой и тестируемой."""
from __future__ import annotations

import abc
from dataclasses import dataclass, field

from agent.policy.model import FirewallRule


@dataclass
class Command:
    """Одна команда настройки firewall как argv (без shell)."""

    argv: list[str]
    # allow_fail=True для идемпотентных шагов (создать цепочку, удалить старое правило),
    # которые могут «упасть», если объекта ещё/уже нет — это нормально.
    allow_fail: bool = False
    note: str = ""

    def __str__(self) -> str:
        return " ".join(self.argv)


class FirewallBackend(abc.ABC):
    name: str = "base"

    @abc.abstractmethod
    def build_commands(
        self,
        rules: list[FirewallRule],
        default_drop_output: bool,
    ) -> list[Command]:
        """Сформировать идемпотентный набор команд для применения правил.

        rules — уже «скомпилированные» правила (включая ACCEPT для разрешённых IP).
        default_drop_output — добавить запрет всего остального исходящего трафика.
        """

    @abc.abstractmethod
    def list_commands(self) -> list[Command]:
        """Команды для чтения текущих правил (используется контролем дрейфа)."""

    @abc.abstractmethod
    def desired_keys(self, rules: list[FirewallRule], default_drop_output: bool) -> set:
        """Канонический набор «эталонных» ключей правил (для сравнения с фактом)."""

    @abc.abstractmethod
    def parse_current(self, outputs: list[str]) -> set:
        """Распарсить вывод list_commands в набор ключей в том же каноне, что desired_keys."""

    @abc.abstractmethod
    def cleanup_commands(self) -> list[Command]:
        """Команды для полного снятия правил Aegis и возврата хоста в исходное состояние.

        Вызывается при остановке агента. Должна затрагивать только НАШИ правила
        (в группе Aegis / цепочках AEGIS_*) и не трогать чужие.
        """
