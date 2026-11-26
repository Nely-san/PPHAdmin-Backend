# Generated data migration to idempotently seed core system roles SUPER_ADMIN and ADMIN
from django.db import migrations


def seed_core_roles(apps, schema_editor):
    Role = apps.get_model('users', 'Role')

    core_roles = [
        {'code': 'SUPER_ADMIN', 'name': 'Super Administrator'},
        {'code': 'ADMIN', 'name': 'Admin'},
    ]

    for item in core_roles:
        role, created = Role.objects.get_or_create(
            code=item['code'],
            defaults={
                'name': item['name'],
                'is_system_role': True,
                'is_archived': False,
            }
        )
        if not created:
            updated_fields = []
            if not role.is_system_role:
                role.is_system_role = True
                updated_fields.append('is_system_role')
            if role.is_archived:
                role.is_archived = False
                updated_fields.append('is_archived')
            if updated_fields:
                role.save(update_fields=updated_fields)

    core_codes = ['SUPER_ADMIN', 'ADMIN']
    roles = Role.objects.filter(code__in=core_codes, is_system_role=True)
    if roles.count() != 2:
        raise RuntimeError(
            f"Expected exactly 2 roles with code in {core_codes} and is_system_role=True, found {roles.count()}"
        )

    for r in roles:
        if r.is_archived:
            raise RuntimeError(
                f"Core role '{r.code}' must have is_archived=False, found is_archived=True"
            )


def reverse_seed_core_roles(apps, schema_editor):
    """
    Reverse migration: deletes SUPER_ADMIN and ADMIN roles if no users are attached.
    Raises RuntimeError if any role has users attached.
    """
    Role = apps.get_model('users', 'Role')
    User = apps.get_model('users', 'User')

    for code in ['ADMIN', 'SUPER_ADMIN']:
        role = Role.objects.filter(code=code).first()
        if role:
            if User.objects.filter(role=role).exists():
                raise RuntimeError(
                    f"Cannot reverse seed_core_roles: Role '{code}' has users attached."
                )
            role.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('settings', '0009_backfill_upload_biometrics_from_attendance'),
    ]

    operations = [
        migrations.RunPython(
            seed_core_roles,
            reverse_seed_core_roles,
        ),
    ]
