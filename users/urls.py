from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from users.views import *

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='users')
router.register(r'persons', PersonViewSet, basename='persons')

urlpatterns = [
    # Authentication endpoints
    path('auth/login/', CustomLoginView.as_view(), name='auth_login'),
    path('auth/register/', register_view, name='auth_register'),
    path('auth/google-login/', GoogleLoginView.as_view(), name='auth_google_login'),
    path('auth/me/', current_user_view, name='auth_current_user'),
    path('auth/logout/', logout_view, name='auth_logout'),
    path('auth/change-password/', ChangePasswordView.as_view(), name='auth_change_password'),
    path('auth/password-reset/request/', PasswordResetRequestView.as_view(), name='auth_password_reset_request'),
    path('auth/password-reset/confirm/', PasswordResetConfirmView.as_view(), name='auth_password_reset_confirm'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='auth_token_refresh'),

    # Resource routers (users, persons)
    path('', include(router.urls)),

    # Notification endpoints
    path('notifications/', notifications_list_view, name='notifications_list'),
    path('notifications', notifications_list_view, name='notifications_list_no_slash'),
    path('notifications/unread-count', notifications_unread_count_view, name='notifications_unread_count'),
    path('notifications/unread-count/', notifications_unread_count_view, name='notifications_unread_count_slash'),
    path('notifications/read-all', notifications_mark_all_read_view, name='notifications_read_all'),
    path('notifications/read-all/', notifications_mark_all_read_view, name='notifications_read_all_slash'),
    path('notifications/<str:pk>/read', notification_mark_read_view, name='notification_mark_read'),
    path('notifications/<str:pk>/read/', notification_mark_read_view, name='notification_mark_read_slash'),
    path('notifications/preferences', notification_preferences_view, name='notification_preferences'),
    path('notifications/preferences/', notification_preferences_view, name='notification_preferences_slash'),

    # Attendance endpoints
    path('attendance/reset', attendance_reset_view, name='attendance_reset'),
    path('attendance/reset/', attendance_reset_view, name='attendance_reset_slash'),
]


