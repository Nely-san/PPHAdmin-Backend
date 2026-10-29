from datetime import date
from rest_framework.test import APITestCase
from rest_framework import status
from users.models import User, Role, Person, PagePermission
from leaves_ob.models import LeaveOBApplication, OvertimeApplication
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

    def test_unauthorized_user_cannot_approve_leave(self):
        emp_role, _ = Role.objects.get_or_create(code='EMPLOYEE', defaults={'name': 'Employee'})
        emp_user = User.objects.create_user(username='unauthorized_emp', password='password123', role=emp_role)

        app = LeaveOBApplication.objects.create(
            person=self.person,
            request_type='VACATION_LEAVE',
            start_date=date(2026, 4, 15),
            end_date=date(2026, 4, 16),
            total_days=2.0,
            reason='Trip',
            status='PENDING'
        )

        # Employee (no attendance:leaves:edit) -> 403
        self.client.force_authenticate(user=emp_user)
        res = self.client.post(f'/api/leaves-ob/{app.id}/action/', {
            'action': 'APPROVED',
            'remarks': 'Unauthorized approval'
        })
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        # Unauthenticated request -> 401
        self.client.force_authenticate(user=None)
        res_unauth = self.client.post(f'/api/leaves-ob/{app.id}/action/', {
            'action': 'APPROVED',
            'remarks': 'Unauthenticated approval'
        })
        self.assertEqual(res_unauth.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_leave_action_denied_for_parent_view_only(self):
        """
        Parent-view-only denied edit: a user with 'attendance:view' (no attendance:leaves:edit,
        no attendance:edit, and not a manager/admin role) must be denied when attempting to
        POST /api/leaves-ob/{id}/action/. Expect HTTP 403 Forbidden.
        """
        perm_view, _ = PagePermission.objects.get_or_create(
            code='attendance:view',
            defaults={'name': 'Attendance View', 'module': 'HR'}
        )
        emp_role, _ = Role.objects.get_or_create(code='EMPLOYEE', defaults={'name': 'Employee'})
        user = User.objects.create_user(username='view_only_user', password='password123', role=emp_role)
        user.custom_permissions.add(perm_view)

        app = LeaveOBApplication.objects.create(
            person=self.person,
            request_type='VACATION_LEAVE',
            start_date=date(2026, 4, 20),
            end_date=date(2026, 4, 21),
            total_days=2.0,
            reason='Rest',
            status='PENDING'
        )

        self.client.force_authenticate(user=user)
        res = self.client.post(f'/api/leaves-ob/{app.id}/action/', {
            'action': 'APPROVED',
            'remarks': 'Should fail'
        })
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_leave_action_allowed_for_bare_parent_module(self):
        """
        Bare parent grants edit (pinning behavior): a user with bare 'attendance' (parent granted,
        no sub-action code) POSTing /api/leaves-ob/{id}/action/ receives HTTP 200 OK.
        Under PPHAdmin RBAC, granting top-level module ownership conveys administrative
        authority over sub-features unless granularly scoped.
        """
        perm_parent, _ = PagePermission.objects.get_or_create(
            code='attendance',
            defaults={'name': 'Attendance', 'module': 'HR'}
        )
        emp_role, _ = Role.objects.get_or_create(code='EMPLOYEE', defaults={'name': 'Employee'})
        user = User.objects.create_user(username='bare_parent_user', password='password123', role=emp_role)
        user.custom_permissions.add(perm_parent)

        app = LeaveOBApplication.objects.create(
            person=self.person,
            request_type='VACATION_LEAVE',
            start_date=date(2026, 4, 22),
            end_date=date(2026, 4, 23),
            total_days=2.0,
            reason='Rest',
            status='PENDING'
        )

        self.client.force_authenticate(user=user)
        res = self.client.post(f'/api/leaves-ob/{app.id}/action/', {
            'action': 'APPROVED',
            'remarks': 'Approved via bare parent permission'
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['status'], 'APPROVED')

    def test_file_and_approve_overtime_application(self):
        # 1. File Overtime Application
        res = self.client.post('/api/overtime/', {
            'person': str(self.person.id),
            'date': '2026-04-10',
            'hours': 3.5,
            'reason': 'Inventory audit completion'
        })
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        ot_id = res.data['id']
        self.assertEqual(res.data['status'], 'PENDING')
        self.assertEqual(float(res.data['hours']), 3.5)

        # 2. Approve Application
        res2 = self.client.post(f'/api/overtime/{ot_id}/action/', {
            'action': 'APPROVED',
            'remarks': 'Approved for overtime pay.'
        })
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.assertEqual(res2.data['status'], 'APPROVED')
        self.assertEqual(res2.data['reviewed_by_username'], 'leave_approver')

    def test_unauthorized_user_cannot_approve_overtime(self):
        emp_role, _ = Role.objects.get_or_create(code='EMPLOYEE', defaults={'name': 'Employee'})
        emp_user = User.objects.create_user(username='unauthorized_ot_emp', password='password123', role=emp_role)

        app = OvertimeApplication.objects.create(
            person=self.person,
            date=date(2026, 4, 15),
            hours=2.0,
            reason='Project support',
            status='PENDING'
        )

        # Employee (no attendance:leaves:edit) -> 403
        self.client.force_authenticate(user=emp_user)
        res = self.client.post(f'/api/overtime/{app.id}/action/', {
            'action': 'APPROVED',
            'remarks': 'Unauthorized approval'
        })
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        # Unauthenticated request -> 401
        self.client.force_authenticate(user=None)
        res_unauth = self.client.post(f'/api/overtime/{app.id}/action/', {
            'action': 'APPROVED',
            'remarks': 'Unauthenticated approval'
        })
        self.assertEqual(res_unauth.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_reject_overtime_requires_remarks(self):
        app = OvertimeApplication.objects.create(
            person=self.person,
            date=date(2026, 4, 18),
            hours=4.0,
            reason='Extra shift',
            status='PENDING'
        )

        # Rejection with blank remarks -> 400
        res = self.client.post(f'/api/overtime/{app.id}/action/', {
            'action': 'REJECTED',
            'remarks': '   '
        })
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('remarks', res.data)

        # Rejection with valid remarks -> 200
        res2 = self.client.post(f'/api/overtime/{app.id}/action/', {
            'action': 'REJECTED',
            'remarks': 'Budget exceeded for the department.'
        })
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.assertEqual(res2.data['status'], 'REJECTED')

    def test_reject_leave_requires_remarks(self):
        app = LeaveOBApplication.objects.create(
            person=self.person,
            request_type='VACATION_LEAVE',
            start_date=date(2026, 4, 25),
            end_date=date(2026, 4, 26),
            total_days=2.0,
            reason='Trip',
            status='PENDING'
        )

        # Rejection with blank remarks -> 400
        res = self.client.post(f'/api/leaves-ob/{app.id}/action/', {
            'action': 'REJECTED',
            'remarks': ''
        })
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('remarks', res.data)

        # Rejection with valid remarks -> 200
        res2 = self.client.post(f'/api/leaves-ob/{app.id}/action/', {
            'action': 'REJECTED',
            'remarks': 'Manpower shortage on requested dates.'
        })
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.assertEqual(res2.data['status'], 'REJECTED')

