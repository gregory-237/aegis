"""Регистрация моделей в Django admin (управление профилями/машинами вручную)."""
from __future__ import annotations

from django.contrib import admin

from core.models import AuditLog, Event, Machine, Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("name", "version", "description", "updated_at")
    search_fields = ("name",)


@admin.register(Machine)
class MachineAdmin(admin.ModelAdmin):
    list_display = ("hostname", "agent_id", "os", "status", "profile", "last_seen")
    list_filter = ("status", "os")
    search_fields = ("hostname", "agent_id")


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "agent_id", "type", "severity", "message")
    list_filter = ("severity", "type")
    search_fields = ("agent_id", "message")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor", "action", "target")
    search_fields = ("actor", "action", "target")
