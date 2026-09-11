from django.urls import path, include
from rest_framework.routers import DefaultRouter
from biometrics_attendance.views import (
    BiometricImportViewSet, AttendanceRecordViewSet,
    AbnormalClockingViewSet, AttendancePeriodViewSet, AttendanceSummaryViewSet
)

router = DefaultRouter()
router.register(r'biometrics', BiometricImportViewSet, basename='biometric-import')
router.register(r'attendance/exceptions', AbnormalClockingViewSet, basename='attendance-exception')
router.register(r'attendance/periods', AttendancePeriodViewSet, basename='attendance-period')
router.register(r'attendance/summaries', AttendanceSummaryViewSet, basename='attendance-summary')
router.register(r'attendance', AttendanceRecordViewSet, basename='attendance')

urlpatterns = [
    path('', include(router.urls)),
]
