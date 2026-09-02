from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from settings.models import SystemParameter, ModuleAccess
from settings.serializers import (
    SystemParameterSerializer, RoleSerializer, PagePermissionSerializer, ModuleAccessSerializer
)
from users.models import Role, PagePermission

class RoleViewSet(viewsets.ModelViewSet):
    """
    CRUD ViewSet for Super Admin to manage dynamic roles & assign page permissions.
    Supports lookup by either database ID or role code (e.g. 'ADMIN', 'HR_MANAGER').
    """
    queryset = Role.objects.filter(is_archived=False)
    serializer_class = RoleSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None
    lookup_value_regex = '[^/]+'

    def get_object(self):
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        lookup_value = self.kwargs[lookup_url_kwarg]
        queryset = self.filter_queryset(self.get_queryset())
        
        obj = None
        if str(lookup_value).isdigit():
            obj = queryset.filter(pk=lookup_value).first()
        if not obj:
            obj = queryset.filter(code__iexact=str(lookup_value)).first()
        if not obj:
            obj = queryset.filter(name__iexact=str(lookup_value)).first()
            
        if not obj:
            from django.http import Http404
            raise Http404(f"Role '{lookup_value}' not found.")
            
        self.check_object_permissions(self.request, obj)
        return obj

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', True)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        role = self.get_object()
        if role.code == 'SUPER_ADMIN':
            return Response(
                {"detail": "The Super Admin role is permanent and cannot be deleted."},
                status=status.HTTP_400_BAD_REQUEST
            )
        from users.models import User
        active_users = User.objects.filter(role=role, is_archived=False)
        if active_users.exists():
            return Response(
                {"detail": f"Cannot delete role '{role.name or role.code}' because {active_users.count()} active user(s) are currently assigned to it. Please reassign them first."},
                status=status.HTTP_400_BAD_REQUEST
            )
        role.archive(user_identifier=request.user.username)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ModuleAccessViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Dynamic RBAC Module Access and Navigation Configuration (table: settings_module_access).
    """
    queryset = ModuleAccess.objects.filter(is_archived=False).order_by('display_order', 'id')
    serializer_class = ModuleAccessSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None


class PagePermissionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Catalog of all functional page permissions for the Super Admin assignment matrix.
    """
    queryset = PagePermission.objects.filter(is_archived=False)
    serializer_class = PagePermissionSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None


class SystemParameterViewSet(viewsets.ModelViewSet):
    """
    CRUD and bulk update for dynamic system parameters.
    """
    queryset = SystemParameter.objects.filter(is_archived=False)
    serializer_class = SystemParameterSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

    def create(self, request, *args, **kwargs):
        """
        Supports both single record creation and bulk dictionary update (as used by SystemSettingsPage).
        """
        # If payload is a dictionary of key-values { "attendance_grace_period": "15", ... }
        if isinstance(request.data, dict) and not ('key' in request.data and 'value' in request.data):
            updated_params = []
            for k, v in request.data.items():
                param, _ = SystemParameter.objects.get_or_create(
                    key=k,
                    defaults={'value': str(v)}
                )
                param.value = str(v)
                param.save()
                updated_params.append(param)
            return Response(SystemParameterSerializer(updated_params, many=True).data)

        return super().create(request, *args, **kwargs)

    @action(detail=False, methods=['put', 'post'], url_path='bulk')
    def bulk_update(self, request):
        data = request.data
        if isinstance(data, dict):
            for k, v in data.items():
                param, _ = SystemParameter.objects.get_or_create(
                    key=k,
                    defaults={'value': str(v)}
                )
                param.value = str(v)
                param.save()
        return Response({"detail": "Settings successfully updated."})
