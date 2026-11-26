from django.db import migrations


def backfill(apps, schema_editor):
    User = apps.get_model("users", "User")
    UserPagePermission = apps.get_model("users", "UserPagePermission")

    source_count = 0
    rows = []
    for user in User.objects.filter(
        custom_permissions__isnull=False
    ).distinct():
        for perm in user.custom_permissions.all():
            source_count += 1
            rows.append(UserPagePermission(
                user_id=user.id,
                page_key=perm.code,
                can_view=True,
                can_add=False,
                can_edit=False,
                can_delete=False,
            ))

    if rows:
        UserPagePermission.objects.bulk_create(rows, ignore_conflicts=True)

    created_count = UserPagePermission.objects.count()
    if created_count != source_count:
        raise RuntimeError(
            f"Backfill mismatch: source M2M rows={source_count}, "
            f"UserPagePermission rows={created_count}. Aborting."
        )

    bad = UserPagePermission.objects.filter(can_view=False).count()
    if bad:
        raise RuntimeError(
            f"Backfill sanity check failed: {bad} rows have can_view=False."
        )


def reverse(apps, schema_editor):
    UserPagePermission = apps.get_model("users", "UserPagePermission")
    deleted, _ = UserPagePermission.objects.all().delete()
    print(f"Reversed backfill: deleted {deleted} UserPagePermission rows.")


class Migration(migrations.Migration):
    dependencies = [("users", "0008_userpagepermission_and_more")]
    operations = [migrations.RunPython(backfill, reverse)]
