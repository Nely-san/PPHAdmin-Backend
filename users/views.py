from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken

from users.models import User, Role, PagePermission, Person
from users.serializers import (
    RoleSerializer, 
    PagePermissionSerializer, 
    UserProfileSerializer,
    PersonDetailSerializer,
    CustomTokenObtainPairSerializer
)

class RoleViewSet(viewsets.ModelViewSet):
    """
    CRUD ViewSet for Super Admin to manage dynamic roles & assign page permissions.
    """
    queryset = Role.objects.filter(is_archived=False)
    serializer_class = RoleSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

    def destroy(self, request, *args, **kwargs):
        role = self.get_object()
        if role.is_system_role or role.code == 'SUPER_ADMIN':
            return Response(
                {"detail": "System baseline roles (including SUPER_ADMIN) cannot be deleted."},
                status=status.HTTP_400_BAD_REQUEST
            )
        role.archive(user_identifier=request.user.username)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PagePermissionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Catalog of all functional page permissions for the Super Admin assignment matrix.
    """
    queryset = PagePermission.objects.filter(is_archived=False)
    serializer_class = PagePermissionSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None


class UserViewSet(viewsets.ModelViewSet):
    """
    User account management with Single Super Admin and Undeletable Super Admin protections.
    """
    queryset = User.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        qs = User.objects.all()
        include_archived = self.request.query_params.get('include_archived', 'false').lower() == 'true'
        if not include_archived:
            qs = qs.filter(is_archived=False)
        return qs

    def destroy(self, request, *args, **kwargs):
        user = self.get_object()
        if user.role and user.role.code == 'SUPER_ADMIN':
            return Response(
                {"detail": "The Super Admin account is permanent and cannot be deleted or archived."},
                status=status.HTTP_400_BAD_REQUEST
            )
        user.archive(user_identifier=request.user.username)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'], url_path='archive')
    def archive_user(self, request, pk=None):
        user = self.get_object()
        if user.role and user.role.code == 'SUPER_ADMIN':
            return Response(
                {"detail": "The Super Admin account cannot be archived."},
                status=status.HTTP_400_BAD_REQUEST
            )
        user.archive(user_identifier=request.user.username)
        return Response({"detail": f"User @{user.username} successfully archived."})

    @action(detail=True, methods=['post'], url_path='unarchive')
    def unarchive_user(self, request, pk=None):
        user = self.get_object()
        user.restore()
        return Response({"detail": f"User @{user.username} successfully restored."})


class PersonViewSet(viewsets.ModelViewSet):
    """
    Personnel (Employee & OJT) profiles management.
    """
    queryset = Person.objects.filter(is_archived=False)
    serializer_class = PersonDetailSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        qs = Person.objects.all()
        include_archived = self.request.query_params.get('include_archived', 'false').lower() == 'true'
        if not include_archived:
            qs = qs.filter(is_archived=False)
        return qs

    @action(detail=True, methods=['post'], url_path='archive')
    def archive_person(self, request, pk=None):
        person = self.get_object()
        person.archive(user_identifier=request.user.username)
        return Response({"detail": f"Profile {person.name} archived."})

    @action(detail=True, methods=['post'], url_path='unarchive')
    def unarchive_person(self, request, pk=None):
        person = self.get_object()
        person.restore()
        return Response({"detail": f"Profile {person.name} restored."})

    @action(detail=True, methods=['patch', 'put'], url_path='ojt-hours')
    def update_ojt_hours(self, request, pk=None):
        person = self.get_object()
        rendered = request.data.get('renderedOjtHours') or request.data.get('rendered_ojt_hours')
        if rendered is not None:
            person.rendered_ojt_hours = rendered
            person.save(update_fields=['rendered_ojt_hours', 'updated_at'])
        return Response(PersonDetailSerializer(person).data)


class CustomLoginView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def current_user_view(request):
    """
    Returns authenticated user profile, dynamic role, and allowed pages.
    """
    serializer = UserProfileSerializer(request.user)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def logout_view(request):
    """
    Blacklists refresh token on logout if provided.
    """
    try:
        refresh_token = request.data.get('refresh_token')
        if refresh_token:
            token = RefreshToken(refresh_token)
            token.blacklist()
    except Exception:
        pass
    return Response({"detail": "Successfully logged out."})
