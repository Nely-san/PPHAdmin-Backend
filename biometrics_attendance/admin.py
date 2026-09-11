from django.contrib import admin
from biometrics_attendance.models import (
    BiometricImportBatch, BiometricLog, AttendanceRecord,
    AbnormalClocking, AttendancePeriod, AttendanceSummary
)

@admin.register(BiometricImportBatch)
class BiometricImportBatchAdmin(admin.ModelAdmin):
    list_display = ('file_name', 'period_start', 'period_end', 'imported_at', 'records_imported', 'anomalies_detected')
    list_filter = ('imported_at',)
    search_fields = ('file_name',)

@admin.register(BiometricLog)
class BiometricLogAdmin(admin.ModelAdmin):
    list_display = ('person', 'biometric_id', 'timestamp', 'log_type', 'device_id')
    list_filter = ('log_type', 'timestamp')
    search_fields = ('biometric_id', 'person__name')

@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ('person', 'date', 'status', 'actual_hours', 'tardiness_minutes', 'is_abnormal', 'is_locked')
    list_filter = ('status', 'date', 'is_abnormal', 'is_locked')
    search_fields = ('person__name', 'person__biometric_id', 'memo')

@admin.register(AbnormalClocking)
class AbnormalClockingAdmin(admin.ModelAdmin):
    list_display = ('person', 'date', 'status', 'tardiness_minutes', 'early_leave_minutes', 'justified_by')
    list_filter = ('status', 'date')
    search_fields = ('person__name', 'reason')

@admin.register(AttendancePeriod)
class AttendancePeriodAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_date', 'end_date', 'is_closed')

@admin.register(AttendanceSummary)
class AttendanceSummaryAdmin(admin.ModelAdmin):
    list_display = ('period', 'person', 'actual_hours', 'tardiness_count', 'required_days', 'actual_days')
