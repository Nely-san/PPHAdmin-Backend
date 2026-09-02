from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.core.exceptions import ValidationError
from core.models import BaseModel

class PagePermission(BaseModel):
    """
    Catalog of all functional modules and navigable pages in PPHAdmin.
    Example codes: 'dashboard', 'user-management', 'employees', 'payroll', 'shifts-rosters', 'attendance', 'audit-logs'.
    """
    code = models.CharField(max_length=100, unique=True, db_index=True)
    name = models.CharField(max_length=255)
    module = models.CharField(max_length=100, help_text="Category: SYSTEM, HR, ATTENDANCE, PAYROLL, SELF_SERVICE")
    icon = models.CharField(max_length=100, default="fi fi-rr-folder")
    description = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'page_permissions'
        ordering = ['module', 'name']

    def __str__(self):
        return f"[{self.module}] {self.name} ({self.code})"


class Role(BaseModel):
    """
    Dynamic Roles configurable by Super Admin.
    Can be assigned any combination of PagePermissions.
    """
    id = models.BigAutoField(primary_key=True, editable=False)
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=100, unique=True, db_index=True)
    description = models.TextField(null=True, blank=True)
    is_system_role = models.BooleanField(
        default=False, 
        help_text="Protects baseline system roles (like SUPER_ADMIN) from deletion"
    )
    permissions = models.ManyToManyField(PagePermission, related_name='roles', blank=True)

    class Meta:
        db_table = 'roles'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.code})"


class UserManager(BaseUserManager):
    def create_user(self, username, password=None, role=None, **extra_fields):
        if not username:
            raise ValueError("The Username field is required")
        user = self.model(username=username, role=role, **extra_fields)
        if password:
            user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password=None, **extra_fields):
        super_admin_role, _ = Role.objects.get_or_create(
            code='SUPER_ADMIN',
            defaults={'name': 'Super Admin', 'is_system_role': True}
        )
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('approval_status', 'APPROVED')
        return self.create_user(username, password, role=super_admin_role, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin, BaseModel):
    """
    System login account with Triple-Lock Super Admin Safeguards and Approval Lifecycle.
    """
    APPROVAL_STATUS_CHOICES = [
        ('PENDING', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]

    username = models.CharField(max_length=150, unique=True, db_index=True)
    email = models.EmailField(unique=True, null=True, blank=True, db_index=True)
    role = models.ForeignKey(Role, on_delete=models.PROTECT, related_name='users', null=True, blank=True)
    approval_status = models.CharField(
        max_length=20, 
        choices=APPROVAL_STATUS_CHOICES, 
        default='PENDING',
        db_index=True
    )
    rejection_reason = models.TextField(null=True, blank=True)
    approved_by = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='approved_users'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    custom_permissions = models.ManyToManyField(
        PagePermission, 
        related_name='custom_permitted_users', 
        blank=True,
        help_text="Custom page permissions assigned directly to this user overriding or supplementing role defaults"
    )
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = []

    class Meta:
        db_table = 'users'
        ordering = ['username']

    def clean(self):
        # 1. Enforce Single Super Admin Policy on creation/promotion
        if self.role and self.role.code == 'SUPER_ADMIN':
            existing = User.objects.filter(role__code='SUPER_ADMIN', is_archived=False)
            if self.pk:
                existing = existing.exclude(pk=self.pk)
            if existing.exists():
                raise ValidationError("System policy strictly allows only one active Super Admin account.")

        # 2. Immutable Role & Undeletable Safeguards for existing Super Admin
        if self.pk:
            original = User.objects.filter(pk=self.pk).first()
            if original and original.role and original.role.code == 'SUPER_ADMIN':
                # Role cannot be changed / demoted
                if not self.role or self.role.code != 'SUPER_ADMIN':
                    raise ValidationError("The Super Admin account's role cannot be modified or demoted to another role.")
                # Cannot be archived
                if self.is_archived:
                    raise ValidationError("The Super Admin account cannot be archived or soft-deleted.")
                # Cannot be deactivated
                if not self.is_active:
                    raise ValidationError("The Super Admin account cannot be deactivated.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.role and self.role.code == 'SUPER_ADMIN':
            raise ValidationError("The Super Admin account is permanent and cannot be deleted.")
        super().delete(*args, **kwargs)

    def archive(self, user_identifier: str = None):
        if self.role and self.role.code == 'SUPER_ADMIN':
            raise ValidationError("The Super Admin account cannot be archived.")
        super().archive(user_identifier=user_identifier)


class Person(BaseModel):
    """
    Personnel profile master record (Employee & OJT).
    """
    PERSON_TYPE_CHOICES = [
        ('EMPLOYEE', 'Regular Employee'),
        ('OJT', 'OJT Trainee / Intern'),
    ]
    EMPLOYMENT_MODE_CHOICES = [
        ('FULL_TIME', 'Full Time'),
        ('PART_TIME', 'Part Time'),
        ('CONTRACT', 'Contractual'),
        ('INTERN', 'Internship'),
    ]
    RATE_TYPE_CHOICES = [
        ('DAILY', 'Daily Paid'),
        ('MONTHLY', 'Monthly Paid'),
        ('HOURLY', 'Hourly Paid'),
    ]
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('ARCHIVED', 'Archived / Resigned'),
        ('ON_LEAVE', 'On Leave'),
        ('COMPLETED', 'Completed Internship'),
    ]

    biometric_id = models.CharField(max_length=50, unique=True, null=True, blank=True, db_index=True)
    name = models.CharField(max_length=255)
    person_type = models.CharField(max_length=20, choices=PERSON_TYPE_CHOICES, default='EMPLOYEE')
    employment_mode = models.CharField(max_length=20, choices=EMPLOYMENT_MODE_CHOICES, default='FULL_TIME')
    rate_type = models.CharField(max_length=20, choices=RATE_TYPE_CHOICES, default='DAILY')
    base_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    date_started = models.DateField(null=True, blank=True)
    date_ended = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')

    # Linked User Account
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='person')

    # Department & Company Info
    company_name = models.CharField(max_length=255, null=True, blank=True)
    department_name = models.CharField(max_length=255, null=True, blank=True)

    # OJT Internship Specific Tracking
    school_name = models.CharField(max_length=255, null=True, blank=True)
    coordinator_contact = models.CharField(max_length=255, null=True, blank=True)
    required_ojt_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, null=True, blank=True)
    rendered_ojt_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, null=True, blank=True)

    # Setup Queue Flag for biometric auto-registered profiles
    is_newly_imported = models.BooleanField(default=False, db_index=True)

    # Work Schedule & Arrangement Setup
    work_setup = models.CharField(max_length=20, default='ONSITE', null=True, blank=True, help_text="ONSITE, WFH, HYBRID, OFFSITE")
    notes = models.TextField(null=True, blank=True, help_text="Work arrangement notes, reporting method, hybrid schedule, etc.")
    shift_code = models.CharField(max_length=50, default='DAY', null=True, blank=True)
    work_days = models.CharField(max_length=100, default='Mon - Fri', null=True, blank=True)

    class Meta:
        db_table = 'persons'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.person_type})"


from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=User)
def ensure_person_for_user(sender, instance, created, **kwargs):
    """
    Ensure every active/created User account has a corresponding Person profile
    so it seamlessly appears in the Employees directory.
    """
    try:
        person = getattr(instance, 'person', None)
        if not person:
            existing_person = Person.objects.filter(name__iexact=instance.username, user__isnull=True).first()
            if existing_person:
                existing_person.user = instance
                existing_person.save(update_fields=['user'])
            else:
                is_ojt = instance.role and instance.role.code == 'OJT'
                Person.objects.create(
                    user=instance,
                    name=instance.username,
                    person_type='OJT' if is_ojt else 'EMPLOYEE',
                    employment_mode='INTERN' if is_ojt else 'FULL_TIME',
                    rate_type='HOURLY' if is_ojt else 'DAILY',
                    base_rate=0.00,
                    status='ACTIVE'
                )
    except Exception:
        pass
