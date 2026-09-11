from django.urls import path, include
from rest_framework.routers import DefaultRouter
from leaves_ob.views import LeaveOBViewSet

router = DefaultRouter()
router.register(r'leaves-ob', LeaveOBViewSet, basename='leave-ob')

urlpatterns = [
    path('', include(router.urls)),
]
