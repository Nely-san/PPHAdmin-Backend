from django.urls import path, include
from rest_framework.routers import DefaultRouter
from payroll.views import PayrollRecordViewSet, SalaryRateAdjustmentViewSet

router = DefaultRouter()
router.register(r'payroll/rate-adjustments', SalaryRateAdjustmentViewSet, basename='payroll-rate-adjustments')
router.register(r'payroll/base-rates', SalaryRateAdjustmentViewSet, basename='payroll-base-rates')
router.register(r'payroll', PayrollRecordViewSet, basename='payroll')

urlpatterns = [
    path('', include(router.urls)),
]
