from django.urls import path, include
from rest_framework.routers import DefaultRouter
from scheduling.views import ShiftViewSet, ScheduleViewSet

router = DefaultRouter()
router.register(r'shifts', ShiftViewSet, basename='shift')
router.register(r'schedules', ScheduleViewSet, basename='schedule')

urlpatterns = [
    path('', include(router.urls)),
]
