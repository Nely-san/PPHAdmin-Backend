# Generated data migration to permanently purge obsolete report PagePermissions
from django.db import migrations

def purge_obsolete_report_permissions(apps, schema_editor):
    PagePermission = apps.get_model('users', 'PagePermission')
    ModuleAccess = apps.get_model('settings', 'ModuleAccess')

    obsolete_codes = ['hr-reports', 'payroll-reports', 'system-reports', 'payroll-register']
    
    # 1. Delete ModuleAccess records if any linger
    ModuleAccess.objects.filter(code__in=obsolete_codes).delete()

    # 2. Delete PagePermission records and cascade remove from role M2M
    for code in obsolete_codes:
        PagePermission.objects.filter(code=code).delete()
        PagePermission.objects.filter(code__startswith=f"{code}:").delete()

def reverse_purge(apps, schema_editor):
    pass

class Migration(migrations.Migration):
    dependencies = [
        ('settings', '0006_consolidate_reports_module_access'),
    ]

    operations = [
        migrations.RunPython(purge_obsolete_report_permissions, reverse_purge),
    ]
