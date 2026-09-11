from django.db import models
from settings.models import BaseModel

class LeaveOBApplication(BaseModel):
    """
    Leave of Absence (VL, SL, EL) and Official Business (OB) Applications.
    """
    REQUEST_TYPE_CHOICES = [
        ('VACATION_LEAVE', 'Vacation Leave (VL)'),
        ('SICK_LEAVE', 'Sick Leave (SL)'),
        ('EMERGENCY_LEAVE', 'Emergency Leave (EL)'),
        ('OFFICIAL_BUSINESS', 'Official Business Trip (OB)'),
    ]
    STATUS_CHOICES = [
        ('PENDING', 'Pending HR Review'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('WITHDRAWN', 'Withdrawn by Employee'),
    ]

    person = models.ForeignKey('users.Person', on_delete=models.CASCADE, related_name='leave_applications')
    request_type = models.CharField(max_length=30, choices=REQUEST_TYPE_CHOICES)
    start_date = models.DateField(db_index=True)
    end_date = models.DateField(db_index=True)
    total_days = models.DecimalField(max_digits=4, decimal_places=1, default=1.0)
    reason = models.TextField()
    location = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', db_index=True)

    reviewed_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_leaves')
    review_remarks = models.TextField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'leave_ob_applications'
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.person.name} - {self.get_request_type_display()} ({self.start_date} to {self.end_date}) [{self.status}]"
