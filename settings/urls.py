from django.urls import path, include
from rest_framework.routers import DefaultRouter
from settings.views import (
    SystemParameterViewSet, RoleViewSet, PagePermissionViewSet, ModuleAccessViewSet
)

router = DefaultRouter()
router.register(r'system-parameters', SystemParameterViewSet, basename='system-parameters')
router.register(r'settings', SystemParameterViewSet, basename='settings')
router.register(r'roles', RoleViewSet, basename='roles')
router.register(r'module-access', ModuleAccessViewSet, basename='module-access')
router.register(r'permissions', PagePermissionViewSet, basename='permissions')

urlpatterns = [
    path('', include(router.urls)),
]

