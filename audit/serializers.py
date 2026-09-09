from rest_framework import serializers
from audit.models import AuditLog

class AuditLogSerializer(serializers.ModelSerializer):
    tableName = serializers.CharField(source='table_name', read_only=True)
    recordId = serializers.CharField(source='record_id', allow_null=True, required=False, read_only=True)
    oldData = serializers.CharField(source='old_data', allow_null=True, required=False, read_only=True)
    newData = serializers.CharField(source='new_data', allow_null=True, required=False, read_only=True)
    changedBy = serializers.CharField(source='changed_by', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            'id', 'table_name', 'record_id', 'action', 'old_data', 'new_data', 'changed_by', 'created_at',
            'tableName', 'recordId', 'oldData', 'newData', 'changedBy', 'createdAt'
        ]
        read_only_fields = fields
