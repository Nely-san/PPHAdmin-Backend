from datetime import timedelta
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.db.models import Q
from scheduling.models import Shift, Schedule
from scheduling.serializers import (
    ShiftSerializer, ScheduleSerializer, BatchScheduleAssignSerializer
)
from users.models import Person

class ShiftViewSet(viewsets.ModelViewSet):
    """
    CRUD ViewSet for Shift Templates.
    Supports soft-delete archiving and templates initialization.
    """
    queryset = Shift.objects.filter(is_archived=False)
    serializer_class = ShiftSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

    def destroy(self, request, *args, **kwargs):
        shift = self.get_object()
        shift.archive(user_identifier=request.user.username)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['post'], url_path='seed-defaults')
    def seed_defaults(self, request):
        """Seed default baseline shift templates if none exist."""
        defaults = [
            {'code': 'DAY', 'name': 'Day Shift (09:00 - 18:00)', 'start_time': '09:00', 'end_time': '18:00', 'break_start_time': '12:00', 'break_end_time': '13:00', 'work_hours': 8.00, 'grace_period_mins': 10},
            {'code': 'NIGHT', 'name': 'Night Shift (22:00 - 07:00)', 'start_time': '22:00', 'end_time': '07:00', 'break_start_time': '02:00', 'break_end_time': '03:00', 'work_hours': 8.00, 'grace_period_mins': 10},
            {'code': 'MID', 'name': 'Mid Shift (13:00 - 22:00)', 'start_time': '13:00', 'end_time': '22:00', 'break_start_time': '17:00', 'break_end_time': '18:00', 'work_hours': 8.00, 'grace_period_mins': 10},
            {'code': 'OJT_FLEX', 'name': 'OJT Flexible Schedule', 'start_time': '08:00', 'end_time': '17:00', 'break_start_time': '12:00', 'break_end_time': '13:00', 'work_hours': 8.00, 'grace_period_mins': 15, 'is_flexible': True},
            {'code': 'FIELD_OB', 'name': 'Official Business / Field Trip', 'start_time': '09:00', 'end_time': '18:00', 'work_hours': 8.00, 'grace_period_mins': 60, 'is_field_ob': True},
        ]
        created_count = 0
        for item in defaults:
            shift, created = Shift.objects.get_or_create(code=item['code'], defaults=item)
            if created:
                created_count += 1
        return Response({
            'message': f'Default shifts seeded ({created_count} new shifts created).',
            'shifts': ShiftSerializer(Shift.objects.filter(is_archived=False), many=True).data
        })


class ScheduleViewSet(viewsets.ModelViewSet):
    """
    CRUD and Batch assignment ViewSet for Schedules and Rosters.
    """
    queryset = Schedule.objects.filter(is_archived=False).select_related('person', 'shift')
    serializer_class = ScheduleSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        qs = super().get_queryset()
        person_id = self.request.query_params.get('person') or self.request.query_params.get('personId')
        if person_id:
            qs = qs.filter(person_id=person_id)

        start_date = self.request.query_params.get('startDate') or self.request.query_params.get('start_date')
        if start_date:
            qs = qs.filter(date__gte=start_date)

        end_date = self.request.query_params.get('endDate') or self.request.query_params.get('end_date')
        if end_date:
            qs = qs.filter(date__lte=end_date)

        schedule_type = self.request.query_params.get('scheduleType') or self.request.query_params.get('schedule_type')
        if schedule_type:
            qs = qs.filter(schedule_type=schedule_type)

        company_id = self.request.query_params.get('companyId')
        if company_id:
            qs = qs.filter(person__company_id=company_id)

        department_id = self.request.query_params.get('departmentId')
        if department_id:
            qs = qs.filter(person__department_id=department_id)

        return qs

    @action(detail=False, methods=['post'], url_path='batch-assign')
    def batch_assign(self, request):
        """
        Assigns shifts and rosters to multiple personnel over a date span.
        """
        serializer = BatchScheduleAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        person_ids = data['person_ids']
        start_date = data['start_date']
        end_date = data['end_date']
        shift_id = data.get('shift_id')
        schedule_type = data['schedule_type']
        weekdays = data.get('weekdays', [])
        note = data.get('note', '')

        if start_date > end_date:
            return Response(
                {"detail": "start_date must be less than or equal to end_date."},
                status=status.HTTP_400_BAD_REQUEST
            )

        shift = None
        if shift_id:
            shift = Shift.objects.filter(id=shift_id, is_archived=False).first()
            if not shift:
                return Response(
                    {"detail": f"Shift with id {shift_id} not found."},
                    status=status.HTTP_404_NOT_FOUND
                )

        persons = Person.objects.filter(id__in=person_ids, is_archived=False)
        if not persons.exists():
            return Response(
                {"detail": "No valid active personnel found for the given IDs."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Generate list of dates
        cur_date = start_date
        assigned_count = 0

        with transaction.atomic():
            while cur_date <= end_date:
                # If weekdays filter is provided, check if cur_date matches weekday
                # In Python date.weekday(): 0=Mon, 6=Sun
                if not weekdays or cur_date.weekday() in weekdays:
                    for person in persons:
                        Schedule.objects.update_or_create(
                            person=person,
                            date=cur_date,
                            defaults={
                                'shift': shift,
                                'schedule_type': schedule_type,
                                'note': note,
                                'is_archived': False
                            }
                        )
                        assigned_count += 1
                cur_date += timedelta(days=1)

        return Response({
            'success': True,
            'message': f'Successfully assigned {assigned_count} schedule entries across {persons.count()} personnel.',
            'assigned_count': assigned_count,
            'person_count': persons.count()
        })
