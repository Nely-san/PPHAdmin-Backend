from django.contrib import admin
from payroll.models import PayrollRecord, PayrollItem, SalaryRateAdjustment

class PayrollItemInline(admin.TabularInline):
    model = PayrollItem
    extra = 0

@admin.register(PayrollRecord)
class PayrollRecordAdmin(admin.ModelAdmin):
    list_display = ('person', 'cutoff_start', 'cutoff_end', 'gross_pay', 'total_deductions', 'net_pay', 'status')
    list_filter = ('status', 'cutoff_start')
    search_fields = ('person__name',)
    inlines = [PayrollItemInline]

@admin.register(SalaryRateAdjustment)
class SalaryRateAdjustmentAdmin(admin.ModelAdmin):
    list_display = ('person', 'old_rate', 'new_rate', 'adjustment_type', 'effective_date', 'adjusted_by')
    list_filter = ('adjustment_type', 'effective_date')
    search_fields = ('person__name', 'reason')
