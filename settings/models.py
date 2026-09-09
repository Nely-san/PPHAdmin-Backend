import uuid
from django.db import models
from django.utils import timezone

class BaseModel(models.Model):
    """
    Abstract base model providing UUID primary keys, audit timestamps,
    and soft-delete archiving lifecycle fields (Zero Hard-Delete Policy).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_archived = models.BooleanField(default=False, db_index=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    archived_by = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        abstract = True

    def archive(self, user_identifier: str = None):
        """Soft-deletes the record preserving database integrity."""
        self.is_archived = True
        self.archived_at = timezone.now()
        self.archived_by = user_identifier
        self.save(update_fields=['is_archived', 'archived_at', 'archived_by', 'updated_at'])

    def restore(self):
        """Restores a soft-archived record back to active state."""
        self.is_archived = False
        self.archived_at = None
        self.archived_by = None
        self.save(update_fields=['is_archived', 'archived_at', 'archived_by', 'updated_at'])


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


from audit.models import AuditLog


