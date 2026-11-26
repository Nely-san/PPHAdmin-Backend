# Generated data migration to consolidate reports into a single module & permission entry
from django.db import migrations

def consolidate_reports(apps, schema_editor):
    ModuleAccess = apps.get_model('settings', 'ModuleAccess')
    PagePermission = apps.get_model('users', 'PagePermission')
    Role = apps.get_model('users', 'Role')

    # 1. Update/Create PagePermission for reports
    base_perm, _ = PagePermission.objects.get_or_create(
        code='reports',
        defaults={
            'name': 'Reports & Analytics',
            'module': 'HR',
            'icon': 'fi fi-rr-stats',
            'description': 'Consolidated workforce, attendance, payroll register, statutory contributions, and executive analytics reports'
        }
    )
    base_perm.name = 'Reports & Analytics'
    base_perm.module = 'HR'
    base_perm.icon = 'fi fi-rr-stats'
    base_perm.is_archived = False
    base_perm.save()

    actions = [
        ('view', 'Reports & Analytics (View)'),
        ('add', 'Reports & Analytics (Add)'),
        ('edit', 'Reports & Analytics (Edit)'),
        ('delete', 'Reports & Analytics (Delete)'),
    ]
    action_perms = {}
    for act, desc in actions:
        perm, _ = PagePermission.objects.get_or_create(
            code=f'reports:{act}',
            defaults={
                'name': desc,
                'module': 'HR',
                'icon': 'fi fi-rr-stats',
                'description': f'Permission capabilities ({act.capitalize()}) for Reports & Analytics'
            }
        )
        perm.name = desc
        perm.module = 'HR'
        perm.is_archived = False
        perm.save()
        action_perms[act] = perm

    # 2. Migrate existing Roles permissions
    old_codes = ['hr-reports', 'payroll-reports', 'system-reports', 'payroll-register']
    for role in Role.objects.all():
        role_perm_codes = set(role.permissions.values_list('code', flat=True))
        has_any_report = any(c in role_perm_codes for c in old_codes) or any(c.startswith(tuple(f'{oc}:' for oc in old_codes)) for c in role_perm_codes)
        if has_any_report:
            role.permissions.add(base_perm)
            has_view = any(c in role_perm_codes for c in old_codes) or any(f'{oc}:view' in role_perm_codes for oc in old_codes)
            has_add = any(f'{oc}:add' in role_perm_codes for oc in old_codes)
            has_edit = any(f'{oc}:edit' in role_perm_codes for oc in old_codes)
            has_del = any(f'{oc}:delete' in role_perm_codes for oc in old_codes)

            if has_view or True:
                role.permissions.add(action_perms['view'])
            if has_add:
                role.permissions.add(action_perms['add'])
            if has_edit:
                role.permissions.add(action_perms['edit'])
            if has_del:
                role.permissions.add(action_perms['delete'])

    # 3. Soft archive or delete the old PagePermission records
    for oc in old_codes:
        PagePermission.objects.filter(code=oc).delete()
        PagePermission.objects.filter(code__startswith=f"{oc}:").delete()

    # 4. Consolidate ModuleAccess
    ModuleAccess.objects.filter(code__in=old_codes).delete()
    mod_access, _ = ModuleAccess.objects.get_or_create(
        code='reports',
        defaults={
            'name': 'Reports & Analytics',
            'module': 'HR',
            'icon': 'fi fi-rr-stats',
            'path': '/reports',
            'display_order': 6,
            'allowed_actions': ['view', 'add', 'edit', 'delete'],
            'description': 'Consolidated workforce, attendance, payroll register, statutory contributions, and executive analytics reports'
        }
    )
    mod_access.name = 'Reports & Analytics'
    mod_access.path = '/reports'
    mod_access.icon = 'fi fi-rr-stats'
    mod_access.is_archived = False
    mod_access.save()

def reverse_consolidate(apps, schema_editor):
    pass

class Migration(migrations.Migration):
    dependencies = [
        ('settings', '0005_sync_active_rbac_catalog'),
    ]

    operations = [
        migrations.RunPython(consolidate_reports, reverse_consolidate),
    ]
