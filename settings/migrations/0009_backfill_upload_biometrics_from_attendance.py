# Generated data migration to backfill 'upload-biometrics' permission from 'attendance'
from django.db import migrations


def backfill_upload_biometrics_from_attendance(apps, schema_editor):
    PagePermission = apps.get_model('users', 'PagePermission')
    Role = apps.get_model('users', 'Role')

    perm_upload = PagePermission.objects.filter(code='upload-biometrics').first()
    if not perm_upload:
        raise RuntimeError(
            "PagePermission 'upload-biometrics' does not exist. Migration 0008 must run first."
        )

    # BEFORE: compute roles_with_attendance = set of role ids where the active role
    # has 'attendance' or any 'attendance:*' permission.
    roles_with_attendance = set(
        Role.objects.filter(
            is_archived=False,
            permissions__code__startswith='attendance'
        ).values_list('id', flat=True)
    ) | set(
        Role.objects.filter(
            is_archived=False,
            permissions__code='attendance'
        ).values_list('id', flat=True)
    )

    # Backfill upload-biometrics to each role
    for role in Role.objects.filter(id__in=roles_with_attendance):
        role.permissions.add(perm_upload)

    # AFTER: compute roles_with_upload_biometrics
    roles_with_upload_biometrics = set(
        Role.objects.filter(
            permissions__code='upload-biometrics'
        ).values_list('id', flat=True)
    )

    if roles_with_attendance != roles_with_upload_biometrics:
        raise RuntimeError(
            f"Backfill mismatch: roles_with_attendance={roles_with_attendance} != "
            f"roles_with_upload_biometrics={roles_with_upload_biometrics}"
        )

    if not roles_with_attendance.issubset(roles_with_upload_biometrics):
        missing = roles_with_attendance - roles_with_upload_biometrics
        raise RuntimeError(f"Missing roles from backfill set: {missing}")


def reverse_backfill_upload_biometrics_from_attendance(apps, schema_editor):
    """
    Reverse migration: removes 'upload-biometrics' from every role.
    Does not delete the PagePermission record itself (owned by 0008).
    Idempotent.
    """
    PagePermission = apps.get_model('users', 'PagePermission')
    Role = apps.get_model('users', 'Role')

    perm_upload = PagePermission.objects.filter(code='upload-biometrics').first()
    if perm_upload:
        for role in Role.objects.filter(permissions=perm_upload):
            role.permissions.remove(perm_upload)


class Migration(migrations.Migration):

    dependencies = [
        ('settings', '0008_add_upload_biometrics_and_extra_flags'),
    ]

    operations = [
        migrations.RunPython(
            backfill_upload_biometrics_from_attendance,
            reverse_backfill_upload_biometrics_from_attendance,
        ),
    ]
