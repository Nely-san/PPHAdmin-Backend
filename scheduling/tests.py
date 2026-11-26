from datetime import date, timedelta
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from users.models import User, Role, Person, PagePermission
from scheduling.models import Shift, Schedule

class SchedulingTests(APITestCase):
    def setUp(self):
        self.role, _ = Role.objects.get_or_create(code='ADMIN', defaults={'name': 'Admin'})
        perm_sched, _ = PagePermission.objects.get_or_create(
            code='attendance:schedules:edit',
            defaults={'name': 'Schedules (Edit)', 'module': 'ATTENDANCE'}
        )
        self.role.permissions.add(perm_sched)
        self.user = User.objects.create_user(
            username='sched_admin', password='password123', role=self.role, is_active=True, approval_status='APPROVED'
        )
        self.client.force_authenticate(user=self.user)

        self.person1 = Person.objects.create(name='Alice Tester', base_rate=500.00, status='ACTIVE')
        self.person2 = Person.objects.create(name='Bob Tester', base_rate=600.00, status='ACTIVE')

    def test_shift_crud_and_seed(self):
        # 1. Seed defaults
        res = self.client.post('/api/shifts/seed-defaults/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(Shift.objects.filter(code='DAY').exists())

        # 2. Create custom shift
        res = self.client.post('/api/shifts/', {
            'code': 'CUSTOM_1',
            'name': 'Custom Early Shift',
            'start_time': '07:00',
            'end_time': '16:00',
            'work_hours': 8.00,
            'grace_period_mins': 15
        })
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['code'], 'CUSTOM_1')

    def test_batch_schedule_assignment(self):
        shift = Shift.objects.create(
            code='DAY_TEST', name='Day Shift', start_time='09:00', end_time='18:00', work_hours=8.00
        )
        today = date.today()
        end = today + timedelta(days=4)

        res = self.client.post('/api/schedules/batch-assign/', {
            'person_ids': [str(self.person1.id), str(self.person2.id)],
            'start_date': today.isoformat(),
            'end_date': end.isoformat(),
            'shift_id': str(shift.id),
            'schedule_type': 'REGULAR',
            'note': 'Automated test roster'
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['success'], True)
        self.assertEqual(Schedule.objects.filter(shift=shift).count(), 10)


class SchedulingPermissionsSecurityTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin_role, _ = Role.objects.get_or_create(
            code='ADMIN', defaults={'name': 'Admin', 'is_system_role': True}
        )
        self.employee_role, _ = Role.objects.get_or_create(
            code='EMPLOYEE', defaults={'name': 'Employee', 'is_system_role': False}
        )

        perm_edit, _ = PagePermission.objects.get_or_create(
            code='attendance:schedules:edit',
            defaults={'name': 'Schedules (Edit)', 'module': 'ATTENDANCE'}
        )
        self.admin_role.permissions.add(perm_edit)

        self.admin_user, _ = User.objects.get_or_create(
            username='sched_admin_user',
            defaults={
                'email': 'admin@test.com',
                'role': self.admin_role,
                'approval_status': 'APPROVED',
                'is_active': True,
            }
        )
        self.employee_user, _ = User.objects.get_or_create(
            username='sched_employee_user',
            defaults={
                'email': 'employee@test.com',
                'role': self.employee_role,
                'approval_status': 'APPROVED',
                'is_active': True,
            }
        )

        self.person = Person.objects.create(name='Schedule Test Person', base_rate=500.00, status='ACTIVE')

    def test_shift_write_denied_for_employee(self):
        # authenticate as a user with role code 'EMPLOYEE' and no
        # attendance:schedules:edit grant.
        # POST /api/shifts/ with a minimal valid body -> 403.
        # GET /api/shifts/ -> 200 (read stays open to any authenticated user).
        self.client.force_authenticate(user=self.employee_user)
        response = self.client.post('/api/shifts/', {
            'name': 'Denied Shift',
            'code': 'DENIED_SHIFT',
            'start_time': '09:00',
            'end_time': '18:00',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data.get('detail'), "You do not have permission to create shifts.")

        get_res = self.client.get('/api/shifts/')
        self.assertEqual(get_res.status_code, status.HTTP_200_OK)

    def test_shift_write_allowed_for_admin(self):
        # authenticate as a user with role code 'ADMIN' (has
        # attendance:schedules:edit today).
        # POST /api/shifts/ with a minimal valid body -> 201.
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post('/api/shifts/', {
            'name': 'Admin Allowed Shift',
            'code': 'ADM_SHIFT',
            'start_time': '09:00',
            'end_time': '18:00',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_schedule_write_denied_for_employee(self):
        # authenticate as a user with role code 'EMPLOYEE' and no
        # attendance:schedules:edit grant.
        # POST /api/schedules/ with a minimal valid body -> 403.
        # GET /api/schedules/ -> 200 (read stays open to any authenticated user).
        self.client.force_authenticate(user=self.employee_user)
        response = self.client.post('/api/schedules/', {
            'person': str(self.person.id),
            'date': '2026-12-01',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data.get('detail'), "You do not have permission to create schedules.")

        get_res = self.client.get('/api/schedules/')
        self.assertEqual(get_res.status_code, status.HTTP_200_OK)

    def test_schedule_write_allowed_for_admin(self):
        # authenticate as a user with role code 'ADMIN' (has
        # attendance:schedules:edit today).
        # POST /api/schedules/ with a minimal valid body -> 201.
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post('/api/schedules/', {
            'person': str(self.person.id),
            'date': '2026-12-02',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_batch_assign_denied_for_employee(self):
        # authenticate as EMPLOYEE. POST /api/schedules/batch-assign/ with a
        # minimal valid body (person ids, date range, shift id if required).
        # Expect 403.
        self.client.force_authenticate(user=self.employee_user)
        response = self.client.post('/api/schedules/batch-assign/', {
            'person_ids': [str(self.person.id)],
            'start_date': '2026-12-01',
            'end_date': '2026-12-02',
            'schedule_type': 'REGULAR',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data.get('detail'), "You do not have permission to batch assign schedules.")

    def test_batch_assign_allowed_for_admin(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post('/api/schedules/batch-assign/', {
            'person_ids': [str(self.person.id)],
            'start_date': '2026-12-01',
            'end_date': '2026-12-02',
            'schedule_type': 'REGULAR',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get('success'), True)

    def test_seed_defaults_denied_for_employee(self):
        # authenticate as EMPLOYEE. POST /api/shifts/seed-defaults/.
        # Expect 403.
        self.client.force_authenticate(user=self.employee_user)
        response = self.client.post('/api/shifts/seed-defaults/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data.get('detail'), "You do not have permission to seed shift defaults.")

    def test_seed_defaults_allowed_for_admin(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post('/api/shifts/seed-defaults/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


