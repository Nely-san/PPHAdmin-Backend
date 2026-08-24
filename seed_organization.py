import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from organization.models import Company, Department

def seed_organization():
    company, _ = Company.objects.get_or_create(
        name="Philippine Property Homes",
        defaults={"code": "PPH"}
    )

    departments = [
        {"name": "Software Engineering", "code": "ENG"},
        {"name": "Real Estate Sales", "code": "SALES"},
        {"name": "Human Resources", "code": "HR"},
        {"name": "Finance & Accounting", "code": "ACCT"},
        {"name": "Operations & Admin", "code": "OPS"},
    ]

    for dept in departments:
        Department.objects.get_or_create(
            company=company,
            name=dept["name"],
            defaults={"code": dept["code"]}
        )

    print(f"Successfully seeded company '{company.name}' with {len(departments)} departments!")

if __name__ == '__main__':
    seed_organization()
