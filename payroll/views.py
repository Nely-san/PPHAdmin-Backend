from decimal import Decimal
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.db.models import Q

from payroll.models import PayrollRecord, PayrollItem, SalaryRateAdjustment
from payroll.serializers import (
    PayrollRecordSerializer, SalaryRateAdjustmentSerializer,
    PayrollCalculateSerializer, PayrollLockSerializer,
    BaseRateAdjustSerializer, BulkSalaryAdjustSerializer
)
from payroll.engine import run_cutoff_payroll_batch, lock_cutoff_payroll
from users.models import Person

class PayrollRecordViewSet(viewsets.ModelViewSet):
    """
    CRUD and Batch Execution ViewSet for Cutoff Payroll Records (/api/payroll/).
    """
    queryset = PayrollRecord.objects.filter(is_archived=False).select_related('person').prefetch_related('items')
    serializer_class = PayrollRecordSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        qs = super().get_queryset()
        person_id = self.request.query_params.get('person') or self.request.query_params.get('personId')
        if person_id:
            qs = qs.filter(person_id=person_id)

        cutoff_start = self.request.query_params.get('cutoffStart') or self.request.query_params.get('cutoff_start')
        if cutoff_start:
            qs = qs.filter(cutoff_start=cutoff_start)

        cutoff_end = self.request.query_params.get('cutoffEnd') or self.request.query_params.get('cutoff_end')
        if cutoff_end:
            qs = qs.filter(cutoff_end=cutoff_end)

        status_val = self.request.query_params.get('status')
        if status_val and status_val.upper() != 'ALL':
            qs = qs.filter(status__iexact=status_val)

        company_id = self.request.query_params.get('companyId')
        if company_id:
            qs = qs.filter(person__company_id=company_id)

        department_id = self.request.query_params.get('departmentId')
        if department_id:
            qs = qs.filter(person__department_id=department_id)

        return qs

    @action(detail=False, methods=['post'], url_path='calculate')
    def calculate_cutoff(self, request):
        """
        Executes batch payroll generation for a cutoff date range.
        """
        serializer = PayrollCalculateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        records = run_cutoff_payroll_batch(
            cutoff_start=data['cutoff_start'],
            cutoff_end=data['cutoff_end'],
            method=data.get('method', 'OPTION_1'),
            person_ids=data.get('person_ids'),
            department_id=data.get('department_id'),
            company_id=data.get('company_id'),
            include_government_deductions=data.get('include_government_deductions', True),
            include_tardiness=data.get('include_tardiness', True),
            include_sss=data.get('include_sss', True),
            include_philhealth=data.get('include_philhealth', True),
            include_pagibig=data.get('include_pagibig', True)
        )

        return Response({
            'success': True,
            'message': f"Calculated payroll draft for {len(records)} active personnel.",
            'count': len(records),
            'records': PayrollRecordSerializer(records, many=True).data
        })

    @action(detail=False, methods=['post'], url_path='lock')
    def lock_cutoff(self, request):
        """
        Finalizes and locks cutoff records and freezes underlying attendance timecards.
        """
        serializer = PayrollLockSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        count = lock_cutoff_payroll(
            cutoff_start=data['cutoff_start'],
            cutoff_end=data['cutoff_end']
        )

        return Response({
            'success': True,
            'message': f"Successfully locked and frozen {count} payroll cutoff records.",
            'locked_count': count
        })


class SalaryRateAdjustmentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Viewing and Applying Base Rate Adjustments (/api/payroll/rate-adjustments/).
    """
    queryset = SalaryRateAdjustment.objects.filter(is_archived=False).select_related('person', 'adjusted_by')
    serializer_class = SalaryRateAdjustmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        qs = super().get_queryset()
        person_id = self.request.query_params.get('person') or self.request.query_params.get('personId')
        if person_id:
            qs = qs.filter(person_id=person_id)
        return qs

    @action(detail=False, methods=['post'], url_path='adjust')
    def adjust_single_rate(self, request):
        """
        Adjusts base rate for a single employee with reason and audit record.
        """
        serializer = BaseRateAdjustSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        person = Person.objects.filter(id=data['person_id'], is_archived=False).first()
        if not person:
            return Response({"detail": "Personnel record not found."}, status=status.HTTP_404_NOT_FOUND)

        old_rate = person.base_rate
        old_rate_type = person.rate_type

        with transaction.atomic():
            person.base_rate = data['new_rate']
            person.rate_type = data['new_rate_type']
            person.save(update_fields=['base_rate', 'rate_type'])

            adjustment = SalaryRateAdjustment.objects.create(
                person=person,
                old_rate=old_rate,
                new_rate=data['new_rate'],
                old_rate_type=old_rate_type,
                new_rate_type=data['new_rate_type'],
                adjustment_type=data['adjustment_type'],
                reason=data['reason'],
                adjusted_by=request.user,
                effective_date=data['effective_date']
            )

        return Response(SalaryRateAdjustmentSerializer(adjustment).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='bulk-adjust')
    def bulk_adjust_rates(self, request):
        """
        Applies department-wide or filtered salary increases.
        """
        serializer = BulkSalaryAdjustSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        persons = Person.objects.filter(is_archived=False, status='ACTIVE')
        if data.get('person_ids'):
            persons = persons.filter(id__in=data['person_ids'])
        if data.get('department_id'):
            persons = persons.filter(department_id=data['department_id'])
        if data.get('company_id'):
            persons = persons.filter(company_id=data['company_id'])

        adj_type = data['adjustment_type']
        adj_val = data['adjustment_value']
        reason = data['reason']
        eff_date = data['effective_date']

        created_adjustments = []
        with transaction.atomic():
            for p in persons:
                old_rate = p.base_rate or Decimal('0.00')
                new_rate = old_rate

                if adj_type == 'PERCENTAGE':
                    new_rate = old_rate * (Decimal('1.00') + (adj_val / Decimal('100.00')))
                elif adj_type == 'FLAT_AMOUNT':
                    new_rate = old_rate + adj_val
                elif adj_type == 'TARGET_RATE':
                    new_rate = adj_val

                new_rate = max(Decimal('0.00'), round(new_rate, 2))
                p.base_rate = new_rate
                p.save(update_fields=['base_rate'])

                adj = SalaryRateAdjustment.objects.create(
                    person=p,
                    old_rate=old_rate,
                    new_rate=new_rate,
                    old_rate_type=p.rate_type,
                    new_rate_type=p.rate_type,
                    adjustment_type='BULK_INCREMENT',
                    reason=reason,
                    adjusted_by=request.user,
                    effective_date=eff_date
                )
                created_adjustments.append(adj)

        return Response({
            'success': True,
            'message': f"Successfully applied bulk base rate adjustment across {len(created_adjustments)} personnel.",
            'count': len(created_adjustments),
            'adjustments': SalaryRateAdjustmentSerializer(created_adjustments, many=True).data
        })
