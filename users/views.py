import requests
from django.conf import settings
from django.db.models import Case, When, Value, IntegerField
from django.utils import timezone
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken

from users.models import User, Person, Role, PagePermission, Notification, NotificationPreference
from users.serializers import (
    UserProfileSerializer,
    PersonDetailSerializer,
    CustomTokenObtainPairSerializer,
    RegisterSerializer,
    AccountApprovalSerializer,
    NotificationSerializer,
    NotificationPreferenceSerializer
)

ROLE_ORDER_MAP = {
    'SUPER_ADMIN': 1,
    'ADMIN': 2,
    'HR_MANAGER': 3,
    'PAYROLL_OFFICER': 4,
    'EMPLOYEE': 5,
    'OJT': 6,
}


class UserViewSet(viewsets.ModelViewSet):
    """
    User account management with Single Super Admin, Undeletable Super Admin protections,
    and Account Review & Approval Lifecycle.
    """
    queryset = User.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        qs = User.objects.all()
        # For detail actions (approve, reject, archive, unarchive, retrieve, update, etc.), do not restrict queryset by list filters
        if self.action and self.action not in ['list', 'pending_approvals']:
            return qs

        include_archived = self.request.query_params.get('include_archived', 'false').lower() == 'true'
        include_pending = self.request.query_params.get('include_pending', 'false').lower() == 'true'
        if not include_archived:
            qs = qs.filter(is_archived=False)
        
        approval_status = self.request.query_params.get('approval_status')
        if approval_status:
            qs = qs.filter(approval_status=approval_status.upper())
        elif not include_pending:
            qs = qs.filter(approval_status='APPROVED', is_active=True)
            
        role_when_clauses = [When(role__code=code, then=Value(rank)) for code, rank in ROLE_ORDER_MAP.items()]

        qs = qs.annotate(
            is_pending_order=Case(
                When(approval_status='PENDING', is_archived=False, then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            ),
            role_hierarchy_order=Case(
                *role_when_clauses,
                default=Value(99),
                output_field=IntegerField(),
            )
        ).order_by('is_pending_order', 'role_hierarchy_order', 'username')

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

    @action(detail=False, methods=['get'], url_path='pending-approvals')
    def pending_approvals(self, request):
        """
        List all accounts awaiting admin review & approval.
        """
        pending_users = User.objects.filter(approval_status='PENDING', is_archived=False).order_by('-created_at')
        serializer = self.get_serializer(pending_users, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='approve')
    def approve_user(self, request, pk=None):
        """
        Approve an account, assign dynamic role and accessible pages, and activate login.
        """
        user = self.get_object()
        payload = dict(request.data)
        for k, v in payload.items():
            if isinstance(v, list) and k not in ['page_codes']:
                payload[k] = v[0] if len(v) > 0 else None
        payload['action'] = 'APPROVE'

        serializer = AccountApprovalSerializer(data=payload)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        role = None
        if data.get('role_id'):
            role = Role.objects.filter(id=data['role_id'], is_archived=False).first()
        elif data.get('role_code'):
            role = Role.objects.filter(code=data['role_code'], is_archived=False).first()

        if not role:
            return Response({"role": "Valid role is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Enforce single Super Admin safeguard
        if role.code == 'SUPER_ADMIN':
            existing_sa = User.objects.filter(role__code='SUPER_ADMIN', is_archived=False).exclude(pk=user.pk)
            if existing_sa.exists():
                return Response(
                    {"detail": "System policy strictly allows only one active Super Admin account."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        user.role = role
        user.approval_status = 'APPROVED'
        user.is_active = True
        user.approved_by = request.user
        user.approved_at = timezone.now()
        user.rejection_reason = None

        # Assign custom page permissions if provided
        page_codes = data.get('page_codes')
        if page_codes is not None:
            pages = PagePermission.objects.filter(code__in=page_codes)
            user.custom_permissions.set(pages)

        user.save()
        return Response(
            UserProfileSerializer(user).data,
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['post'], url_path='reject')
    def reject_user(self, request, pk=None):
        """
        Reject an account application with a mandatory rejection reason.
        """
        user = self.get_object()
        if user.role and user.role.code == 'SUPER_ADMIN':
            return Response(
                {"detail": "The Super Admin account cannot be rejected."},
                status=status.HTTP_400_BAD_REQUEST
            )

        payload = dict(request.data)
        for k, v in payload.items():
            if isinstance(v, list):
                payload[k] = v[0] if len(v) > 0 else None
        payload['action'] = 'REJECT'

        serializer = AccountApprovalSerializer(data=payload)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        user.approval_status = 'REJECTED'
        user.is_active = False
        user.rejection_reason = data.get('rejection_reason')
        user.approved_by = request.user
        user.approved_at = timezone.now()
        user.save()

        return Response(
            UserProfileSerializer(user).data,
            status=status.HTTP_200_OK
        )


class PersonViewSet(viewsets.ModelViewSet):
    """
    Personnel (Employee & OJT) profiles management.
    """
    queryset = Person.objects.filter(is_archived=False)
    serializer_class = PersonDetailSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        from django.db.models import Q
        qs = Person.objects.all()
        if self.action and self.action not in ['list']:
            return qs

        include_archived = self.request.query_params.get('include_archived', 'false').lower() == 'true'
        include_pending = self.request.query_params.get('include_pending', 'false').lower() == 'true'
        
        if not include_archived:
            qs = qs.filter(is_archived=False).exclude(status='ARCHIVED')
        else:
            status_param = self.request.query_params.get('status')
            if status_param == 'ARCHIVED':
                qs = qs.filter(Q(is_archived=True) | Q(status='ARCHIVED'))

        if not include_pending:
            qs = qs.filter(
                Q(user__isnull=True) | Q(user__approval_status='APPROVED', user__is_active=True)
            )
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


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def register_view(request):
    """
    Public registration endpoint for new users.
    Accepts username, email, and password.
    """
    serializer = RegisterSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        response_serializer = UserProfileSerializer(user)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)
    
    errors = serializer.errors
    error_messages = []
    for field, field_errors in errors.items():
        if isinstance(field_errors, list):
            error_messages.append(f"{field.capitalize()}: {field_errors[0]}")
        else:
            error_messages.append(f"{field.capitalize()}: {field_errors}")
    return Response(
        {"detail": " ".join(error_messages), "errors": errors},
        status=status.HTTP_400_BAD_REQUEST
    )


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


class ChangePasswordView(APIView):
    """
    Endpoint for authenticated users to update their password.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        current_password = request.data.get('current_password')
        new_password = request.data.get('new_password')

        if not current_password or not new_password:
            return Response({'error': 'Current and new passwords are required.'}, status=status.HTTP_400_BAD_REQUEST)

        user = request.user

        if not user.check_password(current_password):
            return Response({'error': 'Incorrect current password.'}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()

        return Response({'message': 'Password updated successfully.'}, status=status.HTTP_200_OK)


class GoogleLoginView(APIView):
    """
    Endpoint for Google Sign-In and Sign-Up.
    Cryptographically verifies the Google ID Token (or access token) before authenticating,
    matching with existing accounts, or auto-provisioning a new Employee User and Person profile.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        raw_token = (
            request.data.get('id_token') or
            request.data.get('credential') or
            request.data.get('token')
        )
        access_token = request.data.get('access_token')

        email = None
        first_name = ''
        last_name = ''
        name = ''

        if raw_token:
            try:
                google_client_id = getattr(settings, 'GOOGLE_CLIENT_ID', None)
                audience = google_client_id if (google_client_id and not google_client_id.startswith('YOUR_')) else None
                idinfo = id_token.verify_oauth2_token(
                    raw_token,
                    google_requests.Request(),
                    audience=audience
                )

                email = idinfo.get('email', '').strip().lower()
                first_name = idinfo.get('given_name', '').strip()
                last_name = idinfo.get('family_name', '').strip()
                name = idinfo.get('name', '').strip() or f"{first_name} {last_name}".strip()
                email_verified = idinfo.get('email_verified', True)

                if not email_verified:
                    return Response({'error': 'Google email is not verified.'}, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                return Response(
                    {'error': f'Invalid Google ID token signature or token expired: {str(e)}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        elif access_token:
            try:
                userinfo_res = requests.get(
                    'https://www.googleapis.com/oauth2/v3/userinfo',
                    headers={'Authorization': f'Bearer {access_token}'},
                    timeout=10
                )
                if userinfo_res.status_code != 200:
                    return Response({'error': 'Failed to verify Google access token.'}, status=status.HTTP_400_BAD_REQUEST)
                idinfo = userinfo_res.json()
                email = idinfo.get('email', '').strip().lower()
                first_name = idinfo.get('given_name', '').strip()
                last_name = idinfo.get('family_name', '').strip()
                name = idinfo.get('name', '').strip() or f"{first_name} {last_name}".strip()
                email_verified = idinfo.get('email_verified', True)
                if not email_verified:
                    return Response({'error': 'Google email is not verified.'}, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                return Response(
                    {'error': f'Failed to verify Google access token: {str(e)}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            return Response(
                {'error': 'Google ID token or valid OAuth credential is required for authentication.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not email:
            return Response({'error': 'Email could not be verified from Google credentials.'}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.filter(email__iexact=email, is_archived=False).first()
        is_new_user = False

        if not user:
            # ---------------------------------------------------------------------------------
            # GOOGLE SIGN-UP FLOW: Provision new User + linked Person HR profile
            # ---------------------------------------------------------------------------------
            is_new_user = True
            base_username = email.split('@')[0]
            username = base_username
            counter = 1
            while User.objects.filter(username__iexact=username).exists():
                username = f"{base_username}{counter}"
                counter += 1

            employee_role = Role.objects.filter(code='EMPLOYEE').first()

            user = User.objects.create(
                username=username,
                email=email,
                role=employee_role,
                approval_status='PENDING',  # Account awaits admin review & approval
                is_active=False,
                is_staff=False,
                is_archived=False
            )
            # Google OAuth users don't need a local raw password
            user.set_unusable_password()
            user.save()

            # Update or create corresponding personnel HR profile
            display_name = name if name else username
            person = Person.objects.filter(user=user).first()
            if person:
                person.name = display_name
                person.save(update_fields=['name'])
            else:
                Person.objects.create(
                    user=user,
                    name=display_name,
                    person_type='EMPLOYEE',
                    employment_mode='FULL_TIME',
                    rate_type='DAILY',
                    base_rate=0.00,
                    status='ACTIVE'
                )

            serializer = UserProfileSerializer(user)
            return Response({
                'is_new_user': True,
                'approval_status': 'PENDING',
                'message': 'Account registered successfully with Google. Please wait for an administrator to approve your account before you can log in.',
                'user': serializer.data
            }, status=status.HTTP_201_CREATED)

        if user.approval_status == 'PENDING':
            return Response({
                'error': 'Your account registration is pending approval. You cannot log in until an administrator approves your account.'
            }, status=status.HTTP_403_FORBIDDEN)

        if user.approval_status == 'REJECTED':
            reason = f" Reason: {user.rejection_reason}" if user.rejection_reason else ""
            return Response({
                'error': f'Your account registration has been rejected.{reason}'
            }, status=status.HTTP_403_FORBIDDEN)

        if not user.is_active:
            return Response({
                'error': 'Your account has been deactivated. Please contact an administrator.'
            }, status=status.HTTP_403_FORBIDDEN)

        refresh = RefreshToken.for_user(user)
        refresh['username'] = user.username
        refresh['role'] = user.role.code if user.role else 'EMPLOYEE'

        serializer = UserProfileSerializer(user)

        return Response({
            'access': str(getattr(refresh, 'access_token', '')),
            'access_token': str(getattr(refresh, 'access_token', '')),
            'refresh': str(refresh),
            'is_new_user': False,
            'user': serializer.data
        }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def notifications_list_view(request):
    """
    Returns the list of notifications for the current authenticated user.
    Supports cursor-based and limit-based pagination.
    """
    qs = Notification.objects.filter(user=request.user, is_archived=False).order_by('-created_at')

    cursor = request.query_params.get('cursor')
    if cursor:
        cursor_item = Notification.objects.filter(id=cursor).first()
        if cursor_item:
            qs = qs.filter(created_at__lt=cursor_item.created_at)

    limit = request.query_params.get('limit')
    try:
        limit = int(limit) if limit else 20
        if limit < 1:
            limit = 20
    except (ValueError, TypeError):
        limit = 20

    notifications = qs[:limit]
    serializer = NotificationSerializer(notifications, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def notifications_unread_count_view(request):
    """Returns the unread notifications count for the current authenticated user."""
    count = Notification.objects.filter(user=request.user, is_read=False, is_archived=False).count()
    return Response({"unreadCount": count})


@api_view(['PUT', 'POST'])
@permission_classes([permissions.IsAuthenticated])
def notification_mark_read_view(request, pk=None):
    """Marks a specific notification as read."""
    notification = Notification.objects.filter(id=pk, user=request.user, is_archived=False).first()
    if not notification:
        return Response({'detail': 'Notification not found.'}, status=status.HTTP_404_NOT_FOUND)
    notification.is_read = True
    notification.save(update_fields=['is_read', 'updated_at'])
    return Response(NotificationSerializer(notification).data)


@api_view(['PUT', 'POST'])
@permission_classes([permissions.IsAuthenticated])
def notifications_mark_all_read_view(request):
    """Marks all unread notifications for the user as read."""
    unread_qs = Notification.objects.filter(user=request.user, is_read=False, is_archived=False)
    count = unread_qs.count()
    unread_qs.update(is_read=True)
    return Response({"status": "success", "count": count})


@api_view(['GET', 'PUT', 'PATCH'])
@permission_classes([permissions.IsAuthenticated])
def notification_preferences_view(request):
    """Retrieves or updates notification preferences for current user."""
    pref, _ = NotificationPreference.objects.get_or_create(user=request.user)
    if request.method in ['PUT', 'PATCH']:
        serializer = NotificationPreferenceSerializer(pref, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
    return Response(NotificationPreferenceSerializer(pref).data)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def attendance_reset_view(request):
    """
    Resets biometric attendance logs and cleans out imported temporary accounts.
    Logs audit trail event.
    """
    imported_persons = Person.objects.filter(is_newly_imported=True, is_archived=False)
    count = imported_persons.count()
    for p in imported_persons:
        p.archive(user_identifier=request.user.username)

    from settings.models import AuditLog
    AuditLog.objects.create(
        table_name='attendance_records',
        action='RESET',
        changed_by=request.user.username,
        new_data=f"Attendance and biometrics vault reset. {count} newly imported temporary record(s) archived."
    )

    return Response({
        'status': 'success',
        'message': f'Attendance records reset cleanly. {count} temporary imported record(s) purged.'
    }, status=status.HTTP_200_OK)




