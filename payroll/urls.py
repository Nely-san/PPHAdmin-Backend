from django.urls import path, include
from rest_framework.routers import DefaultRouter
from payroll.views import PayrollRecordViewSet, SalaryRateAdjustmentViewSet

router = DefaultRouter()
router.register(r'payroll/rate-adjustments', SalaryRateAdjustmentViewSet, basename='payroll-rate-adjustments')
router.register(r'payroll/base-rates', SalaryRateAdjustmentViewSet, basename='payroll-base-rates')
router.register(r'payroll', PayrollRecordViewSet, basename='payroll')

urlpatterns = [
    path('payroll/my-payslips/history/', PayrollRecordViewSet.as_view({'get': 'my_payslips_history'}), name='my-payslips-history'),
    path('payroll/my-payslips/history', PayrollRecordViewSet.as_view({'get': 'my_payslips_history'}), name='my-payslips-history-no-slash'),
    path('payroll/my-payslips/', PayrollRecordViewSet.as_view({'get': 'my_payslips'}), name='my-payslips'),
    path('payroll/my-payslips', PayrollRecordViewSet.as_view({'get': 'my_payslips'}), name='my-payslips-no-slash'),
    path('', include(router.urls)),
]
