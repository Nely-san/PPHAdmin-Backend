from django.contrib import admin
from scheduling.models import Shift, Schedule

@admin.register(Shift)
class ShiftAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'start_time', 'end_time', 'work_hours', 'grace_period_mins', 'is_flexible', 'is_field_ob', 'is_archived')
    list_filter = ('is_flexible', 'is_field_ob', 'is_archived')
    search_fields = ('code', 'name')

@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = ('person', 'date', 'shift', 'schedule_type', 'is_archived')
    list_filter = ('schedule_type', 'date', 'is_archived')
    search_fields = ('person__name', 'note')
