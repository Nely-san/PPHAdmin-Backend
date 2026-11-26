from django.db import migrations

def cleanup_legacy_modules_and_permissions(apps, schema_editor):
    ModuleAccess = apps.get_model('settings', 'ModuleAccess')
    PagePermission = apps.get_model('users', 'PagePermission')

    # 1. Update Employee module name
    ModuleAccess.objects.filter(code='employees').update(name='Employee')
    ModuleAccess.objects.filter(code='employee').update(name='Employee')

    # 2. Remove obsolete modules
    obsolete_codes = ['shifts-rosters', 'attendance', 'base-rates', 'salary-base-rates', 'company_department', 'departments']
    ModuleAccess.objects.filter(code__in=obsolete_codes).delete()

    # 3. Update PagePermission names
    for perm in PagePermission.objects.filter(code__startswith='employees'):
        if 'Profiles' in perm.name:
            perm.name = perm.name.replace('Employee Profiles', 'Employee')
            perm.save()

    # 4. Remove obsolete PagePermissions (excluding my-attendance and attendance-exceptions)
    obsolete_perms = PagePermission.objects.filter(
        code__in=obsolete_codes
    ) | PagePermission.objects.filter(
        code__startswith='shifts-rosters:'
    ) | PagePermission.objects.filter(
        code__startswith='attendance:'
    ) | PagePermission.objects.filter(
        code__startswith='base-rates:'
    ) | PagePermission.objects.filter(
        code__startswith='salary-base-rates:'
    )
    obsolete_perms.delete()

class Migration(migrations.Migration):

    dependencies = [
        ('settings', '0003_auditlog'),
        ('users', '0005_remove_person_company_name_and_more'),
    ]

    operations = [
        migrations.RunPython(cleanup_legacy_modules_and_permissions, reverse_code=migrations.RunPython.noop),
    ]
