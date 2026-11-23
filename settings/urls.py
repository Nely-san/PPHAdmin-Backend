from django.urls import path, include
from rest_framework.routers import DefaultRouter
from settings.views import (
    RoleViewSet, PagePermissionViewSet, ModuleAccessViewSet, AuditLogViewSet
)

router = DefaultRouter()
router.register(r'roles', RoleViewSet, basename='roles')
router.register(r'module-access', ModuleAccessViewSet, basename='module-access')
router.register(r'permissions', PagePermissionViewSet, basename='permissions')
router.register(r'audit-logs', AuditLogViewSet, basename='audit-logs')

urlpatterns = [
    path('audit-logs', AuditLogViewSet.as_view({'get': 'list'}), name='audit-logs-no-slash'),
    path('audit-logs/', AuditLogViewSet.as_view({'get': 'list'}), name='audit-logs-root'),
    path('', include(router.urls)),
]


