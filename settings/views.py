from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from django.db.models import Q
from settings.models import SystemParameter, ModuleAccess, AuditLog
from settings.serializers import (
    SystemParameterSerializer, RoleSerializer, PagePermissionSerializer, 
    ModuleAccessSerializer, AuditLogSerializer
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

    def _apply_bulk_updates(self, data):
        """
        Parses and applies updates from various formats:
        - {"updates": [{"key": "k", "value": "v"}, ...]}
        - [{"key": "k", "value": "v"}, ...]
        - {"key1": "val1", "key2": "val2", ...}
        """
        if isinstance(data, dict) and "updates" in data and isinstance(data["updates"], list):
            items = data["updates"]
            for item in items:
                if isinstance(item, dict) and 'key' in item and 'value' in item:
                    param, _ = SystemParameter.objects.get_or_create(
                        key=item['key'],
                        defaults={'value': str(item['value'])}
                    )
                    param.value = str(item['value'])
                    param.save()
            return SystemParameter.objects.filter(is_archived=False)

        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and 'key' in item and 'value' in item:
                    param, _ = SystemParameter.objects.get_or_create(
                        key=item['key'],
                        defaults={'value': str(item['value'])}
                    )
                    param.value = str(item['value'])
                    param.save()
            return SystemParameter.objects.filter(is_archived=False)

        if isinstance(data, dict) and not ('key' in data and 'value' in data):
            for k, v in data.items():
                param, _ = SystemParameter.objects.get_or_create(
                    key=k,
                    defaults={'value': str(v)}
                )
                param.value = str(v)
                param.save()
            return SystemParameter.objects.filter(is_archived=False)

        return None

    def create(self, request, *args, **kwargs):
        """
        Supports single record creation and bulk dictionary/list update.
        """
        updated_qs = self._apply_bulk_updates(request.data)
        if updated_qs is not None:
            return Response(SystemParameterSerializer(updated_qs, many=True).data)

        return super().create(request, *args, **kwargs)

    @action(detail=False, methods=['put', 'patch', 'post'], url_path='bulk')
    def bulk_update(self, request, *args, **kwargs):
        """
        Handles bulk updates sent to /api/system-parameters/ or /api/system-parameters/bulk/
        """
        updated_qs = self._apply_bulk_updates(request.data)
        if updated_qs is not None:
            return Response(SystemParameterSerializer(updated_qs, many=True).data)
        return Response(
            {"detail": "Invalid payload format for bulk parameter update."},
            status=status.HTTP_400_BAD_REQUEST
        )


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for System Audit Logs (/api/audit-logs/).
    Returns paginated response format: { total, page, limit, logs }.
    """
    queryset = AuditLog.objects.all().order_by('-created_at')
    serializer_class = AuditLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        # Table Filter
        table_filter = request.query_params.get('tableName') or request.query_params.get('table_name')
        if table_filter and table_filter.strip().upper() != 'ALL':
            queryset = queryset.filter(table_name__iexact=table_filter.strip())

        # Action Filter
        action_filter = request.query_params.get('action')
        if action_filter and action_filter.strip().upper() != 'ALL':
            queryset = queryset.filter(action__iexact=action_filter.strip())

        # Changed By Filter
        changed_by_filter = request.query_params.get('changedBy') or request.query_params.get('changed_by')
        if changed_by_filter and changed_by_filter.strip():
            queryset = queryset.filter(changed_by__icontains=changed_by_filter.strip())

        # Search Query across fields
        search_query = request.query_params.get('search')
        if search_query and search_query.strip():
            q = search_query.strip()
            queryset = queryset.filter(
                Q(table_name__icontains=q) |
                Q(record_id__icontains=q) |
                Q(action__icontains=q) |
                Q(changed_by__icontains=q) |
                Q(old_data__icontains=q) |
                Q(new_data__icontains=q)
            )

        total = queryset.count()

        # Pagination
        try:
            page = int(request.query_params.get('page', 1))
            if page < 1:
                page = 1
        except (ValueError, TypeError):
            page = 1

        try:
            limit = int(request.query_params.get('limit', 15))
            if limit < 1:
                limit = 15
        except (ValueError, TypeError):
            limit = 15

        start = (page - 1) * limit
        end = start + limit
        paged_queryset = queryset[start:end]

        serializer = self.get_serializer(paged_queryset, many=True)
        return Response({
            'total': total,
            'page': page,
            'limit': limit,
            'logs': serializer.data
        })


