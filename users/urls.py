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
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='auth_token_refresh'),

    # Resource routers (users, persons)
    path('', include(router.urls)),

    # Notification endpoints
    path('notifications/', notifications_list_view, name='notifications_list'),
    path('notifications/unread-count', notifications_unread_count_view, name='notifications_unread_count'),
]


