from django.urls import path, include
from rest_framework.routers import DefaultRouter
from users.views import (
    RoleViewSet, 
    PagePermissionViewSet, 
    UserViewSet, 
    PersonViewSet,
    CustomLoginView,
    current_user_view,
    logout_view
)

router = DefaultRouter()
router.register(r'roles', RoleViewSet, basename='roles')
router.register(r'permissions', PagePermissionViewSet, basename='permissions')
router.register(r'users', UserViewSet, basename='users')
router.register(r'persons', PersonViewSet, basename='persons')

urlpatterns = [
    path('auth/login', CustomLoginView.as_view(), name='token_obtain_pair'),
    path('auth/me', current_user_view, name='current_user'),
    path('auth/logout', logout_view, name='logout'),
    path('', include(router.urls)),
]
