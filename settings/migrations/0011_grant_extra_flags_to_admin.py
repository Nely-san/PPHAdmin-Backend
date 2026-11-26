# Generated data migration to grant extra permission flags to ADMIN role
from django.db import migrations


def grant_extra_flags_to_admin(apps, schema_editor):
    PagePermission = apps.get_model('users', 'PagePermission')
    Role = apps.get_model('users', 'Role')

    flag_codes = ['payroll:approve', 'payroll:export', 'employees:view_salary']
    flags = list(PagePermission.objects.filter(code__in=flag_codes))
    if len(flags) != 3:
        found_codes = [f.code for f in flags]
        raise RuntimeError(
            f"Expected 3 PagePermission rows for {flag_codes}, found {len(flags)}: {found_codes}"
        )

    admin_role = Role.objects.filter(code='ADMIN').first()
    if not admin_role:
        raise RuntimeError("Role 'ADMIN' not found.")
    if admin_role.is_archived:
        raise RuntimeError("Role 'ADMIN' is archived. Structural problem.")

    for flag in flags:
        admin_role.permissions.add(flag)

    count = admin_role.permissions.filter(code__in=flag_codes).count()
    if count != 3:
        raise RuntimeError(
            f"Expected ADMIN to have 3 flags in {flag_codes}, found {count}"
        )


def reverse_grant_extra_flags_to_admin(apps, schema_editor):
    """
    Reverse migration: removes the 3 extra flags from ADMIN role.
    Idempotent.
    """
    PagePermission = apps.get_model('users', 'PagePermission')
    Role = apps.get_model('users', 'Role')

    admin_role = Role.objects.filter(code='ADMIN').first()
    if admin_role:
        flag_codes = ['payroll:approve', 'payroll:export', 'employees:view_salary']
        flags = PagePermission.objects.filter(code__in=flag_codes)
        for flag in flags:
            admin_role.permissions.remove(flag)


class Migration(migrations.Migration):

    dependencies = [
        ('settings', '0010_seed_core_roles'),
    ]

    operations = [
        migrations.RunPython(
            grant_extra_flags_to_admin,
            reverse_grant_extra_flags_to_admin,
        ),
    ]
