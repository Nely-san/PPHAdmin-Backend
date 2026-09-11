from rest_framework import serializers
from leaves_ob.models import LeaveOBApplication

class LeaveOBApplicationSerializer(serializers.ModelSerializer):
    person_name = serializers.CharField(source='person.name', read_only=True)
    person_type = serializers.CharField(source='person.person_type', read_only=True)
    biometric_id = serializers.CharField(source='person.biometric_id', read_only=True)
    company_name = serializers.CharField(source='person.company_name', read_only=True)
    department_name = serializers.CharField(source='person.department_name', read_only=True)
    reviewed_by_username = serializers.CharField(source='reviewed_by.username', read_only=True)
    request_type_display = serializers.CharField(source='get_request_type_display', read_only=True)

    class Meta:
        model = LeaveOBApplication
        fields = [
            'id', 'person', 'person_name', 'person_type', 'biometric_id',
            'company_name', 'department_name',
            'request_type', 'request_type_display', 'start_date', 'end_date',
            'total_days', 'reason', 'location', 'status',
            'reviewed_by', 'reviewed_by_username', 'review_remarks', 'reviewed_at',
            'is_archived', 'archived_at', 'archived_by', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'reviewed_by', 'reviewed_at', 'created_at', 'updated_at',
            'is_archived', 'archived_at', 'archived_by'
        ]


class LeaveOBActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=['APPROVED', 'REJECTED'])
    remarks = serializers.CharField(required=False, allow_blank=True, default='')
