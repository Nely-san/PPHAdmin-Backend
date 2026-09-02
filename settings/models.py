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


class ModuleAccess(BaseModel):
    """
    Dynamic RBAC Module Access and Navigation Configuration.
    Stored in database table: 'settings_module_access'
    """
    code = models.CharField(max_length=100, unique=True, db_index=True, help_text="Unique slug/key e.g. 'dashboard', 'user-management'")
    name = models.CharField(max_length=150, help_text="Human-readable module/page title")
    module = models.CharField(max_length=100, help_text="Category grouping e.g. 'SYSTEM', 'HR', 'ATTENDANCE', 'PAYROLL', 'SELF_SERVICE'")
    icon = models.CharField(max_length=100, default='fi fi-rr-apps', help_text="Flaticon / CSS icon class")
    path = models.CharField(max_length=150, null=True, blank=True, help_text="Frontend route path e.g. '/dashboard'")
    tag = models.CharField(max_length=50, null=True, blank=True, help_text="Optional UI pill tag e.g. 'Security', 'PHP'")
    is_primary = models.BooleanField(default=False, help_text="Pinned or primary highlighted item")
    display_order = models.IntegerField(default=0, help_text="Sequence index for sidebar navigation")
    allowed_actions = models.JSONField(default=list, blank=True, help_text="List of permitted CRUD actions e.g. ['view', 'add', 'edit', 'delete']")
    description = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'settings_module_access'
        ordering = ['display_order', 'id']

    def __str__(self):
        return f"[{self.module}] {self.name} ({self.code})"

