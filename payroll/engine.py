from decimal import Decimal, ROUND_HALF_UP
from datetime import date
from django.db import transaction
from users.models import Person
from biometrics_attendance.models import AttendanceRecord
from payroll.models import PayrollRecord, PayrollItem, SalaryRateAdjustment

def round_curr(val):
    if not isinstance(val, Decimal):
        val = Decimal(str(val or 0.00))
    return val.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

def calculate_sss(monthly_salary):
    """
    Standard SSS Philippine Employee Contribution calculation (approx 4.5% employee share capped at ~1,350 PHP).
    Semi-monthly cutoff uses half the deduction.
    """
    ms = Decimal(str(monthly_salary))
    if ms < Decimal('4250'):
        monthly_ee = Decimal('180.00')
    elif ms >= Decimal('29750'):
        monthly_ee = Decimal('1350.00')
    else:
        monthly_ee = ms * Decimal('0.045')
    return round_curr(monthly_ee / Decimal('2'))

def calculate_philhealth(monthly_salary):
    """
    Standard PhilHealth Philippine Employee Contribution (5% total divided equally = 2.5% EE share).
    Semi-monthly cutoff uses half the deduction.
    """
    ms = Decimal(str(monthly_salary))
    capped_ms = min(max(ms, Decimal('10000')), Decimal('100000'))
    monthly_ee = capped_ms * Decimal('0.025')
    return round_curr(monthly_ee / Decimal('2'))

def calculate_pagibig(monthly_salary):
    """
    Standard Pag-IBIG Mandatory Contribution (PHP 100 or PHP 200 / month = PHP 100 / cutoff).
    """
    ms = Decimal(str(monthly_salary))
    if ms > Decimal('1500'):
        return Decimal('100.00')
    return Decimal('50.00')


def calculate_person_cutoff_payroll(
    person,
    cutoff_start,
    cutoff_end,
    method='OPTION_1',
    working_days_in_cutoff=12,
    include_government_deductions=True,
    include_tardiness=True,
    include_sss=True,
    include_philhealth=True,
    include_pagibig=True
):
    """
    Calculates gross pay, deductions (tardiness, SSS, PhilHealth, Pag-IBIG), and net pay
    for an individual person for a specified cutoff period.
    """
    records = AttendanceRecord.objects.filter(
        person=person,
        date__gte=cutoff_start,
        date__lte=cutoff_end,
        is_archived=False
    )

    total_actual_hours = Decimal('0.00')
    total_tardiness_mins = 0
    total_ot_mins = 0
    days_present = 0
    leave_days = 0

    for r in records:
        total_actual_hours += r.actual_hours
        total_tardiness_mins += r.tardiness_minutes
        total_ot_mins += r.overtime_regular_minutes
        if r.status in ('PRESENT', 'LATE', 'HALF_DAY', 'BUSINESS_TRIP'):
            days_present += 1
        elif r.status == 'ON_LEAVE':
            leave_days += 1

    rate_type = person.rate_type or 'DAILY'
    base_rate = person.base_rate or Decimal('0.00')

    basic_pay = Decimal('0.00')
    hourly_rate = Decimal('0.00')
    monthly_equivalent = Decimal('0.00')

    # Basic Salary Calculation
    if rate_type == 'DAILY':
        hourly_rate = round_curr(base_rate / Decimal('8.00'))
        monthly_equivalent = base_rate * Decimal('22')
        if method == 'OPTION_1':
            # Option 1: Total Minutes (High Precision)
            total_worked_mins = int(total_actual_hours * Decimal('60'))
            basic_pay = round_curr((Decimal(total_worked_mins) * base_rate) / Decimal('480'))
        else:
            # Option 2: Decimal Hours
            basic_pay = round_curr(hourly_rate * total_actual_hours)

    elif rate_type == 'MONTHLY':
        hourly_rate = round_curr(base_rate / (Decimal(working_days_in_cutoff * 2) * Decimal('8.00')))
        monthly_equivalent = base_rate
        # Worked Days = total_hours / 8
        worked_days = total_actual_hours / Decimal('8.00')
        cutoff_basic = base_rate / Decimal('2.00')
        basic_pay = round_curr((worked_days * cutoff_basic) / Decimal(working_days_in_cutoff))

    elif rate_type == 'HOURLY':
        hourly_rate = base_rate
        monthly_equivalent = base_rate * Decimal('160')
        basic_pay = round_curr(base_rate * total_actual_hours)

    # Overtime Earning (1.25x hourly rate)
    ot_pay = Decimal('0.00')
    if total_ot_mins > 0 and hourly_rate > 0:
        ot_hours = Decimal(total_ot_mins) / Decimal('60')
        ot_pay = round_curr(hourly_rate * Decimal('1.25') * ot_hours)

    gross_pay = basic_pay + ot_pay

    # Deductions
    tardiness_deduction = Decimal('0.00')
    if include_tardiness and total_tardiness_mins > 0 and hourly_rate > 0:
        tardiness_deduction = round_curr((hourly_rate / Decimal('60')) * Decimal(total_tardiness_mins))

    # Statutory Deductions (only apply to Regular Employees with non-zero gross and enabled statutory deductions)
    sss_deduction = Decimal('0.00')
    philhealth_deduction = Decimal('0.00')
    pagibig_deduction = Decimal('0.00')

    person_has_gov = getattr(person, 'has_government_deductions', True)
    if include_government_deductions and person_has_gov and person.person_type == 'EMPLOYEE' and gross_pay > 0:
        if include_sss:
            sss_deduction = calculate_sss(monthly_equivalent)
        if include_philhealth:
            philhealth_deduction = calculate_philhealth(monthly_equivalent)
        if include_pagibig:
            pagibig_deduction = calculate_pagibig(monthly_equivalent)

    total_deductions = tardiness_deduction + sss_deduction + philhealth_deduction + pagibig_deduction
    net_pay = max(Decimal('0.00'), gross_pay - total_deductions)

    # Items Breakdown list
    items = []
    items.append({
        'item_type': 'EARNING',
        'description': f'Basic Salary ({total_actual_hours} hrs @ PHP {base_rate}/{rate_type.lower()})',
        'amount': basic_pay
    })

    if ot_pay > 0:
        items.append({
            'item_type': 'EARNING',
            'description': f'Overtime Pay ({total_ot_mins} mins @ 1.25x)',
            'amount': ot_pay
        })

    if tardiness_deduction > 0:
        items.append({
            'item_type': 'DEDUCTION',
            'description': f'Tardiness Deduction ({total_tardiness_mins} mins)',
            'amount': tardiness_deduction
        })

    if sss_deduction > 0:
        items.append({
            'item_type': 'DEDUCTION',
            'description': 'SSS Contribution (Employee Share)',
            'amount': sss_deduction
        })

    if philhealth_deduction > 0:
        items.append({
            'item_type': 'DEDUCTION',
            'description': 'PhilHealth Contribution (Employee Share)',
            'amount': philhealth_deduction
        })

    if pagibig_deduction > 0:
        items.append({
            'item_type': 'DEDUCTION',
            'description': 'Pag-IBIG / HDMF Contribution',
            'amount': pagibig_deduction
        })

    return {
        'person': person,
        'cutoff_start': cutoff_start,
        'cutoff_end': cutoff_end,
        'gross_pay': gross_pay,
        'total_deductions': total_deductions,
        'net_pay': net_pay,
        'total_actual_hours': total_actual_hours,
        'days_present': days_present,
        'items': items
    }


def run_cutoff_payroll_batch(
    cutoff_start,
    cutoff_end,
    method='OPTION_1',
    person_ids=None,
    include_government_deductions=True,
    include_tardiness=True,
    include_sss=True,
    include_philhealth=True,
    include_pagibig=True
):
    """
    Executes batch payroll calculation across active personnel with positive base rates for a cutoff window.
    Personnel with base_rate = 0 (such as unpaid OJTs) are excluded.
    """
    persons = Person.objects.filter(is_archived=False, status='ACTIVE', base_rate__gt=Decimal('0.00'))
    if person_ids:
        persons = persons.filter(id__in=person_ids)

    results = []
    with transaction.atomic():
        for person in persons:
            calc = calculate_person_cutoff_payroll(
                person=person,
                cutoff_start=cutoff_start,
                cutoff_end=cutoff_end,
                method=method,
                include_government_deductions=include_government_deductions,
                include_tardiness=include_tardiness,
                include_sss=include_sss,
                include_philhealth=include_philhealth,
                include_pagibig=include_pagibig
            )

            # Update or create PayrollRecord
            payroll_rec, _ = PayrollRecord.objects.update_or_create(
                person=person,
                cutoff_start=cutoff_start,
                cutoff_end=cutoff_end,
                defaults={
                    'gross_pay': calc['gross_pay'],
                    'total_deductions': calc['total_deductions'],
                    'net_pay': calc['net_pay'],
                    'status': 'DRAFT',
                    'is_archived': False
                }
            )

            # Re-create line items
            payroll_rec.items.all().delete()
            for itm in calc['items']:
                PayrollItem.objects.create(
                    payroll_record=payroll_rec,
                    item_type=itm['item_type'],
                    description=itm['description'],
                    amount=itm['amount']
                )

            # Link attendance records to this payroll record
            AttendanceRecord.objects.filter(
                person=person,
                date__gte=cutoff_start,
                date__lte=cutoff_end
            ).update(payroll_record=payroll_rec)

            results.append(payroll_rec)

    return results


def lock_cutoff_payroll(cutoff_start, cutoff_end):
    """
    Finalizes and locks all payroll records and their corresponding daily attendance timecards.
    """
    with transaction.atomic():
        updated_records = PayrollRecord.objects.filter(
            cutoff_start=cutoff_start,
            cutoff_end=cutoff_end,
            is_archived=False
        ).update(status='LOCKED')

        # Freeze attendance records
        AttendanceRecord.objects.filter(
            date__gte=cutoff_start,
            date__lte=cutoff_end,
            is_archived=False
        ).update(is_locked=True)

    return updated_records
