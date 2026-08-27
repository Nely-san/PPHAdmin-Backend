from django.db import models
from core.models import BaseModel

class SystemParameter(BaseModel):
    """
    Dynamic system parameter store for runtime settings without code redeployments.
    Categories: GENERAL, ATTENDANCE, PAYROLL, SECURITY, BIOMETRICS.
    """
    CATEGORY_CHOICES = [
        ('GENERAL', 'General Configuration & Branding'),
        ('ATTENDANCE', 'Attendance, Grace Periods & Shifts'),
        ('PAYROLL', 'Payroll Formulas, Rules & Multipliers'),
        ('SECURITY', 'Security, Session Timeouts & Allowed Domains'),
        ('BIOMETRICS', 'Biometric Import Profiles & Hardware Mappings'),
    ]

    key = models.CharField(max_length=100, unique=True, db_index=True)
    value = models.TextField(help_text="Stores string, integer, or JSON dynamic configurations")
    description = models.TextField(null=True, blank=True)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='GENERAL')

    class Meta:
        db_table = 'system_parameters'
        ordering = ['category', 'key']

    def __str__(self):
        return f"[{self.category}] {self.key} = {self.value}"
