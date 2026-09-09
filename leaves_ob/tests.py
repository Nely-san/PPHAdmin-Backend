from datetime import date
from rest_framework.test import APITestCase
from rest_framework import status
from users.models import User, Role, Person
from leaves_ob.models import LeaveOBApplication
from biometrics_attendance.models import AttendanceRecord
from scheduling.models import Schedule

class LeavesOBTests(APITestCase):
    def setUp(self):
        self.role, _ = Role.objects.get_or_create(code='HR_ADMIN', defaults={'name': 'HR Admin'})
        self.user = User.objects.create_user(username='leave_approver', password='password123', role=self.role)
        self.client.force_authenticate(user=self.user)

        self.person = Person.objects.create(name='Jane Vacationer', status='ACTIVE', base_rate=750.00)

    def test_file_and_approve_leave_application(self):
        # 1. File Leave Application
        res = self.client.post('/api/leaves-ob/', {
            'person': str(self.person.id),
            'request_type': 'VACATION_LEAVE',
            'start_date': '2026-04-10',
            'end_date': '2026-04-12',
            'total_days': 3.0,
            'reason': 'Family vacation in Palawan'
        })
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        app_id = res.data['id']
        self.assertEqual(res.data['status'], 'PENDING')

        # 2. Approve Application
        res2 = self.client.post(f'/api/leaves-ob/{app_id}/action/', {
            'action': 'APPROVED',
            'remarks': 'Approved. Enjoy your vacation!'
        })
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.assertEqual(res2.data['status'], 'APPROVED')

        # 3. Verify automatic attendance sync
        rec = AttendanceRecord.objects.filter(person=self.person, date=date(2026, 4, 10)).first()
        self.assertIsNotNone(rec)
        self.assertEqual(rec.status, 'ON_LEAVE')
        self.assertTrue(rec.is_leave)

        # 4. Verify schedule sync
        sched = Schedule.objects.filter(person=self.person, date=date(2026, 4, 11)).first()
        self.assertIsNotNone(sched)
        self.assertEqual(sched.schedule_type, 'LEAVE')
