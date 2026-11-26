import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models
from django.db.models import Count


def assert_no_duplicate_legacy_biometric_ids(Person):
    duplicates = (
        Person.objects.exclude(biometric_id__isnull=True)
        .exclude(biometric_id='')
        .values('biometric_id')
        .annotate(count=Count('id'))
        .filter(count__gt=1)
    )
    duplicate = duplicates.order_by('biometric_id').first()
    if duplicate:
        raise RuntimeError(
            "Cannot backfill biometric enrollments: duplicate legacy "
            f"Person.biometric_id {duplicate['biometric_id']!r} is assigned "
            f"to {duplicate['count']} persons."
        )


def backfill_legacy_biometric_ids(apps, schema_editor):
    Person = apps.get_model('users', 'Person')
    BiometricEnrollment = apps.get_model(
        'biometrics_attendance',
        'BiometricEnrollment',
    )

    assert_no_duplicate_legacy_biometric_ids(Person)

    for person in (
        Person.objects.exclude(biometric_id__isnull=True)
        .exclude(biometric_id='')
        .iterator()
    ):
        BiometricEnrollment.objects.update_or_create(
            person_id=person.pk,
            external_biometric_id=person.biometric_id,
            defaults={
                'device_name': 'Migrated from legacy field',
                'device_id': '',
                'status': 'ENROLLED',
                'is_active': True,
                'enrolled_by_id': None,
            },
        )


def remove_migrated_enrollments(apps, schema_editor):
    BiometricEnrollment = apps.get_model(
        'biometrics_attendance',
        'BiometricEnrollment',
    )
    BiometricEnrollment.objects.filter(
        device_name='Migrated from legacy field',
        enrolled_by_id=None,
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('biometrics_attendance', '0002_initial'),
        ('users', '0005_remove_person_company_name_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='BiometricEnrollment',
            fields=[
                ('id', models.UUIDField(
                    default=uuid.uuid4,
                    editable=False,
                    primary_key=True,
                    serialize=False,
                )),
                ('created_at', models.DateTimeField(
                    auto_now_add=True,
                    db_index=True,
                )),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_archived', models.BooleanField(db_index=True, default=False)),
                ('archived_at', models.DateTimeField(blank=True, null=True)),
                ('archived_by', models.CharField(
                    blank=True,
                    max_length=255,
                    null=True,
                )),
                ('device_name', models.CharField(
                    blank=True,
                    default='',
                    max_length=255,
                )),
                ('device_id', models.CharField(
                    blank=True,
                    db_index=True,
                    default='',
                    max_length=50,
                )),
                ('external_biometric_id', models.CharField(
                    db_index=True,
                    max_length=50,
                )),
                ('enrolled_at', models.DateTimeField(auto_now_add=True)),
                ('status', models.CharField(
                    choices=[
                        ('ENROLLED', 'Enrolled'),
                        ('REVOKED', 'Revoked'),
                    ],
                    default='ENROLLED',
                    max_length=20,
                )),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('enrolled_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='biometric_enrollments',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('person', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='biometric_enrollments',
                    to='users.person',
                )),
            ],
            options={
                'db_table': 'biometric_enrollments',
                'ordering': ['-enrolled_at'],
            },
        ),
        migrations.RunPython(
            backfill_legacy_biometric_ids,
            remove_migrated_enrollments,
        ),
        migrations.RunSQL(
            sql=(
                "ALTER TABLE `biometric_enrollments` "
                "ADD COLUMN `active_biometric_key` varchar(50) "
                "GENERATED ALWAYS AS ("
                "CASE WHEN `status` = 'ENROLLED' AND `is_active` = 1 "
                "THEN `external_biometric_id` ELSE NULL END"
                ") STORED, "
                "ADD COLUMN `active_person_key` char(32) "
                "GENERATED ALWAYS AS ("
                "CASE WHEN `status` = 'ENROLLED' AND `is_active` = 1 "
                "THEN `person_id` ELSE NULL END"
                ") STORED; "
                "ALTER TABLE `biometric_enrollments` "
                "ADD UNIQUE INDEX `uq_active_external_biometric_id` "
                "(`active_biometric_key`), "
                "ADD UNIQUE INDEX `uq_active_person_id` "
                "(`active_person_key`);"
            ),
            reverse_sql=(
                "ALTER TABLE `biometric_enrollments` "
                "DROP INDEX `uq_active_external_biometric_id`, "
                "DROP INDEX `uq_active_person_id`; "
                "ALTER TABLE `biometric_enrollments` "
                "DROP COLUMN `active_biometric_key`, "
                "DROP COLUMN `active_person_key`;"
            ),
        ),
        migrations.AddIndex(
            model_name='biometricenrollment',
            index=models.Index(
                fields=['person', 'status', 'is_active'],
                name='bio_enroll_person_status_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='biometricenrollment',
            index=models.Index(
                fields=['external_biometric_id', 'status'],
                name='bio_enroll_external_status_idx',
            ),
        ),
    ]
