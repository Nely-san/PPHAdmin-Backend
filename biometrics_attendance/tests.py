from datetime import date, time, datetime
from decimal import Decimal
import io
import importlib
from unittest.mock import patch
from django.apps import apps
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection, IntegrityError, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APITestCase
from rest_framework import status
from users.models import User, Role, Person
from scheduling.models import Shift
from biometrics_attendance.models import (
    BiometricEnrollment, BiometricImportBatch, AttendanceRecord, AbnormalClocking
)
from biometrics_attendance.engine import compute_daily_attendance, process_biometric_import

class BiometricsAttendanceTests(APITestCase):
    def setUp(self):
        self.role, _ = Role.objects.get_or_create(code='HR_ADMIN', defaults={'name': 'HR Admin'})
        self.user = User.objects.create_user(username='hr_tester', password='password123', role=self.role)
        self.client.force_authenticate(user=self.user)

        self.shift = Shift.objects.create(
            code='DAY', name='Day Shift', start_time='09:00', end_time='18:00',
            work_hours=Decimal('8.00'), grace_period_mins=10
        )
        self.person = Person.objects.create(
            biometric_id='101', name='John Biometrics', person_type='EMPLOYEE',
            base_rate=Decimal('600.00'), status='ACTIVE'
        )
        BiometricEnrollment.objects.create(
            person=self.person,
            external_biometric_id='101',
            device_name='Migrated test fixture',
            device_id='',
            status='ENROLLED',
            is_active=True,
            enrolled_by=None,
        )
        self.ojt = Person.objects.create(
            biometric_id='102', name='Sarah Intern', person_type='OJT',
            base_rate=Decimal('0.00'), rendered_ojt_hours=Decimal('10.00'), status='ACTIVE'
        )
        BiometricEnrollment.objects.create(
            person=self.ojt,
            external_biometric_id='102',
            device_name='Migrated test fixture',
            device_id='',
            status='ENROLLED',
            is_active=True,
            enrolled_by=None,
        )

    def test_compute_daily_attendance_ontime(self):
        rec_date = date(2026, 3, 1)
        res = compute_daily_attendance(
            person=self.person,
            record_date=rec_date,
            am_in_t=time(8, 55),
            am_out_t=time(12, 0),
            pm_in_t=time(13, 0),
            pm_out_t=time(18, 0),
            ot_in_t=None,
            ot_out_t=None,
            shift=self.shift
        )
        self.assertEqual(res['tardiness_minutes'], 0)
        self.assertEqual(res['actual_hours'], Decimal('8.00'))
        self.assertEqual(res['status'], 'PRESENT')
        self.assertFalse(res['is_abnormal'])

    def test_compute_daily_attendance_tardy(self):
        rec_date = date(2026, 3, 1)
        # Clock in at 09:25 AM (15 mins past 10 min grace period = 25 mins tardy from 09:00)
        res = compute_daily_attendance(
            person=self.person,
            record_date=rec_date,
            am_in_t=time(9, 25),
            am_out_t=time(12, 0),
            pm_in_t=time(13, 0),
            pm_out_t=time(18, 0),
            ot_in_t=None,
            ot_out_t=None,
            shift=self.shift
        )
        self.assertEqual(res['tardiness_minutes'], 25)
        self.assertEqual(res['status'], 'LATE')
        self.assertTrue(res['is_abnormal'])

    def test_biometric_import_and_ojt_increment(self):
        csv_content = (
            "biometric_id,name,date,am_in,am_out,pm_in,pm_out\n"
            "101,John Biometrics,2026-03-02,08:58,12:00,13:00,18:00\n"
            "102,Sarah Intern,2026-03-02,09:00,12:00,13:00,18:00\n"
            "999,Unknown Newbie,2026-03-02,09:00,12:00,13:00,18:00\n"
        ).encode('utf-8')

        uploaded = SimpleUploadedFile("attendance_test.csv", csv_content, content_type="text/csv")
        res = self.client.post('/api/biometrics/upload/', {'file': uploaded}, format='multipart')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['success'], True)
        self.assertEqual(res.data['records_imported'], 3)
        self.assertEqual(res.data['newly_created_accounts_count'], 1)

        # Verify OJT rendered hours incremented by 8
        self.ojt.refresh_from_db()
        self.assertEqual(self.ojt.rendered_ojt_hours, Decimal('18.00'))

        # Verify newly created person
        newbie = Person.objects.filter(biometric_id='999').first()
        self.assertIsNotNone(newbie)
        self.assertTrue(newbie.is_newly_imported)
        enrollment = BiometricEnrollment.objects.get(person=newbie)
        self.assertEqual(enrollment.external_biometric_id, '999')
        self.assertEqual(enrollment.status, 'ENROLLED')
        self.assertTrue(enrollment.is_active)
        self.assertEqual(enrollment.device_id, '')
        self.assertEqual(enrollment.device_name, 'Biometric import')

    def test_import_revoked_id_does_not_match_person(self):
        revoked_owner = Person.objects.create(
            name='Revoked Owner',
            status='ACTIVE',
        )
        BiometricEnrollment.objects.create(
            person=revoked_owner,
            external_biometric_id='REV-100',
            status='REVOKED',
            is_active=False,
        )
        raw_records = [{
            'biometric_id': 'REV-100',
            'name': 'Revoked Owner',
            'date': date(2026, 3, 2),
            'am_in': None,
            'pm_out': None,
        }]

        with patch(
            'biometrics_attendance.engine.extract_rows_from_file',
            return_value=raw_records,
        ):
            process_biometric_import(
                io.BytesIO(b''),
                'revoked-match.csv',
            )

        revoked_owner.refresh_from_db()
        self.assertEqual(
            revoked_owner.biometric_enrollments.filter(status='REVOKED').count(),
            1,
        )
        self.assertFalse(
            BiometricEnrollment.objects.filter(
                person=revoked_owner,
                status='ENROLLED',
                is_active=True,
            ).exists()
        )

    def test_import_revoked_id_does_not_auto_enroll_by_name(self):
        candidate = Person.objects.create(
            name='Revoked Name Candidate',
            biometric_id=None,
            status='ACTIVE',
        )
        revoked_owner = Person.objects.create(name='Other Revoked Owner', status='ACTIVE')
        BiometricEnrollment.objects.create(
            person=revoked_owner,
            external_biometric_id='REV-NAME',
            status='REVOKED',
            is_active=False,
        )
        raw_records = [{
            'biometric_id': 'REV-NAME',
            'name': candidate.name,
            'date': date(2026, 3, 2),
            'am_in': None,
            'pm_out': None,
        }]

        with patch(
            'biometrics_attendance.engine.extract_rows_from_file',
            return_value=raw_records,
        ):
            process_biometric_import(io.BytesIO(b''), 'revoked-name.csv')

        candidate.refresh_from_db()
        self.assertIsNone(candidate.biometric_id)
        self.assertFalse(
            candidate.biometric_enrollments.filter(is_active=True).exists()
        )

    def test_import_revoked_id_does_not_create_new_person(self):
        owner = Person.objects.create(name='Revoked Unknown Owner', status='ACTIVE')
        BiometricEnrollment.objects.create(
            person=owner,
            external_biometric_id='REV-NEW',
            status='REVOKED',
            is_active=False,
        )
        raw_records = [{
            'biometric_id': 'REV-NEW',
            'name': 'Unknown Revoked Person',
            'date': date(2026, 3, 2),
            'am_in': None,
            'pm_out': None,
        }]

        with patch(
            'biometrics_attendance.engine.extract_rows_from_file',
            return_value=raw_records,
        ):
            process_biometric_import(io.BytesIO(b''), 'revoked-new.csv')

        self.assertFalse(
            Person.objects.filter(name='Unknown Revoked Person').exists()
        )
        self.assertFalse(
            Person.objects.filter(biometric_id='REV-NEW').exists()
        )

    def test_import_name_match_creates_enrollment(self):
        candidate = Person.objects.create(
            name='Unassigned Import Employee',
            biometric_id=None,
            status='ACTIVE',
        )
        raw_records = [{
            'biometric_id': 'NAME-MATCH-300',
            'name': candidate.name,
            'date': date(2026, 3, 2),
            'am_in': None,
            'pm_out': None,
        }]

        with patch(
            'biometrics_attendance.engine.extract_rows_from_file',
            return_value=raw_records,
        ):
            process_biometric_import(io.BytesIO(b''), 'name-match.csv')

        candidate.refresh_from_db()
        enrollment = candidate.biometric_enrollments.get()
        self.assertEqual(candidate.biometric_id, 'NAME-MATCH-300')
        self.assertEqual(enrollment.external_biometric_id, 'NAME-MATCH-300')
        self.assertEqual(enrollment.status, 'ENROLLED')
        self.assertTrue(enrollment.is_active)
        self.assertEqual(enrollment.device_id, '')
        self.assertEqual(enrollment.device_name, 'Biometric import')
        self.assertIsNone(enrollment.enrolled_by)

    def test_import_new_person_creates_enrollment(self):
        raw_records = [{
            'biometric_id': 'NEW-PERSON-400',
            'name': 'New Import Employee',
            'date': date(2026, 3, 2),
            'am_in': None,
            'pm_out': None,
        }]

        with patch(
            'biometrics_attendance.engine.extract_rows_from_file',
            return_value=raw_records,
        ):
            process_biometric_import(io.BytesIO(b''), 'new-person.csv')

        person = Person.objects.get(name='New Import Employee')
        enrollment = person.biometric_enrollments.get()
        self.assertEqual(person.biometric_id, 'NEW-PERSON-400')
        self.assertEqual(enrollment.external_biometric_id, 'NEW-PERSON-400')
        self.assertEqual(enrollment.status, 'ENROLLED')
        self.assertTrue(enrollment.is_active)
        self.assertEqual(enrollment.device_id, '')
        self.assertEqual(enrollment.device_name, 'Biometric import')
        self.assertIsNone(enrollment.enrolled_by)

    def test_import_transaction_rolls_back_on_failure(self):
        candidate = Person.objects.create(
            name='Rollback Import Employee',
            biometric_id=None,
            status='ACTIVE',
        )
        raw_records = [{
            'biometric_id': 'ROLLBACK-500',
            'name': candidate.name,
            'date': date(2026, 3, 2),
            'am_in': None,
            'pm_out': None,
        }]

        with patch(
            'biometrics_attendance.engine.extract_rows_from_file',
            return_value=raw_records,
        ), patch(
            'biometrics_attendance.engine.AttendanceRecord.objects.update_or_create',
            side_effect=RuntimeError('forced mid-import failure'),
        ):
            with self.assertRaisesRegex(RuntimeError, 'forced mid-import failure'):
                process_biometric_import(io.BytesIO(b''), 'rollback.csv')

        candidate.refresh_from_db()
        self.assertIsNone(candidate.biometric_id)
        self.assertTrue(
            Person.objects.filter(pk=candidate.pk, name=candidate.name).exists()
        )
        self.assertFalse(
            BiometricEnrollment.objects.filter(
                external_biometric_id='ROLLBACK-500',
            ).exists()
        )

    def test_import_revoked_lookup_is_scoped_to_file(self):
        outside_owner = Person.objects.create(name='Outside Revoked Owner', status='ACTIVE')
        inside_owner = Person.objects.create(name='Inside Revoked Owner', status='ACTIVE')
        BiometricEnrollment.objects.create(
            person=outside_owner,
            external_biometric_id='REV-OUTSIDE',
            status='REVOKED',
            is_active=False,
        )
        BiometricEnrollment.objects.create(
            person=inside_owner,
            external_biometric_id='REV-INSIDE',
            status='REVOKED',
            is_active=False,
        )
        raw_records = [{
            'biometric_id': 'REV-INSIDE',
            'name': 'Scoped Revoked Employee',
            'date': date(2026, 3, 2),
            'am_in': None,
            'pm_out': None,
        }]

        with patch(
            'biometrics_attendance.engine.extract_rows_from_file',
            return_value=raw_records,
        ), CaptureQueriesContext(connection) as captured:
            process_biometric_import(io.BytesIO(b''), 'scoped-revoked.csv')

        revoked_queries = [
            query['sql'] for query in captured.captured_queries
            if 'biometric_enrollments' in query['sql']
            and 'external_biometric_id' in query['sql']
        ]
        self.assertTrue(revoked_queries)
        self.assertTrue(
            any("'REV-INSIDE'" in sql for sql in revoked_queries),
            revoked_queries,
        )
        self.assertFalse(
            any("'REV-OUTSIDE'" in sql for sql in revoked_queries),
            revoked_queries,
        )

    def test_field_log_and_exception_justification(self):
        # 1. Submit Field OB punch
        res = self.client.post('/api/attendance/field-log/', {
            'person_id': str(self.person.id),
            'date': '2026-03-03',
            'am_in': '09:00:00',
            'pm_out': '18:00:00',
            'location': 'Client Office Cebu',
            'reason': 'System deployment meeting'
        })
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['status'], 'BUSINESS_TRIP')
        self.assertTrue(res.data['is_field_ob'])

        # 2. Create and justify exception
        att = AttendanceRecord.objects.get(id=res.data['id'])
        exc = AbnormalClocking.objects.create(
            attendance_record=att, person=self.person, date=att.date,
            tardiness_minutes=30, status='PENDING'
        )
        res2 = self.client.post(f'/api/attendance/exceptions/{exc.id}/justify/', {
            'status': 'EXCUSED',
            'reason': 'Heavy traffic due to VIP convoy'
        })
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.assertEqual(res2.data['status'], 'EXCUSED')

    def test_compute_daily_attendance_absent(self):
        rec_date = date(2026, 3, 4)
        res = compute_daily_attendance(
            person=self.person,
            record_date=rec_date,
            am_in_t=None,
            am_out_t=None,
            pm_in_t=None,
            pm_out_t=None,
            ot_in_t=None,
            ot_out_t=None,
            shift=self.shift
        )
        self.assertEqual(res['status'], 'ABSENT')
        self.assertTrue(res['is_absent'])
        self.assertTrue(res['is_abnormal'])
        self.assertEqual(res['actual_hours'], Decimal('0.00'))
        self.assertIn('absence', res['anomaly_reason'].lower())

    def test_compute_daily_attendance_missing_punch(self):
        rec_date = date(2026, 3, 5)
        # AM In present, PM Out missing
        res = compute_daily_attendance(
            person=self.person,
            record_date=rec_date,
            am_in_t=time(8, 55),
            am_out_t=None,
            pm_in_t=None,
            pm_out_t=None,
            ot_in_t=None,
            ot_out_t=None,
            shift=self.shift
        )
        self.assertEqual(res['status'], 'PRESENT')
        self.assertTrue(res['is_abnormal'])
        self.assertIn('missing pm clock-out', res['anomaly_reason'].lower())

    def test_attendance_exceptions_authorization_and_self_justify(self):
        emp_role, _ = Role.objects.get_or_create(code='EMPLOYEE', defaults={'name': 'Employee'})
        emp_user = User.objects.create_user(username='emp_viewer', password='password123', role=emp_role)
        # User post_save signal automatically created emp_user.person
        own_person = emp_user.person

        # Exception on someone else's record (self.person)
        other_exc = AbnormalClocking.objects.create(
            person=self.person, date=date(2026, 3, 2), tardiness_minutes=20, status='PENDING'
        )
        # Exception on employee's own record (own_person)
        own_exc = AbnormalClocking.objects.create(
            person=own_person, date=date(2026, 3, 2), tardiness_minutes=15, status='PENDING'
        )

        # 1. Unauthenticated request -> 401
        self.client.force_authenticate(user=None)
        res_unauth = self.client.get('/api/attendance/exceptions/')
        self.assertEqual(res_unauth.status_code, status.HTTP_401_UNAUTHORIZED)

        # 2. Regular employee without view permission listing all exceptions -> 403
        self.client.force_authenticate(user=emp_user)
        res_list = self.client.get('/api/attendance/exceptions/')
        self.assertEqual(res_list.status_code, status.HTTP_403_FORBIDDEN)

        # 3. Regular employee justifying someone else's record -> 403
        res_justify_other = self.client.post(f'/api/attendance/exceptions/{other_exc.id}/justify/', {
            'status': 'EXCUSED',
            'reason': 'Trying to justify someone else'
        })
        self.assertEqual(res_justify_other.status_code, status.HTTP_403_FORBIDDEN)

        # 4. Regular employee self-justifying own record -> 200 OK
        res_justify_own = self.client.post(f'/api/attendance/exceptions/{own_exc.id}/justify/', {
            'status': 'EXCUSED',
            'reason': 'Clinic visit with medical certificate'
        })
        self.assertEqual(res_justify_own.status_code, status.HTTP_200_OK)
        self.assertEqual(res_justify_own.data['status'], 'EXCUSED')


class BiometricEnrollmentMigrationTests(TransactionTestCase):
    migrate_from = [('biometrics_attendance', '0002_initial')]
    migrate_to = [('biometrics_attendance', '0003_biometricenrollment')]

    def setUp(self):
        super().setUp()
        self.executor = MigrationExecutor(connection)
        self.executor.migrate(self.migrate_from)

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        super().tearDown()

    def test_backfills_legacy_person_biometric_id(self):
        Person = apps.get_model('users', 'Person')
        person = Person.objects.create(
            name='Migrated Legacy Employee',
            biometric_id='101-MIGRATED',
            status='ACTIVE',
        )

        self.executor = MigrationExecutor(connection)
        self.executor.migrate(self.migrate_to)
        new_apps = self.executor.loader.project_state(self.migrate_to).apps

        Enrollment = new_apps.get_model(
            'biometrics_attendance',
            'BiometricEnrollment',
        )
        enrollment = Enrollment.objects.get(person_id=person.pk)

        self.assertEqual(enrollment.external_biometric_id, '101-MIGRATED')
        self.assertEqual(enrollment.device_name, 'Migrated from legacy field')
        self.assertEqual(enrollment.device_id, '')
        self.assertEqual(enrollment.status, 'ENROLLED')
        self.assertTrue(enrollment.is_active)
        self.assertIsNone(enrollment.enrolled_by_id)

    def test_duplicate_legacy_biometric_id_aborts_with_clear_error(self):
        migration = importlib.import_module(
            'biometrics_attendance.migrations.0003_biometricenrollment'
        )

        class DuplicateQuerySet:
            def order_by(self, *args, **kwargs):
                return self

            def first(self):
                return {
                    'biometric_id': '101-DUPLICATE',
                    'count': 2,
                }

        class DuplicateObjects:
            def exclude(self, *args, **kwargs):
                return self

            def values(self, *args, **kwargs):
                return self

            def annotate(self, *args, **kwargs):
                return self

            def filter(self, *args, **kwargs):
                return DuplicateQuerySet()

        class DuplicatePerson:
            objects = DuplicateObjects()

        with self.assertRaisesRegex(
            RuntimeError,
            "Cannot backfill biometric enrollments: duplicate legacy "
            "Person.biometric_id '101-DUPLICATE' is assigned to 2 persons.",
        ):
            migration.assert_no_duplicate_legacy_biometric_ids(DuplicatePerson)


class ActiveBiometricEnrollmentDatabaseConstraintTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        super().setUp()
        self.person_one = Person.objects.create(
            name='Constraint Test Person One',
            status='ACTIVE',
        )
        self.person_two = Person.objects.create(
            name='Constraint Test Person Two',
            status='ACTIVE',
        )

    def test_duplicate_active_external_id_raises_integrity_error(self):
        BiometricEnrollment.objects.create(
            person=self.person_one,
            external_biometric_id='DB-DUPLICATE-ID',
            status='ENROLLED',
            is_active=True,
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            BiometricEnrollment.objects.create(
                person=self.person_two,
                external_biometric_id='DB-DUPLICATE-ID',
                status='ENROLLED',
                is_active=True,
            )

    def test_duplicate_active_person_raises_integrity_error(self):
        BiometricEnrollment.objects.create(
            person=self.person_one,
            external_biometric_id='PERSON-FIRST-ID',
            status='ENROLLED',
            is_active=True,
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            BiometricEnrollment.objects.create(
                person=self.person_one,
                external_biometric_id='PERSON-SECOND-ID',
                status='ENROLLED',
                is_active=True,
            )

    def test_revoked_then_new_active_external_id_is_allowed(self):
        BiometricEnrollment.objects.create(
            person=self.person_one,
            external_biometric_id='REVOKED-THEN-ACTIVE-ID',
            status='REVOKED',
            is_active=False,
        )

        active = BiometricEnrollment.objects.create(
            person=self.person_two,
            external_biometric_id='REVOKED-THEN-ACTIVE-ID',
            status='ENROLLED',
            is_active=True,
        )

        self.assertEqual(active.status, 'ENROLLED')
        self.assertTrue(active.is_active)
