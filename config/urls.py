from django.contrib import admin
from django.urls import path, include

urlpatterns = [
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
