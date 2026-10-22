from django.urls import path, include
from rest_framework.routers import DefaultRouter
from leaves_ob.views import LeaveOBViewSet

router = DefaultRouter()
router.register(r'leaves-ob', LeaveOBViewSet, basename='leave-ob')

urlpatterns = [
    path('leaves/my-leaves/', LeaveOBViewSet.as_view({'get': 'my_leaves'}), name='leaves-my-leaves'),
    path('leaves/my-leaves', LeaveOBViewSet.as_view({'get': 'my_leaves'}), name='leaves-my-leaves-no-slash'),
    path('leaves-ob/my-leaves/', LeaveOBViewSet.as_view({'get': 'my_leaves'}), name='leaves-ob-my-leaves'),
    path('leaves-ob/my-leaves', LeaveOBViewSet.as_view({'get': 'my_leaves'}), name='leaves-ob-my-leaves-no-slash'),
    path('', include(router.urls)),
]
