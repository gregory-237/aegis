"""Создаёт группы admin/observer и (по env) стартовых пользователей.

Неинтерактивно — удобно в Docker/CI:
  AEGIS_ADMIN_USER=admin AEGIS_ADMIN_PASSWORD=secret \
  AEGIS_OBSERVER_USER=viewer AEGIS_OBSERVER_PASSWORD=secret \
  python manage.py bootstrap_rbac
"""
from __future__ import annotations

import os

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand

from core.rbac import ADMIN_GROUP, OBSERVER_GROUP


class Command(BaseCommand):
    help = "Создать роли admin/observer и стартовых пользователей из env"

    def handle(self, *args, **options):
        admin_group, _ = Group.objects.get_or_create(name=ADMIN_GROUP)
        observer_group, _ = Group.objects.get_or_create(name=OBSERVER_GROUP)
        self.stdout.write(self.style.SUCCESS("группы admin/observer готовы"))

        User = get_user_model()
        self._ensure_user(
            User, admin_group, "AEGIS_ADMIN_USER", "AEGIS_ADMIN_PASSWORD", staff=True, superuser=True
        )
        self._ensure_user(
            User, observer_group, "AEGIS_OBSERVER_USER", "AEGIS_OBSERVER_PASSWORD",
            staff=False, superuser=False,
        )

    def _ensure_user(self, User, group, user_env, pass_env, staff, superuser):
        username = os.environ.get(user_env)
        password = os.environ.get(pass_env)
        if not username or not password:
            return
        user, created = User.objects.get_or_create(username=username)
        user.set_password(password)
        user.is_staff = staff
        user.is_superuser = superuser
        user.save()
        user.groups.set([group])
        verb = "создан" if created else "обновлён"
        self.stdout.write(self.style.SUCCESS(f"пользователь {username} ({group.name}) {verb}"))
