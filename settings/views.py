from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from settings.models import SystemParameter
from settings.serializers import SystemParameterSerializer, RoleSerializer, PagePermissionSerializer
from users.models import Role, PagePermission

class RoleViewSet(viewsets.ModelViewSet):
    """
    CRUD ViewSet for Super Admin to manage dynamic roles & assign page permissions.
    """
    queryset = Role.objects.filter(is_archived=False)
    serializer_class = RoleSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

    def destroy(self, request, *args, **kwargs):
        role = self.get_object()
        if role.is_system_role or role.code == 'SUPER_ADMIN':
            return Response(
                {"detail": "System baseline roles (including SUPER_ADMIN) cannot be deleted."},
                status=status.HTTP_400_BAD_REQUEST
            )
        role.archive(user_identifier=request.user.username)
        return Response(status=status.HTTP_204_NO_CONTENT)


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
