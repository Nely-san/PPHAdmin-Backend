from django.urls import path, include
from rest_framework.routers import DefaultRouter
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path
from rest_framework_simplejwt.views import (TokenObtainPairView, TokenRefreshView)
from .views import *
from users.views import (
    RoleViewSet, 
    PagePermissionViewSet, 
    UserViewSet, 
    PersonViewSet,
    CustomLoginView,
    current_user_view,
    logout_view,
    register_view
)

router = DefaultRouter()
router.register(r'roles', RoleViewSet, basename='roles')
router.register(r'permissions', PagePermissionViewSet, basename='permissions')
router.register(r'users', UserViewSet, basename='users')
router.register(r'persons', PersonViewSet, basename='persons')

urlpatterns = [
    path('auth/login', CustomLoginView.as_view(), name='token_obtain_pair'),
    path('auth/register', register_view, name='register'),
    path('auth/signup', register_view, name='signup'),
    path('auth/me', current_user_view, name='current_user'),
    path('auth/logout', logout_view, name='logout'),
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('', include(router.urls)),
]
