from django.db import models
from settings.models import BaseModel

class Shift(BaseModel):
    """
    Standard Shift Schedule Templates and Policies.
    """
    code = models.CharField(max_length=50, unique=True, db_index=True)
    name = models.CharField(max_length=255)
    start_time = models.CharField(max_length=10, help_text="e.g. '09:00'")
    end_time = models.CharField(max_length=10, help_text="e.g. '18:00'")
    break_start_time = models.CharField(max_length=10, null=True, blank=True, help_text="e.g. '12:00'")
    break_end_time = models.CharField(max_length=10, null=True, blank=True, help_text="e.g. '13:00'")
    work_hours = models.DecimalField(max_digits=4, decimal_places=2, default=8.00)
    grace_period_mins = models.IntegerField(default=10)
    is_flexible = models.BooleanField(default=False)
    is_field_ob = models.BooleanField(default=False)

    class Meta:
        db_table = 'shifts'
        ordering = ['code']

    def __str__(self):
        return f"{self.name} ({self.code}: {self.start_time} - {self.end_time})"


class Schedule(BaseModel):
    """
    Personnel Shift and Roster Assignment by Date.
    """
    SCHEDULE_TYPE_CHOICES = [
        ('REGULAR', 'Regular Work Day'),
        ('REST_DAY', 'Rest Day'),
        ('HOLIDAY', 'Holiday'),
        ('LEAVE', 'Official Leave'),
        ('BUSINESS_TRIP', 'Official Business Trip (OB)'),
    ]

    person = models.ForeignKey('users.Person', on_delete=models.CASCADE, related_name='schedules')
    shift = models.ForeignKey(Shift, on_delete=models.SET_NULL, null=True, blank=True, related_name='schedules')
    date = models.DateField(db_index=True)
    schedule_type = models.CharField(max_length=50, choices=SCHEDULE_TYPE_CHOICES, default='REGULAR')
    weekdays = models.JSONField(default=list, blank=True)
    note = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'schedules'
        unique_together = ('person', 'date')
        ordering = ['date', 'person']

    def __str__(self):
        return f"{self.person.name} on {self.date} - {self.schedule_type}"
