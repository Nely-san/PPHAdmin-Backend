import uuid
from django.db import models
from settings.models import BaseModel

class BiometricImportBatch(BaseModel):
    """
    Biometric upload batch metadata and processing summary.
    """
    file_name = models.CharField(max_length=255)
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    imported_at = models.DateTimeField(auto_now_add=True)
    records_imported = models.IntegerField(default=0)
    anomalies_detected = models.IntegerField(default=0)
    newly_created_accounts_count = models.IntegerField(default=0)

    class Meta:
        db_table = 'biometric_import_batches'
        ordering = ['-imported_at']

    def __str__(self):
        return f"Batch {self.file_name} ({self.records_imported} records on {self.imported_at})"


class BiometricLog(models.Model):
    """
    Raw machine biometric punches.
    """
    LOG_TYPE_CHOICES = [
        ('CHECK_IN', 'Clock In'),
        ('CHECK_OUT', 'Clock Out'),
        ('BREAK_IN', 'Break Start'),
        ('BREAK_OUT', 'Break End'),
        ('OVERTIME_IN', 'Overtime In'),
        ('OVERTIME_OUT', 'Overtime Out'),
        ('UNKNOWN', 'Unknown Scan'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    person = models.ForeignKey('users.Person', on_delete=models.SET_NULL, null=True, blank=True, related_name='raw_logs')
    biometric_id = models.CharField(max_length=50, db_index=True)
    timestamp = models.DateTimeField(db_index=True)
    log_type = models.CharField(max_length=30, choices=LOG_TYPE_CHOICES, default='UNKNOWN')
    device_id = models.CharField(max_length=50, null=True, blank=True)
    batch = models.ForeignKey(BiometricImportBatch, on_delete=models.SET_NULL, null=True, blank=True, related_name='raw_logs')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'biometric_logs'
        indexes = [
            models.Index(fields=['biometric_id', 'timestamp']),
        ]

    def __str__(self):
        return f"Scan {self.biometric_id} at {self.timestamp} ({self.log_type})"


class AttendanceRecord(BaseModel):
    """
    Daily processed attendance timecard record per person per date.
    """
    STATUS_CHOICES = [
        ('PRESENT', 'Present'),
        ('ABSENT', 'Absent'),
        ('LATE', 'Late Arrival'),
        ('HALF_DAY', 'Half Day'),
        ('ON_LEAVE', 'On Leave'),
        ('BUSINESS_TRIP', 'Official Business (OB)'),
        ('HOLIDAY', 'Holiday'),
        ('REST_DAY', 'Rest Day'),
    ]

    person = models.ForeignKey('users.Person', on_delete=models.CASCADE, related_name='attendance_records')
    date = models.DateField(db_index=True)
    am_in = models.DateTimeField(null=True, blank=True)
    am_out = models.DateTimeField(null=True, blank=True)
    pm_in = models.DateTimeField(null=True, blank=True)
    pm_out = models.DateTimeField(null=True, blank=True)
    overtime_in = models.DateTimeField(null=True, blank=True)
    overtime_out = models.DateTimeField(null=True, blank=True)

    actual_hours = models.DecimalField(max_digits=6, decimal_places=2, default=0.00)
    required_hours = models.DecimalField(max_digits=6, decimal_places=2, default=8.00)
    tardiness_minutes = models.IntegerField(default=0)
    tardiness_count = models.IntegerField(default=0)
    early_leave_minutes = models.IntegerField(default=0)
    early_leave_count = models.IntegerField(default=0)
    overtime_regular_minutes = models.IntegerField(default=0)
    overtime_special_minutes = models.IntegerField(default=0)

    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='PRESENT')
    is_absent = models.BooleanField(default=False)
    is_leave = models.BooleanField(default=False)
    is_business_trip = models.BooleanField(default=False)
    is_abnormal = models.BooleanField(default=False)
    is_locked = models.BooleanField(default=False)
    is_field_ob = models.BooleanField(default=False)

    batch = models.ForeignKey(BiometricImportBatch, on_delete=models.SET_NULL, null=True, blank=True, related_name='attendance_records')
    payroll_record = models.ForeignKey('payroll.PayrollRecord', on_delete=models.SET_NULL, null=True, blank=True, related_name='attendance_records')
    memo = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'attendance_records'
        unique_together = ('person', 'date')
        ordering = ['-date', 'person']

    def __str__(self):
        return f"{self.person.name} on {self.date} - {self.status} ({self.actual_hours} hrs)"


class AbnormalClocking(BaseModel):
    """
    Attendance Exception and Anomaly Justification record.
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending HR Justification'),
        ('JUSTIFIED', 'Justified by Supervisor'),
        ('RESOLVED', 'Resolved'),
        ('EXCUSED', 'Excused Tardiness'),
        ('UNEXCUSED', 'Unexcused / Deduction Applied'),
    ]

    attendance_record = models.ForeignKey(AttendanceRecord, on_delete=models.SET_NULL, null=True, blank=True, related_name='abnormal_clockings')
    person = models.ForeignKey('users.Person', on_delete=models.CASCADE, related_name='abnormal_clockings')
    date = models.DateField(db_index=True)
    am_in = models.CharField(max_length=20, null=True, blank=True)
    am_out = models.CharField(max_length=20, null=True, blank=True)
    pm_in = models.CharField(max_length=20, null=True, blank=True)
    pm_out = models.CharField(max_length=20, null=True, blank=True)
    tardiness_minutes = models.IntegerField(default=0)
    early_leave_minutes = models.IntegerField(default=0)
    total_abnormal_minutes = models.IntegerField(default=0)
    reason = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='PENDING')

    justified_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='justified_clockings')
    justified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'abnormal_clockings'
        ordering = ['-date', 'status']

    def __str__(self):
        return f"Exception for {self.person.name} on {self.date} ({self.status})"


class AttendancePeriod(BaseModel):
    name = models.CharField(max_length=255)
    start_date = models.DateField()
    end_date = models.DateField()
    is_closed = models.BooleanField(default=False)

    class Meta:
        db_table = 'attendance_periods'
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.name} ({self.start_date} to {self.end_date})"


class AttendanceSummary(BaseModel):
    period = models.ForeignKey(AttendancePeriod, on_delete=models.CASCADE, related_name='summaries')
    person = models.ForeignKey('users.Person', on_delete=models.CASCADE, related_name='attendance_summaries')
    batch = models.ForeignKey(BiometricImportBatch, on_delete=models.SET_NULL, null=True, blank=True)

    required_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    actual_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    tardiness_count = models.IntegerField(default=0)
    tardiness_minutes = models.IntegerField(default=0)
    early_leave_count = models.IntegerField(default=0)
    early_leave_minutes = models.IntegerField(default=0)
    overtime_regular = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    overtime_special = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)

    required_days = models.IntegerField(default=0)
    actual_days = models.IntegerField(default=0)
    business_trip_days = models.IntegerField(default=0)
    absence_days = models.IntegerField(default=0)
    leave_days = models.IntegerField(default=0)

    bonus_pay_note = models.TextField(null=True, blank=True)
    pay_deduction = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    actual_pay = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    memo = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'attendance_summaries'
        unique_together = ('period', 'person')
        ordering = ['period', 'person']

    def __str__(self):
        return f"Summary {self.person.name} for {self.period.name}"
