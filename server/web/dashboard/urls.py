"""Маршруты веб-панели + аутентификация."""
from django.contrib.auth import views as auth_views
from django.urls import path

from dashboard import views

urlpatterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("machines/", views.MachineListView.as_view(), name="machines"),
    path("machines/<int:pk>/", views.MachineDetailView.as_view(), name="machine_detail"),
    path(
        "machines/<int:pk>/profile/",
        views.MachineAssignProfileView.as_view(),
        name="machine_assign_profile",
    ),
    path("events/", views.EventListView.as_view(), name="events"),
    path("profiles/", views.ProfileListView.as_view(), name="profiles"),
    path("profiles/<int:pk>/edit/", views.ProfileEditView.as_view(), name="profile_edit"),
    path("audit/", views.AuditLogView.as_view(), name="audit"),
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="dashboard/login.html", redirect_authenticated_user=True),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
]
