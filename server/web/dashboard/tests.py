"""Тесты RBAC и шаблонного фильтра. Не затрагивают managed=False таблицы."""
from __future__ import annotations

from django.contrib.auth.models import Group, User
from django.test import TestCase

from core.rbac import is_admin, role_of
from dashboard.templatetags.aegis_extras import get_item


class RbacTests(TestCase):
    def setUp(self):
        Group.objects.get_or_create(name="admin")
        Group.objects.get_or_create(name="observer")

    def test_admin_group_user_is_admin(self):
        u = User.objects.create_user("a", password="x")
        u.groups.add(Group.objects.get(name="admin"))
        self.assertTrue(is_admin(u))
        self.assertEqual(role_of(u), "admin")

    def test_observer_is_not_admin(self):
        u = User.objects.create_user("o", password="x")
        u.groups.add(Group.objects.get(name="observer"))
        self.assertFalse(is_admin(u))
        self.assertEqual(role_of(u), "observer")

    def test_superuser_is_admin(self):
        u = User.objects.create_superuser("s", password="x")
        self.assertTrue(is_admin(u))


class FilterTests(TestCase):
    def test_get_item(self):
        self.assertEqual(get_item({"a": 1}, "a"), 1)
        self.assertIsNone(get_item({"a": 1}, "b"))
        self.assertIsNone(get_item("not-a-dict", "x"))
