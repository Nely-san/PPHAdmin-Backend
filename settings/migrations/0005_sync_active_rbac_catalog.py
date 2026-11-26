import uuid
from django.db import migrations

def sync_active_rbac_catalog(apps, schema_editor):
    ModuleAccess = apps.get_model('settings', 'ModuleAccess')
    PagePermission = apps.get_model('users', 'PagePermission')
    Role = apps.get_model('users', 'Role')

    # 1. Clean up obsolete module codes & permission codes
    obsolete_codes = [
        'attendance-exceptions', 'leave-ob-approvals', 'shifts-rosters',
        'base-rates', 'salary-base-rates', 'company_department', 'departments'
    ]
    ModuleAccess.objects.filter(code__in=obsolete_codes).delete()
    PagePermission.objects.filter(code__in=obsolete_codes).delete()
    for code in obsolete_codes:
        PagePermission.objects.filter(code__startswith=f"{code}:").delete()

    # 2. Master active modules definition
    ACTIVE_MODULES = [
        {
            'code': 'dashboard',
            'name': 'Dashboard',
            'module': 'SYSTEM',
            'icon': 'fi fi-rr-chart-histogram',
            'path': '/dashboard',
            'is_primary': True,
            'tag': None,
            'display_order': 1,
            'allowed_actions': ['view', 'add', 'edit', 'delete'],
            'description': 'System overview, statistics, and shortcuts'
        },
        {
            'code': 'user-management',
            'name': 'User Management',
            'module': 'SYSTEM',
            'icon': 'fi fi-rr-users',
            'path': '/user-management',
            'is_primary': False,
            'tag': 'Security',
            'display_order': 2,
            'allowed_actions': ['view', 'add', 'edit', 'delete'],
            'description': 'User account provisioning, credentials, and approvals'
        },
        {
            'code': 'roles-permissions',
            'name': 'Roles & Permissions',
            'module': 'SYSTEM',
            'icon': 'fi fi-rr-shield-check',
            'path': '/roles-permissions',
            'is_primary': False,
            'tag': 'Security',
            'display_order': 3,
            'allowed_actions': ['view', 'add', 'edit', 'delete'],
            'description': 'Dynamic RBAC roles, page accessibility, and CRUD matrix'
        },
        {
            'code': 'employees',
            'name': 'Employee',
            'module': 'HR',
            'icon': 'fi fi-rr-users',
            'path': '/employees',
            'is_primary': False,
            'tag': None,
            'display_order': 4,
            'allowed_actions': ['view', 'add', 'edit', 'delete'],
            'description': 'Unified employee profiles, compensation, attendance, and work schedules'
        },
        {
            'code': 'attendance',
            'name': 'Attendance & Schedules',
            'module': 'HR',
            'icon': 'fi fi-rr-calendar-clock',
            'path': '/attendance',
            'is_primary': False,
            'tag': None,
            'display_order': 5,
            'allowed_actions': ['view', 'add', 'edit', 'delete'],
            'description': 'Attendance tracking, leave/OB approvals, shift schedules, biometrics, and exceptions'
        },
        {
            'code': 'hr-reports',
            'name': 'HR Reports',
            'module': 'HR',
            'icon': 'fi fi-rr-stats',
            'path': '/hr-reports',
            'is_primary': False,
            'tag': None,
            'display_order': 6,
            'allowed_actions': ['view', 'add', 'edit', 'delete'],
            'description': 'Attendance summaries, punctuality analytics, and leave balance utilization'
        },
        {
            'code': 'payroll',
            'name': 'Payroll Processing & Cutoff',
            'module': 'PAYROLL',
            'icon': 'fi fi-rr-wallet',
            'path': '/payroll',
            'is_primary': False,
            'tag': 'PHP',
            'display_order': 7,
            'allowed_actions': ['view', 'add', 'edit', 'delete'],
            'description': 'Generate cutoff calculations, earnings, deductions, and payslips'
        },
        {
            'code': 'payroll-reports',
            'name': 'Payroll Register & Reports',
            'module': 'PAYROLL',
            'icon': 'fi fi-rr-stats',
            'path': '/payroll-reports',
            'is_primary': False,
            'tag': None,
            'display_order': 8,
            'allowed_actions': ['view', 'add', 'edit', 'delete'],
            'description': 'Tax schedules, statutory contributions, and 13th month'
        },
        {
            'code': 'system-reports',
            'name': 'System Reports',
            'module': 'SYSTEM',
            'icon': 'fi fi-rr-stats',
            'path': '/system-reports',
            'is_primary': False,
            'tag': None,
            'display_order': 9,
            'allowed_actions': ['view', 'add', 'edit', 'delete'],
            'description': 'Audit trails, user activity, and executive summary reports'
        },
        {
            'code': 'system-settings',
            'name': 'System Parameters',
            'module': 'SYSTEM',
            'icon': 'fi fi-rr-settings',
            'path': '/system-settings',
            'is_primary': False,
            'tag': None,
            'display_order': 10,
            'allowed_actions': ['view', 'add', 'edit', 'delete'],
            'description': 'Organization configuration, cutoff rules, and environment parameters'
        },
        {
            'code': 'audit-logs',
            'name': 'System Audit Logs',
            'module': 'SYSTEM',
            'icon': 'fi fi-rr-receipt',
            'path': '/audit-logs',
            'is_primary': False,
            'tag': None,
            'display_order': 11,
            'allowed_actions': ['view', 'add', 'edit', 'delete'],
            'description': 'Immutable system audit logs and change history'
        },
        {
            'code': 'archive-vault',
            'name': 'Archive Vault',
            'module': 'SYSTEM',
            'icon': 'fi fi-rr-box-alt',
            'path': '/archive-vault',
            'is_primary': False,
            'tag': None,
            'display_order': 12,
            'allowed_actions': ['view', 'add', 'edit', 'delete'],
            'description': 'Restore or permanently delete archived user & employee records'
        },
        {
            'code': 'hr-archive',
            'name': 'Past Records',
            'module': 'HR',
            'icon': 'fi fi-rr-box-alt',
            'path': '/hr-archive',
            'is_primary': False,
            'tag': None,
            'display_order': 13,
            'allowed_actions': ['view', 'add', 'edit', 'delete'],
            'description': 'Past personnel records and historical contracts'
        },
        {
            'code': 'payroll-archive',
            'name': 'Payroll History Vault',
            'module': 'PAYROLL',
            'icon': 'fi fi-rr-box-alt',
            'path': '/payroll-archive',
            'is_primary': False,
            'tag': None,
            'display_order': 14,
            'allowed_actions': ['view', 'add', 'edit', 'delete'],
            'description': 'Locked historical payroll run registers and payslips'
        },
        {
            'code': 'my-attendance',
            'name': 'My Attendance Logs',
            'module': 'SELF_SERVICE',
            'icon': 'fi fi-rr-clock',
            'path': '/my-attendance',
            'is_primary': False,
            'tag': None,
            'display_order': 15,
            'allowed_actions': ['view', 'add', 'edit', 'delete'],
            'description': 'Personal daily time logs and punch history'
        },
        {
            'code': 'my-roster',
            'name': 'My Schedule',
            'module': 'SELF_SERVICE',
            'icon': 'fi fi-rr-calendar',
            'path': '/my-roster',
            'is_primary': False,
            'tag': None,
            'display_order': 16,
            'allowed_actions': ['view', 'add', 'edit', 'delete'],
            'description': 'Assigned shifts and upcoming schedule calendar'
        },
        {
            'code': 'my-leaves',
            'name': 'Leave, OB & OT Requests',
            'module': 'SELF_SERVICE',
            'icon': 'fi fi-rr-document-signed',
            'path': '/my-leaves',
            'is_primary': False,
            'tag': None,
            'display_order': 17,
            'allowed_actions': ['view', 'add', 'edit', 'delete'],
            'description': 'File leave, official business, and overtime requests'
        },
        {
            'code': 'my-payslips',
            'name': 'My Payslips',
            'module': 'SELF_SERVICE',
            'icon': 'fi fi-rr-receipt',
            'path': '/my-payslips',
            'is_primary': False,
            'tag': None,
            'display_order': 18,
            'allowed_actions': ['view', 'add', 'edit', 'delete'],
            'description': 'View and download itemized payslips'
        },
        {
            'code': 'my-biometrics',
            'name': 'My Biometric Scans',
            'module': 'SELF_SERVICE',
            'icon': 'fi fi-rr-clock',
            'path': '/my-biometrics',
            'is_primary': False,
            'tag': None,
            'display_order': 19,
            'allowed_actions': ['view', 'add', 'edit', 'delete'],
            'description': 'Trainee biometric punch verification'
        },
        {
            'code': 'my-internship-hours',
            'name': 'Internship Hours Tracking',
            'module': 'SELF_SERVICE',
            'icon': 'fi fi-rr-graduation-cap',
            'path': '/my-internship-hours',
            'is_primary': False,
            'tag': None,
            'display_order': 20,
            'allowed_actions': ['view', 'add', 'edit', 'delete'],
            'description': 'OJT required vs rendered hours tracker'
        },
    ]

    for item in ACTIVE_MODULES:
        ModuleAccess.objects.update_or_create(
            code=item['code'],
            defaults={
                'name': item['name'],
                'module': item['module'],
                'icon': item['icon'],
                'path': item['path'],
                'tag': item['tag'],
                'is_primary': item['is_primary'],
                'display_order': item['display_order'],
                'allowed_actions': item['allowed_actions'],
                'description': item['description'],
                'is_archived': False,
            }
        )

        # Ensure base PagePermission
        base_perm, _ = PagePermission.objects.update_or_create(
            code=item['code'],
            defaults={
                'name': item['name'],
                'module': item['module'],
                'icon': item['icon'],
                'description': item['description'],
                'is_archived': False,
            }
        )

        # Ensure granular action PagePermissions
        for action in ['view', 'add', 'edit', 'delete']:
            action_code = f"{item['code']}:{action}"
            PagePermission.objects.update_or_create(
                code=action_code,
                defaults={
                    'name': f"{item['name']} ({action.capitalize()})",
                    'module': item['module'],
                    'icon': item['icon'],
                    'description': f"Permission to {action} in {item['name']}",
                    'is_archived': False,
                }
            )

    # 3. Synchronize baseline roles with active permissions
    ROLE_PERMISSIONS_MAP = {
        'SUPER_ADMIN': [p.code for p in PagePermission.objects.filter(is_archived=False)],
        'ADMIN': [
            'dashboard', 'dashboard:view', 'dashboard:add', 'dashboard:edit',
            'user-management', 'user-management:view', 'user-management:add', 'user-management:edit', 'user-management:delete',
            'roles-permissions', 'roles-permissions:view', 'roles-permissions:add', 'roles-permissions:edit',
            'employees', 'employees:view', 'employees:add', 'employees:edit', 'employees:delete',
            'attendance', 'attendance:view', 'attendance:add', 'attendance:edit',
            'hr-reports', 'hr-reports:view', 'hr-reports:add',
            'payroll', 'payroll:view',
            'payroll-reports', 'payroll-reports:view',
            'system-reports', 'system-reports:view', 'system-reports:add', 'system-reports:edit',
            'system-settings', 'system-settings:view', 'system-settings:add', 'system-settings:edit',
            'audit-logs', 'audit-logs:view', 'audit-logs:add', 'audit-logs:edit',
            'archive-vault', 'archive-vault:view', 'archive-vault:add', 'archive-vault:edit', 'archive-vault:delete',
            'hr-archive', 'hr-archive:view', 'hr-archive:edit',
            'payroll-archive', 'payroll-archive:view',
        ],
        'HR_MANAGER': [
            'dashboard', 'dashboard:view', 'dashboard:add', 'dashboard:edit',
            'employees', 'employees:view', 'employees:add', 'employees:edit',
            'attendance', 'attendance:view', 'attendance:add', 'attendance:edit',
            'hr-reports', 'hr-reports:view', 'hr-reports:add',
            'hr-archive', 'hr-archive:view', 'hr-archive:edit',
        ],
        'PAYROLL_OFFICER': [
            'dashboard', 'dashboard:view', 'dashboard:add', 'dashboard:edit',
            'payroll', 'payroll:view', 'payroll:add', 'payroll:edit', 'payroll:delete',
            'payroll-reports', 'payroll-reports:view', 'payroll-reports:add', 'payroll-reports:edit',
            'payroll-archive', 'payroll-archive:view',
        ],
        'EMPLOYEE': [
            'dashboard', 'dashboard:view', 'dashboard:add', 'dashboard:edit',
            'my-attendance', 'my-attendance:view', 'my-attendance:add', 'my-attendance:edit',
            'my-roster', 'my-roster:view', 'my-roster:add',
            'my-leaves', 'my-leaves:view', 'my-leaves:add', 'my-leaves:edit',
            'my-payslips', 'my-payslips:view',
        ],
        'OJT': [
            'dashboard', 'dashboard:view', 'dashboard:add', 'dashboard:edit',
            'my-attendance', 'my-attendance:view', 'my-attendance:add',
            'my-biometrics', 'my-biometrics:view',
            'my-leaves', 'my-leaves:view', 'my-leaves:add',
            'my-roster', 'my-roster:view',
            'my-internship-hours', 'my-internship-hours:view', 'my-internship-hours:add',
        ],
    }

    for role_code, perm_codes in ROLE_PERMISSIONS_MAP.items():
        role = Role.objects.filter(code=role_code, is_archived=False).first()
        if role:
            perms = PagePermission.objects.filter(code__in=perm_codes, is_archived=False)
            role.permissions.set(perms)


class Migration(migrations.Migration):

    dependencies = [
        ('settings', '0004_cleanup_legacy_modules'),
        ('users', '0005_remove_person_company_name_and_more'),
    ]

    operations = [
        migrations.RunPython(sync_active_rbac_catalog, reverse_code=migrations.RunPython.noop),
    ]
