from datetime import date, time, datetime
from decimal import Decimal
import io
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase
from rest_framework import status
from users.models import User, Role, Person
from scheduling.models import Shift
from biometrics_attendance.models import (
    BiometricImportBatch, AttendanceRecord, AbnormalClocking
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
        self.ojt = Person.objects.create(
            biometric_id='102', name='Sarah Intern', person_type='OJT',
            base_rate=Decimal('0.00'), rendered_ojt_hours=Decimal('10.00'), status='ACTIVE'
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

