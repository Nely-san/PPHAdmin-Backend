from django.utils import timezone
from rest_framework import serializers
from leaves_ob.models import LeaveOBApplication, OvertimeApplication
from users.models import Person

class LeaveOBApplicationSerializer(serializers.ModelSerializer):
    person = serializers.PrimaryKeyRelatedField(queryset=Person.objects.all(), required=False)
    person_id = serializers.PrimaryKeyRelatedField(
        queryset=Person.objects.all(),
        source='person',
        required=False,
        write_only=True
    )
    person_name = serializers.CharField(source='person.name', read_only=True)
    person_type = serializers.CharField(source='person.person_type', read_only=True)
    biometric_id = serializers.CharField(source='person.biometric_id', read_only=True)
    reviewed_by_username = serializers.CharField(source='reviewed_by.username', read_only=True)
    request_type_display = serializers.CharField(source='get_request_type_display', read_only=True)
    status = serializers.ChoiceField(choices=LeaveOBApplication.STATUS_CHOICES, required=False)

    class Meta:
        model = LeaveOBApplication
        fields = [
            'id', 'person', 'person_id', 'person_name', 'person_type', 'biometric_id',
            'request_type', 'request_type_display', 'start_date', 'end_date',
            'total_days', 'reason', 'location', 'status',
            'reviewed_by', 'reviewed_by_username', 'review_remarks', 'reviewed_at',
            'is_archived', 'archived_at', 'archived_by', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'reviewed_by', 'reviewed_at', 'created_at', 'updated_at',
            'is_archived', 'archived_at', 'archived_by'
        ]

    def create(self, validated_data):
        request = self.context.get('request')
        user = getattr(request, 'user', None) if request else None

        if 'person' not in validated_data and user and user.is_authenticated:
            person = getattr(user, 'person', None) or Person.objects.filter(user=user).first() or Person.objects.filter(name__iexact=user.username).first()
            if not person:
                person = Person.objects.create(
                    user=user,
                    name=user.username,
                    person_type='EMPLOYEE',
                    employment_mode='FULL_TIME',
                    rate_type='DAILY',
                    base_rate=0.00,
                    status='ACTIVE'
                )
            validated_data['person'] = person

        # Auto-compute total_days if not provided
        if not validated_data.get('total_days') and validated_data.get('start_date') and validated_data.get('end_date'):
            days = (validated_data['end_date'] - validated_data['start_date']).days + 1
            validated_data['total_days'] = max(1.0, float(days))

        if validated_data.get('status') == 'APPROVED' and user and user.is_authenticated:
            validated_data['reviewed_by'] = user
            if not validated_data.get('reviewed_at'):
                validated_data['reviewed_at'] = timezone.now()

        return super().create(validated_data)

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        ret['employeeId'] = ret.get('person')
        ret['employeeName'] = ret.get('person_name')
        ret['startDate'] = ret.get('start_date')
        ret['endDate'] = ret.get('end_date')
        ret['totalDays'] = float(ret.get('total_days') or 0)
        ret['daysCount'] = float(ret.get('total_days') or 0)
        ret['requestType'] = ret.get('request_type')
        return ret


class LeaveOBActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=['APPROVED', 'REJECTED'])
    remarks = serializers.CharField(required=False, allow_blank=True, default='')

    def validate(self, data):
        if data.get('action') == 'REJECTED' and not (data.get('remarks') or '').strip():
            raise serializers.ValidationError({'remarks': 'Remarks are required when rejecting an application.'})
        return data


class OvertimeApplicationSerializer(serializers.ModelSerializer):
    person = serializers.PrimaryKeyRelatedField(queryset=Person.objects.all(), required=False)
    person_id = serializers.PrimaryKeyRelatedField(
        queryset=Person.objects.all(),
        source='person',
        required=False,
        write_only=True
    )
    person_name = serializers.CharField(source='person.name', read_only=True)
    person_type = serializers.CharField(source='person.person_type', read_only=True)
    biometric_id = serializers.CharField(source='person.biometric_id', read_only=True)
    reviewed_by_username = serializers.CharField(source='reviewed_by.username', read_only=True)
    status = serializers.ChoiceField(choices=OvertimeApplication.STATUS_CHOICES, required=False)

    class Meta:
        model = OvertimeApplication
        fields = [
            'id', 'person', 'person_id', 'person_name', 'person_type', 'biometric_id',
            'date', 'hours', 'reason', 'status',
            'reviewed_by', 'reviewed_by_username', 'review_remarks', 'reviewed_at',
            'is_archived', 'archived_at', 'archived_by', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'reviewed_by', 'reviewed_at', 'created_at', 'updated_at',
            'is_archived', 'archived_at', 'archived_by'
        ]

    def create(self, validated_data):
        request = self.context.get('request')
        user = getattr(request, 'user', None) if request else None

        if 'person' not in validated_data and user and user.is_authenticated:
            person = getattr(user, 'person', None) or Person.objects.filter(user=user).first() or Person.objects.filter(name__iexact=user.username).first()
            if not person:
                person = Person.objects.create(
                    user=user,
                    name=user.username,
                    person_type='EMPLOYEE',
                    employment_mode='FULL_TIME',
                    rate_type='DAILY',
                    base_rate=0.00,
                    status='ACTIVE'
                )
            validated_data['person'] = person

        if validated_data.get('status') == 'APPROVED' and user and user.is_authenticated:
            validated_data['reviewed_by'] = user
            if not validated_data.get('reviewed_at'):
                validated_data['reviewed_at'] = timezone.now()

        return super().create(validated_data)

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        ret['employeeId'] = ret.get('person')
        ret['employeeName'] = ret.get('person_name')
        ret['startDate'] = ret.get('date')
        ret['endDate'] = ret.get('date')
        ret['hours'] = float(ret.get('hours') or 0)
        ret['totalDays'] = float(ret.get('hours') or 0)
        ret['daysCount'] = float(ret.get('hours') or 0)
        ret['requestType'] = 'OVERTIME'
        return ret


class OvertimeActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=['APPROVED', 'REJECTED'])
    remarks = serializers.CharField(required=False, allow_blank=True, default='')

    def validate(self, data):
        if data.get('action') == 'REJECTED' and not (data.get('remarks') or '').strip():
            raise serializers.ValidationError({'remarks': 'Remarks are required when rejecting an application.'})
        return data
