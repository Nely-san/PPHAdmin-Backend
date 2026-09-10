from rest_framework import serializers
from payroll.models import PayrollRecord, PayrollItem, SalaryRateAdjustment
from users.models import Person

class PayrollItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayrollItem
        fields = ['id', 'item_type', 'description', 'amount']


class PayrollRecordSerializer(serializers.ModelSerializer):
    person_name = serializers.CharField(source='person.name', read_only=True)
    person_type = serializers.CharField(source='person.person_type', read_only=True)
    rate_type = serializers.CharField(source='person.rate_type', read_only=True)
    base_rate = serializers.DecimalField(source='person.base_rate', max_digits=10, decimal_places=2, read_only=True)
    company_name = serializers.CharField(source='person.company_name', read_only=True)
    department_name = serializers.CharField(source='person.department_name', read_only=True)
    items = PayrollItemSerializer(many=True, read_only=True)

    class Meta:
        model = PayrollRecord
        fields = [
            'id', 'person', 'person_name', 'person_type', 'rate_type', 'base_rate',
            'company_name', 'department_name',
            'cutoff_start', 'cutoff_end', 'gross_pay', 'total_deductions',
            'net_pay', 'status', 'items',
            'is_archived', 'archived_at', 'archived_by', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_archived', 'archived_at', 'archived_by']


class SalaryRateAdjustmentSerializer(serializers.ModelSerializer):
    person_name = serializers.CharField(source='person.name', read_only=True)
    person_type = serializers.CharField(source='person.person_type', read_only=True)
    adjusted_by_username = serializers.CharField(source='adjusted_by.username', read_only=True)

    class Meta:
        model = SalaryRateAdjustment
        fields = [
            'id', 'person', 'person_name', 'person_type',
            'old_rate', 'new_rate', 'old_rate_type', 'new_rate_type',
            'adjustment_type', 'reason', 'adjusted_by', 'adjusted_by_username',
            'effective_date', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'adjusted_by', 'created_at', 'updated_at']


class PayrollCalculateSerializer(serializers.Serializer):
    cutoff_start = serializers.DateField(required=True)
    cutoff_end = serializers.DateField(required=True)
    method = serializers.ChoiceField(choices=['OPTION_1', 'OPTION_2'], default='OPTION_1')
    person_ids = serializers.ListField(child=serializers.UUIDField(), required=False, default=list)
    department_id = serializers.UUIDField(required=False, allow_null=True)
    company_id = serializers.UUIDField(required=False, allow_null=True)
    include_government_deductions = serializers.BooleanField(required=False, default=True)
    include_tardiness = serializers.BooleanField(required=False, default=True)
    include_sss = serializers.BooleanField(required=False, default=True)
    include_philhealth = serializers.BooleanField(required=False, default=True)
    include_pagibig = serializers.BooleanField(required=False, default=True)


class PayrollLockSerializer(serializers.Serializer):
    cutoff_start = serializers.DateField(required=True)
    cutoff_end = serializers.DateField(required=True)


class BaseRateAdjustSerializer(serializers.Serializer):
    person_id = serializers.UUIDField(required=True)
    new_rate = serializers.DecimalField(max_digits=10, decimal_places=2, required=True)
    new_rate_type = serializers.ChoiceField(choices=['DAILY', 'MONTHLY', 'HOURLY'], default='DAILY')
    adjustment_type = serializers.ChoiceField(choices=['PROMOTION', 'REGULARIZATION', 'ANNUAL_INCREASE', 'MERIT', 'BULK_INCREMENT'], default='MERIT')
    reason = serializers.CharField(required=True, allow_blank=False)
    effective_date = serializers.DateField(required=True)


class BulkSalaryAdjustSerializer(serializers.Serializer):
    department_id = serializers.UUIDField(required=False, allow_null=True)
    company_id = serializers.UUIDField(required=False, allow_null=True)
    person_ids = serializers.ListField(child=serializers.UUIDField(), required=False, default=list)
    adjustment_type = serializers.ChoiceField(choices=['PERCENTAGE', 'FLAT_AMOUNT', 'TARGET_RATE'])
    adjustment_value = serializers.DecimalField(max_digits=10, decimal_places=2, required=True)
    reason = serializers.CharField(required=True, allow_blank=False)
    effective_date = serializers.DateField(required=True)
