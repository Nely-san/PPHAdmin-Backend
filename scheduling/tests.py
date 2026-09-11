from datetime import date, timedelta
from rest_framework.test import APITestCase
from rest_framework import status
from users.models import User, Role, Person
from scheduling.models import Shift, Schedule

class SchedulingTests(APITestCase):
    def setUp(self):
        self.role, _ = Role.objects.get_or_create(code='ADMIN', defaults={'name': 'Admin'})
        self.user = User.objects.create_user(username='sched_admin', password='password123', role=self.role)
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
