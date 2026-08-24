from django.urls import path, include
from rest_framework.routers import DefaultRouter
from organization.views import CompanyViewSet, DepartmentViewSet

router = DefaultRouter()
router.register(r'companies', CompanyViewSet, basename='companies')
router.register(r'departments', DepartmentViewSet, basename='departments')

urlpatterns = [
    path('', include(router.urls)),
]
