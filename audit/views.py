from rest_framework import viewsets, permissions
from rest_framework.response import Response
from django.db.models import Q
from audit.models import AuditLog
from audit.serializers import AuditLogSerializer

class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for Automated Security and Data Audit Logs (/api/audit-logs/).
    Returns paginated response format: { total, page, limit, logs }.
    """
    queryset = AuditLog.objects.all().order_by('-created_at')
    serializer_class = AuditLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        table_filter = request.query_params.get('tableName') or request.query_params.get('table_name')
        if table_filter and table_filter.strip().upper() != 'ALL':
            queryset = queryset.filter(table_name__iexact=table_filter.strip())

        action_filter = request.query_params.get('action')
        if action_filter and action_filter.strip().upper() != 'ALL':
            queryset = queryset.filter(action__iexact=action_filter.strip())

        changed_by_filter = request.query_params.get('changedBy') or request.query_params.get('changed_by')
        if changed_by_filter and changed_by_filter.strip():
            queryset = queryset.filter(changed_by__icontains=changed_by_filter.strip())

        record_id_filter = request.query_params.get('recordId') or request.query_params.get('record_id')
        if record_id_filter and record_id_filter.strip():
            queryset = queryset.filter(record_id=record_id_filter.strip())

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
