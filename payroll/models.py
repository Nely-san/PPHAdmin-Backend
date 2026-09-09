import uuid
from django.db import models
from settings.models import BaseModel

class PayrollRecord(BaseModel):
    """
    Consolidated Cutoff Payroll Record per Employee / Intern.
    """
    STATUS_CHOICES = [
        ('DRAFT', 'Draft Computation'),
        ('APPROVED', 'Approved by Payroll Officer'),
        ('PAID', 'Paid / Distributed'),
        ('LOCKED', 'Finalized & Locked'),
    ]

    person = models.ForeignKey('users.Person', on_delete=models.CASCADE, related_name='payroll_records')
    cutoff_start = models.DateField(db_index=True)
    cutoff_end = models.DateField(db_index=True)
    gross_pay = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    net_pay = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT', db_index=True)

    class Meta:
        db_table = 'payroll_records'
        unique_together = ('person', 'cutoff_start', 'cutoff_end')
        ordering = ['-cutoff_start', 'person']

    def __str__(self):
        return f"{self.person.name} ({self.cutoff_start} to {self.cutoff_end}): Net PHP {self.net_pay} [{self.status}]"


class PayrollItem(models.Model):
    """
    Itemized Earnings and Deduction lines attached to a PayrollRecord.
    """
    ITEM_TYPE_CHOICES = [
        ('EARNING', 'Taxable / Basic Earning'),
        ('DEDUCTION', 'Tax / Government / Tardiness Deduction'),
        ('ADVANCE', 'Cash Advance Amortization'),
        ('REIMBURSEMENT', 'Non-Taxable Expense Reimbursement'),
        ('ALLOWANCE', 'Non-Taxable Allowance'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payroll_record = models.ForeignKey(PayrollRecord, on_delete=models.CASCADE, related_name='items')
    item_type = models.CharField(max_length=30, choices=ITEM_TYPE_CHOICES)
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    class Meta:
        db_table = 'payroll_items'

    def __str__(self):
        return f"[{self.item_type}] {self.description}: PHP {self.amount}"


class SalaryRateAdjustment(BaseModel):
    """
    Personnel Base Rate Change Audit History.
    """
    ADJUSTMENT_TYPE_CHOICES = [
        ('PROMOTION', 'Merit Promotion'),
        ('REGULARIZATION', 'Employment Regularization'),
        ('ANNUAL_INCREASE', 'Annual Salary Increment'),
        ('MERIT', 'Merit Increase'),
        ('BULK_INCREMENT', 'Department Bulk Adjustment'),
    ]

    person = models.ForeignKey('users.Person', on_delete=models.CASCADE, related_name='rate_adjustments')
    old_rate = models.DecimalField(max_digits=10, decimal_places=2)
    new_rate = models.DecimalField(max_digits=10, decimal_places=2)
    old_rate_type = models.CharField(max_length=20, choices=[('DAILY', 'Daily Paid'), ('MONTHLY', 'Monthly Paid'), ('HOURLY', 'Hourly Paid')], default='DAILY')
    new_rate_type = models.CharField(max_length=20, choices=[('DAILY', 'Daily Paid'), ('MONTHLY', 'Monthly Paid'), ('HOURLY', 'Hourly Paid')], default='DAILY')
    adjustment_type = models.CharField(max_length=30, choices=ADJUSTMENT_TYPE_CHOICES, default='MERIT')
    reason = models.TextField()
    adjusted_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True)
    effective_date = models.DateField(db_index=True)

    class Meta:
        db_table = 'salary_rate_adjustments'
        ordering = ['-effective_date']

    def __str__(self):
        return f"{self.person.name}: PHP {self.old_rate} -> {self.new_rate} ({self.adjustment_type})"
