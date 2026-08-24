import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from settings.models import SystemParameter

DEFAULT_SETTINGS = [
    # GENERAL
    {"key": "system_name", "value": "PPHAdmin", "category": "GENERAL", "description": "System branding name"},
    {"key": "company_name", "value": "Philippine Property Homes", "category": "GENERAL", "description": "Primary company name"},
    {"key": "support_email", "value": "support@philippinepropertyhomes.com", "category": "GENERAL", "description": "System administrator support email"},
    {"key": "currency", "value": "PHP", "category": "GENERAL", "description": "System transactional currency"},

    # ATTENDANCE
    {"key": "attendance_grace_period", "value": "15", "category": "ATTENDANCE", "description": "Late arrival grace period in minutes"},
    {"key": "attendance_overtime_threshold", "value": "60", "category": "ATTENDANCE", "description": "Minimum rendered minutes to qualify for overtime"},
    {"key": "attendance_undertime_threshold", "value": "30", "category": "ATTENDANCE", "description": "Under-time qualification threshold in minutes"},
    {"key": "standard_daily_hours", "value": "8.0", "category": "ATTENDANCE", "description": "Standard required work hours per day"},
    {"key": "auto_break_deduction", "value": "60", "category": "ATTENDANCE", "description": "Automatic lunch break deduction in minutes"},

    # SECURITY
    {"key": "security_min_password_length", "value": "8", "category": "SECURITY", "description": "Minimum required password length"},
    {"key": "security_max_login_attempts", "value": "5", "category": "SECURITY", "description": "Max failed login attempts before temporary lockout"},
    {"key": "security_session_timeout", "value": "30", "category": "SECURITY", "description": "Inactivity session timeout in minutes"},
]

def seed_settings():
    for item in DEFAULT_SETTINGS:
        param, created = SystemParameter.objects.get_or_create(
            key=item["key"],
            defaults=item
        )
        if not created:
            param.category = item["category"]
            param.description = item["description"]
            param.save()
    print(f"Successfully seeded {len(DEFAULT_SETTINGS)} default system parameters!")

if __name__ == '__main__':
    seed_settings()
