from django.contrib import admin
from leaves_ob.models import LeaveOBApplication

@admin.register(LeaveOBApplication)
class LeaveOBApplicationAdmin(admin.ModelAdmin):
    list_display = ('person', 'request_type', 'start_date', 'end_date', 'total_days', 'status', 'reviewed_by')
    list_filter = ('request_type', 'status', 'start_date')
    search_fields = ('person__name', 'reason', 'location')
