"""Модели поверх таблиц, которыми владеет ingest/init.sql (managed=False).

Django их не создаёт и не мигрирует — только читает/пишет. Схема — deploy/postgres/init.sql.
"""
from __future__ import annotations

from django.db import models


class Profile(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(default="", blank=True)
    policy = models.JSONField(default=dict)
    version = models.CharField(max_length=64, default="v0")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = "profiles"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Machine(models.Model):
    agent_id = models.CharField(max_length=255, unique=True)
    hostname = models.CharField(max_length=255, default="", blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    os = models.CharField(max_length=64, default="", blank=True)
    arch = models.CharField(max_length=64, default="", blank=True)
    status = models.CharField(max_length=32, default="unknown")
    agent_version = models.CharField(max_length=64, default="", blank=True)
    config_version = models.CharField(max_length=64, default="", blank=True)
    last_seen = models.DateTimeField(null=True, blank=True)
    profile = models.ForeignKey(
        Profile, null=True, blank=True, on_delete=models.SET_NULL, db_column="profile_id"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "machines"
        ordering = ["hostname", "agent_id"]

    def __str__(self) -> str:
        return self.hostname or self.agent_id

    @property
    def is_online(self) -> bool:
        return self.status == "online"


class Event(models.Model):
    machine = models.ForeignKey(
        Machine, null=True, blank=True, on_delete=models.CASCADE, db_column="machine_id"
    )
    agent_id = models.CharField(max_length=255)
    type = models.CharField(max_length=64)
    severity = models.CharField(max_length=16, default="INFO")
    message = models.TextField(default="", blank=True)
    payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "events"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.type}/{self.severity}"


class AuditLog(models.Model):
    actor = models.CharField(max_length=255, default="", blank=True)
    action = models.CharField(max_length=255)
    target = models.CharField(max_length=255, default="", blank=True)
    payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "audit_log"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.actor}:{self.action}"
