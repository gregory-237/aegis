"""REST API маршруты (DRF router)."""
from rest_framework.routers import DefaultRouter

from api.views import EventViewSet, MachineViewSet, ProfileViewSet

router = DefaultRouter()
router.register("machines", MachineViewSet, basename="machine")
router.register("events", EventViewSet, basename="event")
router.register("profiles", ProfileViewSet, basename="profile")

urlpatterns = router.urls
