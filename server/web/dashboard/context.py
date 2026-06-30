"""Контекст-процессор: прокидывает роль пользователя во все шаблоны."""
from __future__ import annotations

from core.rbac import is_admin, role_of


def rbac(request):
    user = getattr(request, "user", None)
    if user is None:
        return {}
    return {
        "user_role": role_of(user),
        "is_admin": is_admin(user),
        "brand_name": "AEGIS",
    }
