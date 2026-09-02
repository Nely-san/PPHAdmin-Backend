from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from users.models import User, Role, PagePermission, Person

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
            'company_name', 'department_name', 'school_name', 'coordinator_contact', 
            'required_ojt_hours', 'rendered_ojt_hours', 'is_newly_imported',
            'work_setup', 'notes', 'shift_code', 'work_days'
        ]

    def to_internal_value(self, data):
        mapped_data = data.copy() if hasattr(data, 'copy') else dict(data)
        camel_to_snake = {
            'biometricId': 'biometric_id',
            'personType': 'person_type',
            'employmentMode': 'employment_mode',
            'rateType': 'rate_type',
            'baseRate': 'base_rate',
            'dateStarted': 'date_started',
            'dateEnded': 'date_ended',
            'companyName': 'company_name',
            'departmentName': 'department_name',
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

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'role', 'role_detail', 'allowed_pages', 'navigation',
            'role_code', 'role_id', 'person', 'password', 'is_active', 'is_staff', 
            'approval_status', 'rejection_reason', 'approved_by', 'approved_by_username',
            'approved_at', 'custom_permissions', 'is_archived', 'created_at'
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
        ret = super().to_internal_value(data)
        if 'role' in data and 'role_code' not in ret and 'role' not in ret:
            ret['role_code'] = data['role']
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
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        role_code = validated_data.pop('role_code', None)
        if role_code:
            role = Role.objects.filter(code=role_code).first()
            if role:
                validated_data['role'] = role
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
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
        Person.objects.create(
            user=user,
            name=username,
            person_type='EMPLOYEE',
            employment_mode='FULL_TIME',
            rate_type='DAILY',
            base_rate=0.00,
            status='ACTIVE'
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

