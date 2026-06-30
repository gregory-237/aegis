"""Шаблонные фильтры Aegis."""
from __future__ import annotations

from django import template

register = template.Library()


@register.filter
def get_item(mapping, key):
    """Доступ к значению словаря по ключу из шаблона: {{ d|get_item:key }}."""
    if hasattr(mapping, "get"):
        return mapping.get(key)
    return None
