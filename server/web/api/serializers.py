"""DRF-сериализаторы для REST API."""
from __future__ import annotations

from rest_framework import serializers

from core.models import Event, Machine, Profile


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ["id", "name", "description", "policy", "version", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]


class MachineSerializer(serializers.ModelSerializer):
    profile_name = serializers.CharField(source="profile.name", read_only=True, default=None)

    class Meta:
        model = Machine
        fields = [
            "id", "agent_id", "hostname", "ip", "os", "arch", "status",
            "agent_version", "config_version", "last_seen", "profile", "profile_name",
        ]


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = [
            "id", "machine", "agent_id", "type", "severity", "message", "payload", "created_at"
        ]
