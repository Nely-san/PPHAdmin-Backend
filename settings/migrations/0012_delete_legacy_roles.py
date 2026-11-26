from django.db import migrations

DELETED_ROLES = ['HR_MANAGER', 'PAYROLL_OFFICER', 'EMPLOYEE', 'OJT', 'TEST', 'QUALITY_INSPECTOR']
REASSIGN_TO = 'ADMIN'

def delete_legacy_roles(apps, schema_editor):
    Role = apps.get_model('users', 'Role')
    User = apps.get_model('users', 'User')

    admin_role = Role.objects.filter(code=REASSIGN_TO).first()
    if not admin_role:
        raise RuntimeError(f"Role '{REASSIGN_TO}' not found. Cannot reassign users.")

    # Reassign users on any deleted role to ADMIN (loop form, not QuerySet.update)
    reassigned = {}
    for code in DELETED_ROLES:
        old_role = Role.objects.filter(code=code).first()
        if not old_role:
            continue
        users = User.objects.filter(role=old_role)
        count = users.count()
        if count:
            for user in users:
                user.role = admin_role
                user.save(update_fields=['role'])
            reassigned[code] = count

    # Assert every user now has role in (SUPER_ADMIN, ADMIN) or role=None
    surviving_roles = Role.objects.filter(code__in=['SUPER_ADMIN', 'ADMIN'])
    broken = User.objects.exclude(role__in=surviving_roles).exclude(role__isnull=True).count()
    if broken > 0:
        raise RuntimeError(f"{broken} users still have a non-surviving role after reassignment.")

    # Assert every surviving role is not archived and is a system role
    for r in surviving_roles:
        if r.is_archived:
            raise RuntimeError(f"Surviving role '{r.code}' is archived.")
        if not r.is_system_role:
            raise RuntimeError(f"Surviving role '{r.code}' is not is_system_role=True.")

    # Hard-delete the six legacy roles
    deleted_count, _ = Role.objects.filter(code__in=DELETED_ROLES).delete()
    # deleted_count includes cascade-deleted roles_permissions rows; check
    # no role with a deleted code remains
    remaining = Role.objects.filter(code__in=DELETED_ROLES).count()
    if remaining > 0:
        raise RuntimeError(f"{remaining} roles still exist after deletion.")

    # Assert exactly two roles remain
    total = Role.objects.count()
    if total != 2:
        raise RuntimeError(f"Expected exactly 2 roles after deletion, found {total}.")

    # Record the reassignment count for the operator's report
    print(f"Reassigned users: {reassigned}")

def reverse_delete_legacy_roles(apps, schema_editor):
    raise RuntimeError(
        "Cannot reverse role deletion. The six legacy roles and their "
        "roles_permissions rows were hard-deleted, and the reassignment "
        "of users to ADMIN is not reversible without recording each user's "
        "original role. Restore from the DB backup taken before 4.2."
    )

class Migration(migrations.Migration):
    dependencies = [
        ('settings', '0011_grant_extra_flags_to_admin'),
    ]
    operations = [
        migrations.RunPython(delete_legacy_roles, reverse_delete_legacy_roles),
    ]
