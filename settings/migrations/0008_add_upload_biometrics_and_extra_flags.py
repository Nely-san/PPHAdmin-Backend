# Generated data migration to add 'upload-biometrics' and three permission flags
from django.db import migrations


def add_upload_biometrics_and_extra_flags(apps, schema_editor):
    PagePermission = apps.get_model('users', 'PagePermission')

    new_permissions = [
        {
            'code': 'upload-biometrics',
            'name': 'Upload Biometrics & Terminal Data',
            'module': 'ATTENDANCE',
            'icon': 'fi fi-rr-fingerprint',
            'description': 'Upload biometric punch logs from terminal exports',
        },
        {
            'code': 'payroll:approve',
            'name': 'Payroll Approval',
            'module': 'PAYROLL',
            'icon': 'fi fi-rr-check-circle',
            'description': 'Approve payroll runs',
        },
        {
            'code': 'payroll:export',
            'name': 'Payroll Export',
            'module': 'PAYROLL',
            'icon': 'fi fi-rr-download',
            'description': 'Export payroll data',
        },
        {
            'code': 'employees:view_salary',
            'name': 'View Employee Salary',
            'module': 'EMPLOYEES',
            'icon': 'fi fi-rr-usd-square',
            'description': 'View employee salary and compensation',
        },
    ]

    for item in new_permissions:
        perm, created = PagePermission.objects.get_or_create(
            code=item['code'],
            defaults={
                'name': item['name'],
                'module': item['module'],
                'icon': item['icon'],
                'description': item['description'],
                'is_archived': False,
            }
        )
        if not created:
            perm.name = item['name']
            perm.module = item['module']
            perm.icon = item['icon']
            perm.description = item['description']
            perm.is_archived = False
            perm.save()

    codes = [item['code'] for item in new_permissions]
    count = PagePermission.objects.filter(code__in=codes).count()
    if count != 4:
        raise RuntimeError(f"Expected 4 PagePermission rows for {codes}, found {count}")

    for item in new_permissions:
        row = PagePermission.objects.get(code=item['code'])
        if row.module != item['module']:
            raise RuntimeError(
                f"PagePermission '{item['code']}' has module '{row.module}', expected '{item['module']}'"
            )


def reverse_add_upload_biometrics_and_extra_flags(apps, schema_editor):
    """
    Reverse migration: Deletes the four created PagePermission codes.
    These codes did not exist prior to this migration, so deleting them unconditionally
    on reverse is safe and idempotent.
    """
    PagePermission = apps.get_model('users', 'PagePermission')
    codes = [
        'upload-biometrics',
        'payroll:approve',
        'payroll:export',
        'employees:view_salary',
    ]
    PagePermission.objects.filter(code__in=codes).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('settings', '0007_cleanup_obsolete_report_pagepermissions'),
    ]

    operations = [
        migrations.RunPython(
            add_upload_biometrics_and_extra_flags,
            reverse_add_upload_biometrics_and_extra_flags,
        ),
    ]
