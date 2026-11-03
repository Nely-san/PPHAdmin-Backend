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

    def test_locked_attendance_enforcement_across_write_paths(self):
        from django.core.exceptions import ValidationError
        from leaves_ob.models import LeaveOBApplication

        # 1. Lock cutoff for March 1-15
        self.client.post('/api/payroll/calculate/', {
            'cutoff_start': '2026-03-01',
            'cutoff_end': '2026-03-15',
            'person_ids': [str(self.daily_emp.id)],
            'method': 'OPTION_1'
        })
        self.client.post('/api/payroll/lock/', {
            'cutoff_start': '2026-03-01',
            'cutoff_end': '2026-03-15'
        })

        locked_rec = AttendanceRecord.objects.filter(person=self.daily_emp, date=date(2026, 3, 1)).first()
        self.assertTrue(locked_rec.is_locked)

        # Verification: False -> True transition allowed on save()
        unlocked = AttendanceRecord.objects.create(
            person=self.daily_emp,
            date=date(2026, 4, 1),
            actual_hours=Decimal('8.00'),
            is_locked=False
        )
        unlocked.is_locked = True
        unlocked.save()  # Successfully transitions False -> True
        unlocked.refresh_from_db()
        self.assertTrue(unlocked.is_locked)

        # Write Path 1: Direct save() and delete() on locked model blocked
        locked_rec.actual_hours = Decimal('10.00')
        with self.assertRaises(ValidationError):
            locked_rec.save()

        with self.assertRaises(ValidationError):
            locked_rec.delete()

        # Write Path 2: AttendanceRecordViewSet mutation endpoints (PATCH, DELETE)
        res_patch = self.client.patch(f'/api/attendance/{locked_rec.id}/', {'actual_hours': '9.00'})
        self.assertEqual(res_patch.status_code, status.HTTP_400_BAD_REQUEST)

        res_delete = self.client.delete(f'/api/attendance/{locked_rec.id}/')
        self.assertEqual(res_delete.status_code, status.HTTP_400_BAD_REQUEST)

        # Write Path 3: Attendance field-log endpoint
        res_field = self.client.post('/api/attendance/field-log/', {
            'person_id': str(self.daily_emp.id),
            'date': '2026-03-01',
            'location': 'Site A',
            'reason': 'Field test'
        })
        self.assertEqual(res_field.status_code, status.HTTP_400_BAD_REQUEST)

        # Write Path 4: Leaves/OB approval for dates covering locked cutoff
        app = LeaveOBApplication.objects.create(
            person=self.daily_emp,
            request_type='VACATION_LEAVE',
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 3),
            reason='Family event',
            status='PENDING'
        )
        hr_role, _ = Role.objects.get_or_create(code='HR_ADMIN', defaults={'name': 'HR Admin'})
        self.user.role = hr_role
        self.user.save()
        res_approve = self.client.post(f'/api/leaves-ob/{app.id}/action/', {
            'action': 'APPROVED',
            'remarks': 'Approved by HR'
        })
        self.assertEqual(res_approve.status_code, status.HTTP_400_BAD_REQUEST)

        # Write Path 5: Post-save signal skipping locked records if application approved directly
        app.status = 'APPROVED'
        # saving should not crash and should skip updating locked records
        app.save()
        locked_rec.refresh_from_db()
        self.assertEqual(locked_rec.status, 'PRESENT')  # remains PRESENT, not overwritten to ON_LEAVE

    def test_statutory_calculations_sss_and_pagibig(self):
        from payroll.engine import calculate_sss, calculate_pagibig

        # SSS: monthly 5% capped at 1750, then /2 -> max 875/cutoff
        # Monthly 10,000 -> 500 / 2 = 250.00
        self.assertEqual(calculate_sss(10000), Decimal('250.00'))
        # Monthly 35,000 -> 1750 / 2 = 875.00
        self.assertEqual(calculate_sss(35000), Decimal('875.00'))
        # Monthly 50,000 (capped at 1750) -> 875.00
        self.assertEqual(calculate_sss(50000), Decimal('875.00'))

        # Pag-IBIG: min(monthly_salary, 10000) * 0.02 / 2 -> 50 to 100/cutoff
        # Monthly 5,000 -> 5000 * 0.02 / 2 = 50.00
        self.assertEqual(calculate_pagibig(5000), Decimal('50.00'))
        # Monthly 10,000 -> 10000 * 0.02 / 2 = 100.00
        self.assertEqual(calculate_pagibig(10000), Decimal('100.00'))
        # Monthly 25,000 -> min(25000, 10000) * 0.02 / 2 = 100.00
        self.assertEqual(calculate_pagibig(25000), Decimal('100.00'))

    def test_bir_withholding_tax_official_brackets(self):
        from payroll.engine import calculate_withholding_tax

        # Bracket 1: <= 10,417 -> 0.00
        self.assertEqual(calculate_withholding_tax(Decimal('10000.00')), Decimal('0.00'))
        self.assertEqual(calculate_withholding_tax(Decimal('10417.00')), Decimal('0.00'))

        # Bracket 2: 10,417.01 to 16,666.00 -> 15% over 10,417
        # 14,417 -> (14417 - 10417) * 0.15 = 4000 * 0.15 = 600.00
        self.assertEqual(calculate_withholding_tax(Decimal('14417.00')), Decimal('600.00'))

        # Bracket 3: 16,667.01 to 33,333.00 -> 937.50 + 20% over 16,667
        # 26,667 -> 937.50 + (26667 - 16667) * 0.20 = 937.50 + 2000.00 = 2937.50
        self.assertEqual(calculate_withholding_tax(Decimal('26667.00')), Decimal('2937.50'))

        # Bracket 4: 33,334.01 to 83,333.00 -> 4,270.70 + 25% over 33,333
        # 43,333 -> 4270.70 + (43333 - 33333) * 0.25 = 4270.70 + 2500.00 = 6770.70
        self.assertEqual(calculate_withholding_tax(Decimal('43333.00')), Decimal('6770.70'))

        # Bracket 5: 83,334.01 to 333,333.00 -> 16,770.70 + 30% over 83,333
        # 103,333 -> 16770.70 + (103333 - 83333) * 0.30 = 16770.70 + 6000.00 = 22770.70
        self.assertEqual(calculate_withholding_tax(Decimal('103333.00')), Decimal('22770.70'))

        # Bracket 6: > 333,333.00 -> 91,770.70 + 35% over 333,333
        # 353,333 -> 91770.70 + (353333 - 333333) * 0.35 = 91770.70 + 7000.00 = 98770.70
        self.assertEqual(calculate_withholding_tax(Decimal('353333.00')), Decimal('98770.70'))

    def test_sequencing_and_arrears_tracking(self):
        # High-earner employee to test withholding tax and sequencing
        salaried_emp = Person.objects.create(
            name='Salaried Worker', person_type='EMPLOYEE', rate_type='MONTHLY',
            base_rate=Decimal('50000.00'), status='ACTIVE'
        )
        for day in range(1, 13):
            AttendanceRecord.objects.create(
                person=salaried_emp,
                date=date(2026, 4, day),
                actual_hours=Decimal('8.00'),
                status='PRESENT'
            )

        calc = calculate_person_cutoff_payroll(
            person=salaried_emp,
            cutoff_start=date(2026, 4, 1),
            cutoff_end=date(2026, 4, 15),
            working_days_in_cutoff=12
        )
        # Gross = 25,000.00
        self.assertEqual(calc['gross_pay'], Decimal('25000.00'))
        # SSS: capped at 1750 / 2 = 875.00
        # PhilHealth: 50,000 * 0.025 / 2 = 625.00
        # Pag-IBIG: 10,000 * 0.02 / 2 = 100.00
        # Total statutory: 875 + 625 + 100 = 1600.00
        # Taxable base: 25,000 - 1600 = 23,400.00 (in Bracket 3)
        # Tax: 937.50 + (23400 - 16667) * 0.20 = 937.50 + 1346.60 = 2284.10
        self.assertEqual(calc['withholding_tax'], Decimal('2284.10'))
        self.assertEqual(calc['arrear_balance'], Decimal('0.00'))
        self.assertGreater(calc['net_pay'], Decimal('0.00'))

        # Bracket 4 Employee cutoff computation test:
        # Monthly Base: 100,000 -> Semi-monthly Gross: 50,000.00
        # Statutory deductions:
        #   SSS: capped at 875.00
        #   PhilHealth: 100,000 * 0.025 / 2 = 1,250.00
        #   Pag-IBIG: capped at 100.00
        #   Total statutory: 875 + 1250 + 100 = 2,225.00
        # Taxable Base: 50,000.00 - 2,225.00 = 47,775.00 (falls in Bracket 4: 33,334.01 to 83,333.00)
        # Withholding Tax: 4,270.70 + (47,775 - 33,333) * 0.25 = 4,270.70 + 3,610.50 = 7,881.20
        # Net Pay: 50,000.00 - 2,225.00 - 7,881.20 = 39,893.80
        exec_emp = Person.objects.create(
            name='Executive Worker', person_type='EMPLOYEE', rate_type='MONTHLY',
            base_rate=Decimal('100000.00'), status='ACTIVE'
        )
        for day in range(1, 13):
            AttendanceRecord.objects.create(
                person=exec_emp,
                date=date(2026, 4, day),
                actual_hours=Decimal('8.00'),
                status='PRESENT'
            )
        calc_b4 = calculate_person_cutoff_payroll(
            person=exec_emp,
            cutoff_start=date(2026, 4, 1),
            cutoff_end=date(2026, 4, 15),
            working_days_in_cutoff=12
        )
        self.assertEqual(calc_b4['gross_pay'], Decimal('50000.00'))
        self.assertEqual(calc_b4['withholding_tax'], Decimal('7881.20'))
        self.assertEqual(calc_b4['net_pay'], Decimal('39893.80'))
        self.assertEqual(calc_b4['arrear_balance'], Decimal('0.00'))

        # Test negative net pay shortfall & arrear tracking
        low_emp = Person.objects.create(
            name='Low Earner', person_type='EMPLOYEE', rate_type='DAILY',
            base_rate=Decimal('600.00'), status='ACTIVE'
        )
        # Only 1 hour worked, high tardiness, deductions exceed gross
        AttendanceRecord.objects.create(
            person=low_emp,
            date=date(2026, 4, 1),
            actual_hours=Decimal('1.00'),
            tardiness_minutes=120,
            status='PRESENT'
        )
        calc_arrear = calculate_person_cutoff_payroll(
            person=low_emp,
            cutoff_start=date(2026, 4, 1),
            cutoff_end=date(2026, 4, 15),
        )
        self.assertEqual(calc_arrear['net_pay'], Decimal('0.00'))
        self.assertGreater(calc_arrear['arrear_balance'], Decimal('0.00'))
