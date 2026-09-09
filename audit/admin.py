from django.contrib import admin
from audit.models import AuditLog

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('action', 'table_name', 'record_id', 'changed_by', 'created_at')
    list_filter = ('action', 'table_name', 'created_at')
    search_fields = ('table_name', 'record_id', 'changed_by', 'old_data', 'new_data')
    readonly_fields = ('id', 'table_name', 'record_id', 'action', 'old_data', 'new_data', 'changed_by', 'created_at')
