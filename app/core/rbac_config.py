# AdminOS Role-Based Access Control (RBAC) Configuration for Backend

from typing import Dict, List

ROLE_PERMISSIONS: Dict[str, Dict[str, List[str]]] = {
    "SUPER_ADMIN": {
        "user_management": ["create", "read", "update", "archive", "restore"],
        "company_department": ["create", "read", "update", "archive", "restore"],
        "personnel": ["create", "read", "update", "archive", "restore"],
        "base_rates": ["create", "read", "update"],
        "shifts_rosters": ["create", "read", "update", "archive"],
        "biometrics": ["import", "read", "archive", "restore"],
        "leave_ob": ["create", "read", "archive", "approve"],
        "payroll": ["read", "approve", "archive"],
        "reports": ["read", "export"],
        "system_settings": ["create", "read", "update"]
    },
    "ADMIN": {
        "user_management": ["create", "read", "update", "archive", "restore"],
        "company_department": ["create", "read", "update", "archive", "restore"],
        "personnel": ["create", "read", "update", "archive", "restore"],
        "base_rates": ["read"],
        "shifts_rosters": ["create", "read", "update", "archive"],
        "biometrics": ["import", "read", "archive", "restore"],
        "leave_ob": ["create", "read", "archive", "approve"],
        "reports": ["read", "export"]
    },
    "HR_MANAGER": {
        "company_department": ["read"],
        "personnel": ["create", "read", "update", "archive", "restore"],
        "shifts_rosters": ["create", "read", "update", "archive"],
        "biometrics": ["import", "read", "archive", "restore", "process"],
        "leave_ob": ["create", "read", "archive", "approve"],
        "reports": ["read", "export"]
    },
    "PAYROLL_OFFICER": {
        "company_department": ["read"],
        "personnel": ["read"],
        "base_rates": ["create", "read", "update"],
        "biometrics": ["read"],
        "leave_ob": ["create", "read", "archive"],
        "payroll": ["read", "compute", "approve", "archive"],
        "reports": ["read", "export"]
    },
    "SUPERVISOR": {
        "company_department": ["read_dept"],
        "personnel": ["read_dept"],
        "shifts_rosters": ["read", "update_dept", "archive_dept"],
        "biometrics": ["read_dept"],
        "leave_ob": ["create", "read_dept", "archive", "endorse_dept"],
        "reports": ["read_dept"]
    },
    "EMPLOYEE": {
        "personnel": ["read_self"],
        "shifts_rosters": ["read_self"],
        "biometrics": ["read_self"],
        "leave_ob": ["create_self", "read_self", "archive_self"],
        "payroll": ["read_self"]
    },
    "OJT": {
        "personnel": ["read_self"],
        "shifts_rosters": ["read_self"],
        "biometrics": ["read_self"],
        "leave_ob": ["create_self", "read_self", "archive_self"],
        "reports": ["read_self"]
    }
}

def has_permission(role: str, module: str, action: str) -> bool:
    """
    Check if a given role has a specific permission action for a module.
    """
    role_modules = ROLE_PERMISSIONS.get(role, {})
    module_actions = role_modules.get(module, [])
    return action in module_actions
