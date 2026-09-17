from datetime import datetime, date, time
from decimal import Decimal
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.utils import timezone
from django.db.models import Q

from biometrics_attendance.models import (
    BiometricImportBatch, BiometricLog, AttendanceRecord,
    AbnormalClocking, AttendancePeriod, AttendanceSummary
)
from biometrics_attendance.serializers import (
    BiometricImportBatchSerializer, BiometricLogSerializer, AttendanceRecordSerializer,
    AbnormalClockingSerializer, JustifyExceptionSerializer, FieldLogSerializer,
    AttendancePeriodSerializer, AttendanceSummarySerializer
)
from biometrics_attendance.engine import process_biometric_import
from users.models import Person

class BiometricImportViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for Biometric Import Batches and File Processing.
    """
    queryset = BiometricImportBatch.objects.all().order_by('-imported_at')
    serializer_class = BiometricImportBatchSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @action(detail=False, methods=['post'], url_path='upload')
    def upload_file(self, request):
        """
        Uploads and parses biometric timecard files (07Statistic.xls, .xlsx, .csv).
        """
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response(
                {"detail": "No file uploaded. Please upload a valid .xls, .xlsx, or .csv file."},
                status=status.HTTP_400_BAD_REQUEST
            )

        result = process_biometric_import(
            file_obj=file_obj,
            file_name=file_obj.name,
            user_identifier=request.user.username
        )

        if not result['success']:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)

        return Response(result, status=status.HTTP_200_OK)


class AttendanceRecordViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Querying and Updating Daily Attendance Records (/api/attendance/).
    """
    queryset = AttendanceRecord.objects.filter(is_archived=False).select_related('person', 'batch')
    serializer_class = AttendanceRecordSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        qs = super().get_queryset()
        person_id = self.request.query_params.get('person') or self.request.query_params.get('personId')
        if person_id:
            qs = qs.filter(person_id=person_id)

        biometric_id = self.request.query_params.get('biometricId') or self.request.query_params.get('biometric_id')
        if biometric_id:
            qs = qs.filter(person__biometric_id=biometric_id)

        start_date = self.request.query_params.get('startDate') or self.request.query_params.get('start_date')
        if start_date:
            qs = qs.filter(date__gte=start_date)

        end_date = self.request.query_params.get('endDate') or self.request.query_params.get('end_date')
        if end_date:
            qs = qs.filter(date__lte=end_date)

        date_val = self.request.query_params.get('date')
        if date_val:
            qs = qs.filter(date=date_val)

        status_val = self.request.query_params.get('status')
        if status_val and status_val.upper() != 'ALL':
            qs = qs.filter(status__iexact=status_val)

        person_type = self.request.query_params.get('personType') or self.request.query_params.get('person_type')
        if person_type and person_type.upper() != 'ALL':
            qs = qs.filter(person__person_type__iexact=person_type)

        search = self.request.query_params.get('search')
        if search and search.strip():
            q = search.strip()
            qs = qs.filter(
                Q(person__name__icontains=q) |
                Q(person__biometric_id__icontains=q) |
                Q(memo__icontains=q)
            )

        return qs

    @action(detail=False, methods=['post'], url_path='field-log')
    def field_log(self, request):
        """
        Submits manual field / official business punch for offsite employees.
        """
        serializer = FieldLogSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        person = Person.objects.filter(id=data['person_id'], is_archived=False).first()
        if not person:
            return Response({"detail": "Personnel record not found."}, status=status.HTTP_404_NOT_FOUND)

        log_date = data['date']
        am_in_t = data.get('am_in') or time(9, 0)
        pm_out_t = data.get('pm_out') or time(18, 0)
        dt_am_in = datetime.combine(log_date, am_in_t)
        dt_pm_out = datetime.combine(log_date, pm_out_t)

        worked_mins = max(0, int((dt_pm_out - dt_am_in).total_seconds() / 60) - 60)
        actual_hours = round(Decimal(worked_mins) / Decimal(60), 2)

        record, _ = AttendanceRecord.objects.update_or_create(
            person=person,
            date=log_date,
            defaults={
                'am_in': dt_am_in,
                'pm_out': dt_pm_out,
                'actual_hours': actual_hours,
                'required_hours': Decimal('8.00'),
                'status': 'BUSINESS_TRIP',
                'is_business_trip': True,
                'is_field_ob': True,
                'memo': f"Field OB Log at {data.get('location', 'Offsite')}. {data.get('reason', '')}".strip(),
                'is_archived': False
            }
        )
        return Response(AttendanceRecordSerializer(record).data, status=status.HTTP_201_CREATED)


class AbnormalClockingViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Anomaly Exceptions and Justifications (/api/attendance/exceptions/).
    """
    queryset = AbnormalClocking.objects.filter(is_archived=False).select_related('person', 'attendance_record', 'justified_by')
    serializer_class = AbnormalClockingSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        qs = super().get_queryset()
        status_filter = self.request.query_params.get('status')
        if status_filter and status_filter.upper() != 'ALL':
            qs = qs.filter(status__iexact=status_filter)

        person_id = self.request.query_params.get('person') or self.request.query_params.get('personId')
        if person_id:
            qs = qs.filter(person_id=person_id)

        start_date = self.request.query_params.get('startDate') or self.request.query_params.get('start_date')
        if start_date:
            qs = qs.filter(date__gte=start_date)

        end_date = self.request.query_params.get('endDate') or self.request.query_params.get('end_date')
        if end_date:
            qs = qs.filter(date__lte=end_date)

        return qs

    @action(detail=True, methods=['post'], url_path='justify')
    def justify(self, request, pk=None):
        """
        Supervisor / HR justification for tardiness or missing punch.
        """
        exception = self.get_object()
        serializer = JustifyExceptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        exception.status = serializer.validated_data['status']
        exception.reason = serializer.validated_data['reason']
        exception.justified_by = request.user
        exception.justified_at = timezone.now()
        exception.save()

        # Update linked AttendanceRecord if excused
        if exception.attendance_record and exception.status in ('EXCUSED', 'JUSTIFIED', 'RESOLVED'):
            att = exception.attendance_record
            att.is_abnormal = False
            att.memo = (att.memo or '') + f" [Justified by {request.user.username}: {exception.reason}]"
            att.save()

        return Response(AbnormalClockingSerializer(exception).data)


class AttendancePeriodViewSet(viewsets.ModelViewSet):
    queryset = AttendancePeriod.objects.filter(is_archived=False)
    serializer_class = AttendancePeriodSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None


class AttendanceSummaryViewSet(viewsets.ModelViewSet):
    queryset = AttendanceSummary.objects.filter(is_archived=False).select_related('period', 'person')
    serializer_class = AttendanceSummarySerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None
