"""DRF viewsets. Машины/события — только чтение; профили — чтение всем, запись admin."""
from __future__ import annotations

from rest_framework import viewsets

from api.permissions import IsAdminOrReadOnly
from api.serializers import EventSerializer, MachineSerializer, ProfileSerializer
from core.audit import log_action
from core.models import Event, Machine, Profile


class MachineViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Machine.objects.select_related("profile").all()
    serializer_class = MachineSerializer


class EventViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Event.objects.select_related("machine").all()
    serializer_class = EventSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        severity = self.request.query_params.get("severity")
        if severity:
            qs = qs.filter(severity=severity)
        return qs


class ProfileViewSet(viewsets.ModelViewSet):
    queryset = Profile.objects.all()
    serializer_class = ProfileSerializer
    permission_classes = [IsAdminOrReadOnly]

    def perform_create(self, serializer):
        obj = serializer.save()
        log_action(self.request.user.username, "profile.create", obj.name)

    def perform_update(self, serializer):
        obj = serializer.save()
        log_action(self.request.user.username, "profile.update", obj.name)

    def perform_destroy(self, instance):
        name = instance.name
        instance.delete()
        log_action(self.request.user.username, "profile.delete", name)
