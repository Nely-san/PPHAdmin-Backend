from rest_framework import serializers
from biometrics_attendance.models import (
    BiometricImportBatch, BiometricLog, AttendanceRecord,
    AbnormalClocking, AttendancePeriod, AttendanceSummary
)
from users.models import Person

class BiometricImportBatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = BiometricImportBatch
        fields = [
            'id', 'file_name', 'period_start', 'period_end',
            'imported_at', 'records_imported', 'anomalies_detected',
            'newly_created_accounts_count', 'created_at', 'updated_at'
        ]
        read_only_fields = fields


class BiometricLogSerializer(serializers.ModelSerializer):
    person_name = serializers.CharField(source='person.name', read_only=True)

    class Meta:
        model = BiometricLog
        fields = [
            'id', 'person', 'person_name', 'biometric_id', 'timestamp',
            'log_type', 'device_id', 'batch', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class AttendanceRecordSerializer(serializers.ModelSerializer):
    person_name = serializers.CharField(source='person.name', read_only=True)
    person_type = serializers.CharField(source='person.person_type', read_only=True)
    biometric_id = serializers.CharField(source='person.biometric_id', read_only=True)
    company_name = serializers.CharField(source='person.company_name', read_only=True)
    department_name = serializers.CharField(source='person.department_name', read_only=True)

    class Meta:
        model = AttendanceRecord
        fields = [
            'id', 'person', 'person_name', 'person_type', 'biometric_id',
            'company_name', 'department_name', 'date',
            'am_in', 'am_out', 'pm_in', 'pm_out', 'overtime_in', 'overtime_out',
            'actual_hours', 'required_hours', 'tardiness_minutes', 'tardiness_count',
            'early_leave_minutes', 'early_leave_count', 'overtime_regular_minutes',
            'overtime_special_minutes', 'status', 'is_absent', 'is_leave',
            'is_business_trip', 'is_abnormal', 'is_locked', 'is_field_ob',
            'batch', 'payroll_record', 'memo',
            'is_archived', 'archived_at', 'archived_by', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_archived', 'archived_at', 'archived_by']


class AbnormalClockingSerializer(serializers.ModelSerializer):
    person_name = serializers.CharField(source='person.name', read_only=True)
    person_type = serializers.CharField(source='person.person_type', read_only=True)
    biometric_id = serializers.CharField(source='person.biometric_id', read_only=True)
    justified_by_username = serializers.CharField(source='justified_by.username', read_only=True)

    class Meta:
        model = AbnormalClocking
        fields = [
            'id', 'attendance_record', 'person', 'person_name', 'person_type',
            'biometric_id', 'date', 'am_in', 'am_out', 'pm_in', 'pm_out',
            'tardiness_minutes', 'early_leave_minutes', 'total_abnormal_minutes',
            'reason', 'status', 'justified_by', 'justified_by_username',
            'justified_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class JustifyExceptionSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=['JUSTIFIED', 'RESOLVED', 'EXCUSED', 'UNEXCUSED'])
    reason = serializers.CharField(required=True, allow_blank=False)


class FieldLogSerializer(serializers.Serializer):
    person_id = serializers.UUIDField(required=True)
    date = serializers.DateField(required=True)
    am_in = serializers.TimeField(required=False, allow_null=True)
    pm_out = serializers.TimeField(required=False, allow_null=True)
    location = serializers.CharField(required=False, allow_blank=True, default='')
    reason = serializers.CharField(required=False, allow_blank=True, default='')


class AttendancePeriodSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendancePeriod
        fields = ['id', 'name', 'start_date', 'end_date', 'is_closed', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class AttendanceSummarySerializer(serializers.ModelSerializer):
    person_name = serializers.CharField(source='person.name', read_only=True)
    period_name = serializers.CharField(source='period.name', read_only=True)

    class Meta:
        model = AttendanceSummary
        fields = [
            'id', 'period', 'period_name', 'person', 'person_name', 'batch',
            'required_hours', 'actual_hours', 'tardiness_count', 'tardiness_minutes',
            'early_leave_count', 'early_leave_minutes', 'overtime_regular', 'overtime_special',
            'required_days', 'actual_days', 'business_trip_days', 'absence_days', 'leave_days',
            'bonus_pay_note', 'pay_deduction', 'actual_pay', 'memo', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
