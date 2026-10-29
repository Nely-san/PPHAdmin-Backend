from django.urls import path, include
from rest_framework.routers import DefaultRouter
from leaves_ob.views import LeaveOBViewSet, OvertimeApplicationViewSet

router = DefaultRouter()
router.register(r'leaves-ob', LeaveOBViewSet, basename='leave-ob')
router.register(r'overtime', OvertimeApplicationViewSet, basename='overtime')

urlpatterns = [
    path('leaves/my-leaves/', LeaveOBViewSet.as_view({'get': 'my_leaves'}), name='leaves-my-leaves'),
    path('leaves/my-leaves', LeaveOBViewSet.as_view({'get': 'my_leaves'}), name='leaves-my-leaves-no-slash'),
    path('leaves-ob/my-leaves/', LeaveOBViewSet.as_view({'get': 'my_leaves'}), name='leaves-ob-my-leaves'),
    path('leaves-ob/my-leaves', LeaveOBViewSet.as_view({'get': 'my_leaves'}), name='leaves-ob-my-leaves-no-slash'),
    path('overtime/my-overtime/', OvertimeApplicationViewSet.as_view({'get': 'my_overtime'}), name='overtime-my-overtime'),
    path('overtime/my-overtime', OvertimeApplicationViewSet.as_view({'get': 'my_overtime'}), name='overtime-my-overtime-no-slash'),
    path('', include(router.urls)),
]
