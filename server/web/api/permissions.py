"""Права DRF: запись — только admin, чтение — любой аутентифицированный (RBAC)."""
from __future__ import annotations

from rest_framework.permissions import SAFE_METHODS, BasePermission

from core.rbac import is_admin


class IsAdminOrReadOnly(BasePermission):
    def has_permission(self, request, view) -> bool:
        if request.method in SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        return is_admin(request.user)
