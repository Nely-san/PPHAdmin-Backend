from django.utils import timezone
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from users.models import User, Role, PagePermission, Person, Notification, NotificationPreference

from settings.serializers import PagePermissionSerializer, RoleSerializer


class PersonDetailSerializer(serializers.ModelSerializer):
    user_id = serializers.CharField(source='user.id', read_only=True, default=None)
    username = serializers.CharField(source='user.username', read_only=True, default=None)
    approval_status = serializers.CharField(source='user.approval_status', read_only=True, default=None)
    is_active = serializers.BooleanField(source='user.is_active', read_only=True, default=None)

    biometric_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    class Meta:
        model = Person
        fields = [
            'id', 'user_id', 'username', 'approval_status', 'is_active',
            'biometric_id', 'name', 'person_type', 'employment_mode', 
            'rate_type', 'base_rate', 'date_started', 'date_ended', 'status', 
            'school_name', 'coordinator_contact', 
            'required_ojt_hours', 'rendered_ojt_hours', 'is_newly_imported',
            'work_setup', 'notes', 'shift_code', 'work_days', 'has_government_deductions'
        ]

    def to_internal_value(self, data):
        mapped_data = data.copy() if hasattr(data, 'copy') else dict(data)
        camel_to_snake = {
            'biometricId': 'biometric_id',
            'personType': 'person_type',
            'employmentMode': 'employment_mode',
            'rateType': 'rate_type',
            'baseRate': 'base_rate',
            'hasGovernmentDeductions': 'has_government_deductions',
            'dateStarted': 'date_started',
            'dateEnded': 'date_ended',
            'schoolName': 'school_name',
            'coordinatorContact': 'coordinator_contact',
            'requiredOjtHours': 'required_ojt_hours',
            'renderedOjtHours': 'rendered_ojt_hours',
            'isNewlyImported': 'is_newly_imported',
            'workSetup': 'work_setup',
            'shiftCode': 'shift_code',
            'workDays': 'work_days',
        }
        for camel, snake in camel_to_snake.items():
            if camel in mapped_data and snake not in mapped_data:
                mapped_data[snake] = mapped_data[camel]

        if 'biometric_id' in mapped_data:
            bio = mapped_data['biometric_id']
            if bio is None or (isinstance(bio, str) and not bio.strip()):
                mapped_data['biometric_id'] = None
            else:
                mapped_data['biometric_id'] = str(bio).strip()

        return super().to_internal_value(mapped_data)

    def create(self, validated_data):
        user_id = self.initial_data.get('user_id') or self.initial_data.get('userId')
        username = self.initial_data.get('username')
        if not validated_data.get('user'):
            if user_id:
                user = User.objects.filter(id=user_id).first()
                if user and not getattr(user, 'person', None):
                    validated_data['user'] = user
            elif username:
                user = User.objects.filter(username__iexact=username).first()
                if user and not getattr(user, 'person', None):
                    validated_data['user'] = user
        return super().create(validated_data)

    def update(self, instance, validated_data):
        username = self.initial_data.get('username')
        user_id = self.initial_data.get('user_id') or self.initial_data.get('userId')
        if instance.user:
            if username is not None:
                cleaned_username = username.strip() if isinstance(username, str) else ''
                if cleaned_username and instance.user.username != cleaned_username:
                    existing_user = User.objects.filter(username__iexact=cleaned_username).exclude(id=instance.user.id).first()
                    if existing_user:
                        raise serializers.ValidationError({'username': f"Username '{cleaned_username}' is already taken."})
                    instance.user.username = cleaned_username
                    instance.user.save(update_fields=['username'])
        else:
            if user_id:
                user = User.objects.filter(id=user_id).first()
                if user and (not getattr(user, 'person', None) or user.person == instance):
                    instance.user = user
            elif username:
                cleaned_username = username.strip() if isinstance(username, str) else ''
                if cleaned_username:
                    user = User.objects.filter(username__iexact=cleaned_username).first()
                    if user and (not getattr(user, 'person', None) or user.person == instance):
                        instance.user = user
        return super().update(instance, validated_data)



class UserProfileSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()
    role_detail = RoleSerializer(source='role', read_only=True)
    allowed_pages = serializers.SerializerMethodField()
    navigation = serializers.SerializerMethodField()
    role_code = serializers.CharField(write_only=True, required=False)
    role_id = serializers.PrimaryKeyRelatedField(
        queryset=Role.objects.filter(is_archived=False), source='role', write_only=True, required=False
    )
    person = PersonDetailSerializer(read_only=True)
    password = serializers.CharField(write_only=True, required=False)
    custom_permissions = PagePermissionSerializer(many=True, read_only=True)
    approved_by_username = serializers.CharField(source='approved_by.username', read_only=True)
    school_name = serializers.CharField(write_only=True, required=False, allow_null=True, allow_blank=True)
    schoolName = serializers.CharField(write_only=True, required=False, allow_null=True, allow_blank=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'role', 'role_detail', 'allowed_pages', 'navigation',
            'role_code', 'role_id', 'person', 'password', 'is_active', 'is_staff', 
            'approval_status', 'rejection_reason', 'approved_by', 'approved_by_username',
            'approved_at', 'custom_permissions', 'is_archived', 'created_at',
            'school_name', 'schoolName'
        ]

    def get_role(self, obj):
        return obj.role.code if obj.role else 'EMPLOYEE'

    def get_allowed_pages(self, obj):
        if not obj.role:
            return list(obj.custom_permissions.values_list('code', flat=True))
        role_pages = set(obj.role.permissions.values_list('code', flat=True))
        custom_pages = set(obj.custom_permissions.values_list('code', flat=True))
        return list(role_pages | custom_pages)

    def get_navigation(self, obj):
        from settings.models import ModuleAccess
        from settings.serializers import ModuleAccessSerializer

        allowed_codes = self.get_allowed_pages(obj)
        # Always include dashboard
        if 'dashboard' not in allowed_codes:
            allowed_codes.append('dashboard')
        # Extract base codes in case granular format like 'employees:view' is used
        base_codes = set(c.split(':')[0] for c in allowed_codes)
        modules = ModuleAccess.objects.filter(code__in=base_codes, is_archived=False).order_by('display_order', 'id')
        return ModuleAccessSerializer(modules, many=True).data


    def to_internal_value(self, data):
        mapped_data = data.copy() if hasattr(data, 'copy') else dict(data)
        if 'schoolName' in mapped_data and 'school_name' not in mapped_data:
            mapped_data['school_name'] = mapped_data['schoolName']
        if 'isArchived' in mapped_data and 'is_archived' not in mapped_data:
            mapped_data['is_archived'] = mapped_data['isArchived']
        if 'isActive' in mapped_data and 'is_active' not in mapped_data:
            mapped_data['is_active'] = mapped_data['isActive']
        ret = super().to_internal_value(mapped_data)
        if 'role' in data and 'role_code' not in ret and 'role' not in ret:
            ret['role_code'] = data['role']
        if 'schoolName' in data and 'school_name' not in ret:
            ret['school_name'] = data['schoolName']
        elif 'school_name' in data and 'school_name' not in ret:
            ret['school_name'] = data['school_name']
        if 'isArchived' in data and 'is_archived' not in ret:
            ret['is_archived'] = data['isArchived']
        if 'isActive' in data and 'is_active' not in ret:
            ret['is_active'] = data['isActive']
        return ret

    def validate(self, attrs):
        # Prevent editing role or archiving the Super Admin account
        if self.instance and self.instance.role and self.instance.role.code == 'SUPER_ADMIN':
            if 'role' in attrs and attrs['role'].code != 'SUPER_ADMIN':
                raise serializers.ValidationError({"role": "The Super Admin account cannot be changed to another role."})
            if 'role_code' in attrs and attrs['role_code'] != 'SUPER_ADMIN':
                raise serializers.ValidationError({"role": "The Super Admin account cannot be changed to another role."})
            if attrs.get('is_archived', False):
                raise serializers.ValidationError({"is_archived": "The Super Admin account cannot be archived."})
            if attrs.get('is_active') is False:
                raise serializers.ValidationError({"is_active": "The Super Admin account cannot be deactivated."})
        return attrs

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        role_code = validated_data.pop('role_code', None)
        school_name = validated_data.pop('school_name', None)
        if school_name is None:
            school_name = validated_data.pop('schoolName', None)
        if school_name is None:
            school_name = self.initial_data.get('school_name') or self.initial_data.get('schoolName')

        person_id = self.initial_data.get('person_id') or self.initial_data.get('personId')
        if role_code and 'role' not in validated_data:
            role = Role.objects.filter(code=role_code).first()
            if role:
                validated_data['role'] = role
        # Admins creating users explicitly via dashboard default to APPROVED and active
        validated_data.setdefault('approval_status', 'APPROVED')
        validated_data.setdefault('is_active', True)
        user = User.objects.create(**validated_data)
        if password:
            user.set_password(password)
            user.save()

        if person_id:
            try:
                target_person = Person.objects.filter(id=person_id, is_archived=False).first()
                if target_person:
                    # Clean up any placeholder person auto-created by post_save signal
                    auto_created = Person.objects.filter(user=user).exclude(id=target_person.id).first()
                    if auto_created:
                        auto_created.delete()
                    target_person.user = user
                    if school_name is not None:
                        target_person.school_name = school_name.strip() if isinstance(school_name, str) else school_name
                    if user.role and user.role.code == 'OJT' and target_person.person_type != 'OJT':
                        target_person.person_type = 'OJT'
                        target_person.employment_mode = 'INTERN'
                        target_person.rate_type = 'HOURLY'
                    target_person.save()
            except Exception:
                pass
        else:
            try:
                person = getattr(user, 'person', None) or Person.objects.filter(user=user).first()
                if person:
                    updated = False
                    if school_name is not None:
                        person.school_name = school_name.strip() if isinstance(school_name, str) else school_name
                        updated = True
                    if user.role and user.role.code == 'OJT':
                        if person.person_type != 'OJT':
                            person.person_type = 'OJT'
                            person.employment_mode = 'INTERN'
                            person.rate_type = 'HOURLY'
                            updated = True
                    if updated:
                        person.save()
            except Exception:
                pass

        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        role_code = validated_data.pop('role_code', None)
        school_name = validated_data.pop('school_name', None)
        if school_name is None:
            school_name = validated_data.pop('schoolName', None)
        if school_name is None and ('school_name' in self.initial_data or 'schoolName' in self.initial_data):
            school_name = self.initial_data.get('school_name') if 'school_name' in self.initial_data else self.initial_data.get('schoolName')

        if role_code:
            role = Role.objects.filter(code=role_code).first()
            if role:
                validated_data['role'] = role

        is_archived_val = validated_data.get('is_archived')
        if is_archived_val is not None:
            if is_archived_val and not instance.is_archived:
                request = self.context.get('request')
                user_identifier = request.user.username if request and hasattr(request, 'user') and request.user else None
                instance.archived_at = timezone.now()
                instance.archived_by = user_identifier
            elif not is_archived_val and instance.is_archived:
                instance.archived_at = None
                instance.archived_by = None

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()

        if is_archived_val is not None:
            try:
                person = getattr(instance, 'person', None) or Person.objects.filter(user=instance).first()
                if person:
                    if is_archived_val and not person.is_archived:
                        person.archive(user_identifier=instance.archived_by)
                    elif not is_archived_val and person.is_archived:
                        person.restore()
            except Exception:
                pass

        if school_name is not None:
            try:
                person = getattr(instance, 'person', None) or Person.objects.filter(user=instance).first()
                if person:
                    person.school_name = school_name.strip() if isinstance(school_name, str) else school_name
                    if instance.role and instance.role.code == 'OJT' and person.person_type != 'OJT':
                        person.person_type = 'OJT'
                        person.employment_mode = 'INTERN'
                        person.rate_type = 'HOURLY'
                    person.save()
            except Exception:
                pass

        return instance


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['username'] = user.username
        token['role'] = user.role.code if user.role else 'EMPLOYEE'
        return token

    def validate(self, attrs):
        username_or_email = (attrs.get('username') or '').strip()
        password = attrs.get('password', '')

        if not username_or_email:
            raise serializers.ValidationError({
                "detail": "Username or email is required."
            })

        if not password:
            raise serializers.ValidationError({
                "detail": "Password is required."
            })

        # Support login via either username or email
        user_obj = User.objects.filter(username__iexact=username_or_email).first()
        if not user_obj:
            user_obj = User.objects.filter(email__iexact=username_or_email).first()

        if not user_obj:
            raise serializers.ValidationError({
                "detail": "No account found with that username or email."
            })

        if not user_obj.check_password(password):
            raise serializers.ValidationError({
                "detail": "Incorrect password. Please try again."
            })

        if user_obj.is_archived:
            raise serializers.ValidationError({
                "detail": "This account has been archived. Please contact an administrator."
            })

        if user_obj.approval_status == 'PENDING' or not user_obj.is_active:
            if user_obj.approval_status == 'PENDING':
                raise serializers.ValidationError({
                    "detail": "Your account registration is pending approval. You cannot log in until an administrator approves your account."
                })
            elif user_obj.approval_status == 'REJECTED':
                reason = f" Reason: {user_obj.rejection_reason}" if user_obj.rejection_reason else ""
                raise serializers.ValidationError({
                    "detail": f"Your account registration has been rejected.{reason}"
                })
            else:
                raise serializers.ValidationError({
                    "detail": "Your account is currently inactive. You cannot log in until it is activated."
                })

        if user_obj.approval_status != 'APPROVED':
            raise serializers.ValidationError({
                "detail": "Your account is not approved. You cannot log in until an administrator approves your account."
            })

        attrs['username'] = user_obj.username
        data = super().validate(attrs)

        # Safety check on authenticated user
        if not self.user.is_active or self.user.approval_status != 'APPROVED':
            raise serializers.ValidationError({
                "detail": "Your account registration is pending approval. You cannot log in until an administrator approves your account."
            })

        data['user'] = UserProfileSerializer(self.user).data
        return data


class RegisterSerializer(serializers.ModelSerializer):
    username = serializers.CharField(
        min_length=3,
        max_length=150,
        required=True,
        error_messages={
            'blank': 'Username cannot be blank.',
            'min_length': 'Username must be at least 3 characters long.',
            'required': 'Username is required.'
        }
    )
    email = serializers.EmailField(
        required=True,
        error_messages={
            'blank': 'Email cannot be blank.',
            'invalid': 'Please enter a valid email address.',
            'required': 'Email is required.'
        }
    )
    password = serializers.CharField(
        write_only=True,
        min_length=6,
        required=True,
        error_messages={
            'blank': 'Password cannot be blank.',
            'min_length': 'Password must be at least 6 characters long.',
            'required': 'Password is required.'
        }
    )

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password']

    def validate_username(self, value):
        val = value.strip()
        if not val:
            raise serializers.ValidationError("Username cannot be empty.")
        if User.objects.filter(username__iexact=val).exists():
            raise serializers.ValidationError("A user with this username already exists.")
        return val

    def validate_email(self, value):
        val = value.strip().lower()
        if not val:
            raise serializers.ValidationError("Email cannot be empty.")
        if User.objects.filter(email__iexact=val).exists():
            raise serializers.ValidationError("A user with this email address already exists.")
        return val

    def create(self, validated_data):
        username = validated_data['username'].strip()
        email = validated_data['email'].strip().lower()
        password = validated_data['password']

        employee_role = Role.objects.filter(code='EMPLOYEE').first()

        user = User.objects.create(
            username=username,
            email=email,
            role=employee_role,
            approval_status='PENDING',
            is_active=False,
            is_staff=False,
            is_archived=False
        )
        user.set_password(password)
        user.save()

        # Link or create a Person profile
        if not getattr(user, 'person', None):
            Person.objects.get_or_create(
                user=user,
                defaults={
                    'name': username,
                    'person_type': 'EMPLOYEE',
                    'employment_mode': 'FULL_TIME',
                    'rate_type': 'DAILY',
                    'base_rate': 0.00,
                    'status': 'ACTIVE'
                }
            )

        return user


class AccountApprovalSerializer(serializers.Serializer):
    """
    Serializer for handling account review, approval with role/page assignment, or rejection.
    """
    action = serializers.ChoiceField(choices=['APPROVE', 'REJECT'])
    role_code = serializers.CharField(required=False, allow_null=True)
    role_id = serializers.IntegerField(required=False, allow_null=True)
    page_codes = serializers.ListField(
        child=serializers.CharField(), required=False, allow_empty=True
    )
    rejection_reason = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate(self, attrs):
        action = attrs.get('action')
        if action == 'REJECT' and not attrs.get('rejection_reason'):
            raise serializers.ValidationError({
                "rejection_reason": "A rejection reason is required when rejecting an account."
            })
        if action == 'APPROVE' and not attrs.get('role_code') and not attrs.get('role_id'):
            raise serializers.ValidationError({
                "role": "A role must be assigned when approving an account."
            })
        return attrs


class NotificationSerializer(serializers.ModelSerializer):
    userId = serializers.CharField(source='user.id', read_only=True)
    isRead = serializers.BooleanField(source='is_read')
    actionUrl = serializers.CharField(source='action_url', allow_null=True, required=False)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)

    class Meta:
        model = Notification
        fields = [
            'id', 'userId', 'title', 'message', 'isRead',
            'category', 'priority', 'actionUrl', 'createdAt', 'updatedAt'
        ]


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    enableInApp = serializers.BooleanField(source='enable_in_app', required=False)
    notifyAttendance = serializers.BooleanField(source='notify_attendance', required=False)
    notifyPayroll = serializers.BooleanField(source='notify_payroll', required=False)
    notifyLeave = serializers.BooleanField(source='notify_leave', required=False)

    class Meta:
        model = NotificationPreference
        fields = ['enableInApp', 'notifyAttendance', 'notifyPayroll', 'notifyLeave']

    def to_internal_value(self, data):
        mapped_data = data.copy() if hasattr(data, 'copy') else dict(data)
        camel_to_snake = {
            'enableInApp': 'enable_in_app',
            'notifyAttendance': 'notify_attendance',
            'notifyPayroll': 'notify_payroll',
            'notifyLeave': 'notify_leave',
        }
        for camel, snake in camel_to_snake.items():
            if camel in mapped_data and snake not in mapped_data:
                mapped_data[snake] = mapped_data[camel]
        return super().to_internal_value(mapped_data)


