"""RBAC: две роли — admin (полный доступ) и observer (только чтение)."""
from __future__ import annotations

from django.contrib.auth.mixins import UserPassesTestMixin

ADMIN_GROUP = "admin"
OBSERVER_GROUP = "observer"


def is_admin(user) -> bool:
    if not user.is_authenticated:
        return False
    return user.is_superuser or user.groups.filter(name=ADMIN_GROUP).exists()


def role_of(user) -> str:
    if not user.is_authenticated:
        return "anonymous"
    return "admin" if is_admin(user) else "observer"


class AdminRequiredMixin(UserPassesTestMixin):
    """Доступ к изменяющим страницам — только админам."""

    def test_func(self) -> bool:
        return is_admin(self.request.user)
