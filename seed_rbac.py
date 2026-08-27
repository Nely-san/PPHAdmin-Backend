import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from users.models import PagePermission, Role

PAGE_CATALOG = [
    # System Administration
    {"code": "dashboard", "name": "Dashboard", "module": "SYSTEM", "icon": "fi fi-rr-chart-histogram"},
    {"code": "user-management", "name": "User & Role Management", "module": "SYSTEM", "icon": "fi fi-rr-shield-check"},
    {"code": "system-settings", "name": "System Parameters", "module": "SYSTEM", "icon": "fi fi-rr-settings"},
    {"code": "audit-logs", "name": "System Audit Logs", "module": "SYSTEM", "icon": "fi fi-rr-receipt"},
    {"code": "archive-vault", "name": "Archive Vault", "module": "SYSTEM", "icon": "fi fi-rr-box-alt"},
    {"code": "system-reports", "name": "System Reports", "module": "SYSTEM", "icon": "fi fi-rr-stats"},

    # HR & Personnel
    {"code": "employees", "name": "Employee Profiles", "module": "HR", "icon": "fi fi-rr-users"},
    {"code": "shifts-rosters", "name": "Work Schedules", "module": "HR", "icon": "fi fi-rr-calendar"},
    {"code": "leave-ob-approvals", "name": "Leave & OB Approvals", "module": "HR", "icon": "fi fi-rr-checkbox"},
    {"code": "hr-archive", "name": "HR Past Records", "module": "HR", "icon": "fi fi-rr-box-alt"},

    # Biometrics & Attendance
    {"code": "attendance", "name": "Biometric Logs & Imports", "module": "ATTENDANCE", "icon": "fi fi-rr-clock"},
    {"code": "attendance-exceptions", "name": "Attendance Issues", "module": "ATTENDANCE", "icon": "fi fi-rr-triangle-warning"},

    # Payroll & Finance
    {"code": "base-rates", "name": "Salary Base Rates", "module": "PAYROLL", "icon": "fi fi-rr-usd-square"},
    {"code": "payroll", "name": "Payroll Processing & Cutoff", "module": "PAYROLL", "icon": "fi fi-rr-wallet"},
    {"code": "payroll-reports", "name": "Payroll Reports", "module": "PAYROLL", "icon": "fi fi-rr-stats"},
    {"code": "payroll-archive", "name": "Payroll History Vault", "module": "PAYROLL", "icon": "fi fi-rr-box-alt"},

    # Self Service & OJT
    {"code": "my-attendance", "name": "My Attendance Logs", "module": "SELF_SERVICE", "icon": "fi fi-rr-clock"},
    {"code": "my-roster", "name": "My Schedule", "module": "SELF_SERVICE", "icon": "fi fi-rr-calendar"},
    {"code": "my-leaves", "name": "Leave & OB Applications", "module": "SELF_SERVICE", "icon": "fi fi-rr-document-signed"},
    {"code": "my-payslips", "name": "My Payslips", "module": "SELF_SERVICE", "icon": "fi fi-rr-receipt"},
    {"code": "my-biometrics", "name": "My Biometric Scans", "module": "SELF_SERVICE", "icon": "fi fi-rr-clock"},
    {"code": "my-internship-hours", "name": "Internship Hours Tracking", "module": "SELF_SERVICE", "icon": "fi fi-rr-graduation-cap"},
]

def seed_rbac():
    # 1. Create Page Permissions
    perm_map = {}
    for item in PAGE_CATALOG:
        perm, _ = PagePermission.objects.get_or_create(
            code=item["code"],
            defaults=item
        )
        perm_map[item["code"]] = perm

    # 2. Baseline Role Definitions
    ROLES_CONFIG = {
        "SUPER_ADMIN": {
            "name": "Super Admin",
            "is_system_role": True,
            "description": "Full unrestricted access to all modules, role management, audit logs, and settings.",
            "pages": [p["code"] for p in PAGE_CATALOG]
        },
        "ADMIN": {
            "name": "Admin",
            "is_system_role": True,
            "description": "Administrative operations, user management, and system reports.",
            "pages": ["dashboard", "user-management", "employees", "base-rates", "system-reports", "archive-vault"]
        },
        "HR_MANAGER": {
            "name": "HR Manager",
            "is_system_role": True,
            "description": "HR operations, employee onboarding, rosters, biometric attendance, and leave approvals.",
            "pages": ["dashboard", "employees", "shifts-rosters", "attendance", "attendance-exceptions", "leave-ob-approvals", "hr-archive"]
        },
        "PAYROLL_OFFICER": {
            "name": "Payroll Officer",
            "is_system_role": True,
            "description": "Payroll computations, base rates matrix, and payroll reports.",
            "pages": ["dashboard", "base-rates", "payroll", "payroll-reports", "payroll-archive"]
        },
        "EMPLOYEE": {
            "name": "Employee",
            "is_system_role": True,
            "description": "Employee self-service timecards, schedules, leaves, and payslips.",
            "pages": ["dashboard", "my-attendance", "my-roster", "my-leaves", "my-payslips"]
        },
        "OJT": {
            "name": "OJT Trainee",
            "is_system_role": True,
            "description": "Intern self-service timecards, internship hours tracker, and leaves.",
            "pages": ["dashboard", "my-biometrics", "my-internship-hours", "my-leaves"]
        }
    }

    for code, config in ROLES_CONFIG.items():
        role, _ = Role.objects.get_or_create(
            code=code,
            defaults={
                "name": config["name"], 
                "is_system_role": config["is_system_role"],
                "description": config.get("description", "")
            }
        )
        role_perms = [perm_map[p_code] for p_code in config["pages"] if p_code in perm_map]
        role.permissions.set(role_perms)
        role.save()

    print("RBAC Catalog and baseline roles successfully seeded!")

if __name__ == '__main__':
    seed_rbac()
