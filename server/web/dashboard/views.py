"""Представления веб-панели: дашборд, машины, события, профили, аудит."""
from __future__ import annotations

import json
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import ListView, TemplateView

from core.audit import log_action
from core.models import AuditLog, Event, Machine, Profile
from core.rbac import AdminRequiredMixin
from dashboard import metrics

# Машина считается офлайн, если не выходила на связь дольше этого срока.
OFFLINE_AFTER = timedelta(seconds=120)


def _mark_live(machines, cutoff):
    items = list(machines)
    for m in items:
        m.live = bool(m.last_seen and m.last_seen >= cutoff)
    return items


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        cutoff = timezone.now() - OFFLINE_AFTER
        machines = _mark_live(Machine.objects.all(), cutoff)
        online = sum(1 for m in machines if m.live)

        recent_events = list(Event.objects.select_related("machine")[:8])
        crit_24h = Event.objects.filter(
            severity="CRITICAL", created_at__gte=timezone.now() - timedelta(days=1)
        ).count()

        ctx.update(
            {
                "total_machines": len(machines),
                "online_machines": online,
                "offline_machines": len(machines) - online,
                "critical_24h": crit_24h,
                "machines": machines[:8],
                "recent_events": recent_events,
                "active": "dashboard",
            }
        )
        return ctx


class MachineListView(LoginRequiredMixin, ListView):
    template_name = "dashboard/machines.html"
    context_object_name = "machines"

    def get_queryset(self):
        cutoff = timezone.now() - OFFLINE_AFTER
        return _mark_live(Machine.objects.select_related("profile").all(), cutoff)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active"] = "machines"
        return ctx


class MachineDetailView(LoginRequiredMixin, View):
    template_name = "dashboard/machine_detail.html"

    def get(self, request, pk):
        machine = get_object_or_404(Machine.objects.select_related("profile"), pk=pk)
        machine.live = bool(
            machine.last_seen and machine.last_seen >= timezone.now() - OFFLINE_AFTER
        )
        ctx = {
            "machine": machine,
            "latest": metrics.latest_for_agent(machine.agent_id),
            "metric_labels": dict(metrics.LATEST_METRICS),
            "disks": metrics.disk_for_agent(machine.agent_id),
            "events": Event.objects.filter(machine=machine)[:20],
            "profiles": Profile.objects.all(),
            "active": "machines",
        }
        return render(request, self.template_name, ctx)


class MachineAssignProfileView(AdminRequiredMixin, View):
    """Назначение/снятие профиля машине (только admin). Пишется в аудит."""

    def post(self, request, pk):
        machine = get_object_or_404(Machine, pk=pk)
        profile_id = request.POST.get("profile_id") or None
        if profile_id:
            machine.profile = get_object_or_404(Profile, pk=profile_id)
        else:
            machine.profile = None
        machine.save()
        log_action(
            actor=request.user.username,
            action="machine.assign_profile",
            target=machine.agent_id,
            payload={"profile": machine.profile.name if machine.profile else None},
        )
        messages.success(request, "Профиль машины обновлён")
        return redirect(reverse("machine_detail", args=[pk]))


class EventListView(LoginRequiredMixin, ListView):
    template_name = "dashboard/events.html"
    context_object_name = "events"
    paginate_by = 50

    def get_queryset(self):
        qs = Event.objects.select_related("machine").all()
        severity = self.request.GET.get("severity")
        if severity in ("INFO", "WARNING", "CRITICAL"):
            qs = qs.filter(severity=severity)
        etype = self.request.GET.get("type")
        if etype:
            qs = qs.filter(type=etype)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active"] = "events"
        ctx["severity"] = self.request.GET.get("severity", "")
        return ctx


class ProfileListView(LoginRequiredMixin, ListView):
    template_name = "dashboard/profiles.html"
    context_object_name = "profiles"

    def get_queryset(self):
        return Profile.objects.all()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active"] = "profiles"
        return ctx


class ProfileEditView(AdminRequiredMixin, View):
    """Редактирование политики профиля (только admin). Изменения пишутся в аудит."""

    template_name = "dashboard/profile_edit.html"

    def get(self, request, pk):
        profile = get_object_or_404(Profile, pk=pk)
        return render(
            request,
            self.template_name,
            {
                "profile": profile,
                "policy_json": json.dumps(profile.policy, ensure_ascii=False, indent=2),
                "active": "profiles",
            },
        )

    def post(self, request, pk):
        profile = get_object_or_404(Profile, pk=pk)
        raw = request.POST.get("policy", "").strip()
        try:
            policy = json.loads(raw) if raw else {}
        except json.JSONDecodeError as e:
            messages.error(request, f"Некорректный JSON: {e}")
            return render(
                request,
                self.template_name,
                {"profile": profile, "policy_json": raw, "active": "profiles"},
            )

        profile.description = request.POST.get("description", profile.description)
        profile.policy = policy
        profile.save()
        log_action(
            actor=request.user.username,
            action="profile.update",
            target=profile.name,
            payload={"version": profile.version},
        )
        messages.success(request, f"Профиль «{profile.name}» сохранён")
        return redirect(reverse("profiles"))


class AuditLogView(AdminRequiredMixin, ListView):
    template_name = "dashboard/audit.html"
    context_object_name = "entries"
    paginate_by = 50

    def get_queryset(self):
        return AuditLog.objects.all()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active"] = "audit"
        return ctx
