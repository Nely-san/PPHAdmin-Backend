from datetime import date
from decimal import Decimal
from rest_framework.test import APITestCase
from rest_framework import status
from users.models import User, Role, Person
from biometrics_attendance.models import AttendanceRecord
from payroll.models import PayrollRecord, PayrollItem, SalaryRateAdjustment
from payroll.engine import calculate_person_cutoff_payroll

class PayrollTests(APITestCase):
    def setUp(self):
        self.role, _ = Role.objects.get_or_create(code='PAYROLL_ADMIN', defaults={'name': 'Payroll Admin'})
        self.user = User.objects.create_user(username='payroll_tester', password='password123', role=self.role)
        self.client.force_authenticate(user=self.user)

        self.daily_emp = Person.objects.create(
            name='Daily Worker', person_type='EMPLOYEE', rate_type='DAILY',
            base_rate=Decimal('600.00'), status='ACTIVE'
        )

        # Create 5 days of 8-hour attendance
        for day in range(1, 6):
            AttendanceRecord.objects.create(
                person=self.daily_emp,
                date=date(2026, 3, day),
                actual_hours=Decimal('8.00'),
                tardiness_minutes=0,
                overtime_regular_minutes=60 if day == 5 else 0,
                status='PRESENT'
            )

    def test_payroll_calculation_option_1_and_2(self):
        cutoff_start = date(2026, 3, 1)
        cutoff_end = date(2026, 3, 15)

        # Option 1 (Minutes)
        res1 = calculate_person_cutoff_payroll(
            person=self.daily_emp,
            cutoff_start=cutoff_start,
            cutoff_end=cutoff_end,
            method='OPTION_1'
        )
        self.assertGreater(res1['gross_pay'], Decimal('3000.00'))
        self.assertGreater(res1['net_pay'], Decimal('0.00'))

        # Option 2 (Decimal Hours)
        res2 = calculate_person_cutoff_payroll(
            person=self.daily_emp,
            cutoff_start=cutoff_start,
            cutoff_end=cutoff_end,
            method='OPTION_2'
        )
        self.assertGreater(res2['gross_pay'], Decimal('3000.00'))

    def test_batch_calculate_and_lock_endpoint(self):
        res = self.client.post('/api/payroll/calculate/', {
            'cutoff_start': '2026-03-01',
            'cutoff_end': '2026-03-15',
            'person_ids': [str(self.daily_emp.id)],
            'method': 'OPTION_1'
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['success'], True)
        self.assertEqual(res.data['count'], 1)

        # Lock Cutoff
        res_lock = self.client.post('/api/payroll/lock/', {
            'cutoff_start': '2026-03-01',
            'cutoff_end': '2026-03-15'
        })
        self.assertEqual(res_lock.status_code, status.HTTP_200_OK)
        self.assertEqual(res_lock.data['success'], True)

        # Verify attendance records are frozen
        locked_rec = AttendanceRecord.objects.filter(person=self.daily_emp, date=date(2026, 3, 1)).first()
        self.assertTrue(locked_rec.is_locked)

    def test_base_rate_adjustments(self):
        # Single adjustment
        res = self.client.post('/api/payroll/base-rates/adjust/', {
            'person_id': str(self.daily_emp.id),
            'new_rate': 650.00,
            'new_rate_type': 'DAILY',
            'adjustment_type': 'MERIT',
            'reason': 'Exemplary project delivery',
            'effective_date': '2026-04-01'
        })
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.daily_emp.refresh_from_db()
        self.assertEqual(self.daily_emp.base_rate, Decimal('650.00'))

        # Bulk adjustment (10% increase)
        res2 = self.client.post('/api/payroll/base-rates/bulk-adjust/', {
            'person_ids': [str(self.daily_emp.id)],
            'adjustment_type': 'PERCENTAGE',
            'adjustment_value': 10.00,
            'reason': 'Annual Company-wide Increment',
            'effective_date': '2026-05-01'
        })
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.daily_emp.refresh_from_db()
        self.assertEqual(self.daily_emp.base_rate, Decimal('715.00'))
