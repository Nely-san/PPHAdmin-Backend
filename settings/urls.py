from django.urls import path, include
from rest_framework.routers import DefaultRouter
from settings.views import SystemParameterViewSet

router = DefaultRouter()
router.register(r'system-parameters', SystemParameterViewSet, basename='system-parameters')
router.register(r'settings', SystemParameterViewSet, basename='settings')

urlpatterns = [
    path('', include(router.urls)),
]
