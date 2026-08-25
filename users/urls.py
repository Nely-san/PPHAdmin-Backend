from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (TokenObtainPairView, TokenRefreshView)
from users.views import (
    UserViewSet, 
    PersonViewSet,
    CustomLoginView,
    ChangePasswordView,
    current_user_view,
    logout_view,
    register_view
)

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='users')
router.register(r'persons', PersonViewSet, basename='persons')

urlpatterns = [
    # Auth endpoints
    path('auth/login', CustomLoginView.as_view(), name='auth_login'),
    path('auth/register', register_view, name='register'),
    path('auth/signup', register_view, name='signup'),
    path('auth/me', current_user_view, name='current_user'),
    path('auth/logout', logout_view, name='logout'),
    path('auth/change-password/', ChangePasswordView.as_view(), name='auth_change_password'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='auth_token_refresh'),

    # JWT Token endpoints
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Resource routers
    path('', include(router.urls)),
]

