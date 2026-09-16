from django.contrib import admin
from django.urls import path, include
from config.health import health_check_view

urlpatterns = [
    path('healthz', health_check_view, name='healthz'),
    path('api/health/', health_check_view, name='health_check'),
    path('api/health', health_check_view, name='health_check_no_slash'),
    path('admin/', admin.site.urls),
    path('api/', include('users.urls')),
    path('api/', include('settings.urls')),
    path('api/', include('organization.urls')),
    path('api/', include('audit.urls')),
    path('api/', include('scheduling.urls')),
    path('api/', include('biometrics_attendance.urls')),
    path('api/', include('leaves_ob.urls')),
    path('api/', include('payroll.urls')),
]
