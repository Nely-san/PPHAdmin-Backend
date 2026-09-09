from rest_framework import serializers
from scheduling.models import Shift, Schedule
from users.models import Person

class ShiftSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shift
        fields = [
            'id', 'code', 'name', 'start_time', 'end_time',
            'break_start_time', 'break_end_time', 'work_hours',
            'grace_period_mins', 'is_flexible', 'is_field_ob',
            'is_archived', 'archived_at', 'archived_by', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_archived', 'archived_at', 'archived_by']


class ScheduleSerializer(serializers.ModelSerializer):
    person_name = serializers.CharField(source='person.name', read_only=True)
    person_type = serializers.CharField(source='person.person_type', read_only=True)
    biometric_id = serializers.CharField(source='person.biometric_id', read_only=True)
    company_name = serializers.CharField(source='person.company_name', read_only=True)
    department_name = serializers.CharField(source='person.department_name', read_only=True)
    shift_code = serializers.CharField(source='shift.code', read_only=True)
    shift_name = serializers.CharField(source='shift.name', read_only=True)

    class Meta:
        model = Schedule
        fields = [
            'id', 'person', 'person_name', 'person_type', 'biometric_id',
            'company_name', 'department_name', 'shift', 'shift_code', 'shift_name',
            'date', 'schedule_type', 'weekdays', 'note',
            'is_archived', 'archived_at', 'archived_by', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_archived', 'archived_at', 'archived_by']


class BatchScheduleAssignSerializer(serializers.Serializer):
    person_ids = serializers.ListField(
        child=serializers.UUIDField(),
        allow_empty=False,
        help_text="List of Person UUIDs"
    )
    start_date = serializers.DateField(required=True)
    end_date = serializers.DateField(required=True)
    shift_id = serializers.UUIDField(required=False, allow_null=True)
    schedule_type = serializers.ChoiceField(
        choices=Schedule.SCHEDULE_TYPE_CHOICES,
        default='REGULAR'
    )
    weekdays = serializers.ListField(
        child=serializers.IntegerField(min_value=0, max_value=6),
        required=False,
        default=list,
        help_text="Optional: List of weekday numbers 0=Mon, 1=Tue, ..., 6=Sun to apply this schedule to"
    )
    note = serializers.CharField(required=False, allow_blank=True, default='')
