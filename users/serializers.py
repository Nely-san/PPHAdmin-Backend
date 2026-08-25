from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from users.models import User, Role, PagePermission, Person

class PagePermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PagePermission
        fields = ['id', 'code', 'name', 'module', 'icon', 'description']


class RoleSerializer(serializers.ModelSerializer):
    permissions = PagePermissionSerializer(many=True, read_only=True)
    permission_codes = serializers.ListField(
        child=serializers.CharField(), write_only=True, required=False
    )
    allowed_pages = serializers.SerializerMethodField()

    class Meta:
        model = Role
        fields = [
            'id', 'name', 'code', 'description', 'is_system_role', 
            'permissions', 'permission_codes', 'allowed_pages'
        ]

    def get_allowed_pages(self, obj):
        return list(obj.permissions.values_list('code', flat=True))

    def _resolve_permissions(self, permission_codes):
        perms = []
        for pcode in permission_codes:
            perm = PagePermission.objects.filter(code=pcode).first()
            if not perm:
                parts = pcode.split(':')
                base_code = parts[0]
                action_name = parts[1] if len(parts) > 1 else 'view'
                base_perm = PagePermission.objects.filter(code=base_code).first()
                perm, _ = PagePermission.objects.get_or_create(
                    code=pcode,
                    defaults={
                        'name': f"{base_perm.name if base_perm else base_code.title()} ({action_name.capitalize()})",
                        'module': base_perm.module if base_perm else 'SYSTEM',
                        'icon': base_perm.icon if base_perm else 'fi fi-rr-check',
                        'description': f"Permission to {action_name} in {base_perm.name if base_perm else base_code}"
                    }
                )
            if perm:
                perms.append(perm)
        return perms

    def create(self, validated_data):
        permission_codes = validated_data.pop('permission_codes', [])
        role = Role.objects.create(**validated_data)
        if permission_codes:
            perms = self._resolve_permissions(permission_codes)
            role.permissions.set(perms)
        return role

    def update(self, instance, validated_data):
        if instance.code == 'SUPER_ADMIN' and 'code' in validated_data and validated_data['code'] != 'SUPER_ADMIN':
            raise serializers.ValidationError("Cannot change system code for Super Admin.")
        
        permission_codes = validated_data.pop('permission_codes', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if permission_codes is not None:
            perms = self._resolve_permissions(permission_codes)
            instance.permissions.set(perms)
        return instance


class PersonDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Person
        fields = [
            'id', 'biometric_id', 'name', 'person_type', 'employment_mode', 
            'rate_type', 'base_rate', 'date_started', 'date_ended', 'status', 
            'company_name', 'department_name', 'school_name', 'coordinator_contact', 
            'required_ojt_hours', 'rendered_ojt_hours', 'is_newly_imported'
        ]


class UserProfileSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()
    role_detail = RoleSerializer(source='role', read_only=True)
    allowed_pages = serializers.SerializerMethodField()
    role_code = serializers.CharField(write_only=True, required=False)
    role_id = serializers.PrimaryKeyRelatedField(
        queryset=Role.objects.filter(is_archived=False), source='role', write_only=True, required=False
    )
    person = PersonDetailSerializer(read_only=True)
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'role', 'role_detail', 'allowed_pages', 
            'role_code', 'role_id', 'person', 'password', 'is_active', 'is_staff', 
            'is_archived', 'created_at'
        ]

    def get_role(self, obj):
        return obj.role.code if obj.role else 'EMPLOYEE'

    def get_allowed_pages(self, obj):
        if not obj.role:
            return []
        if obj.role.code == 'SUPER_ADMIN':
            return list(PagePermission.objects.values_list('code', flat=True))
        return list(obj.role.permissions.values_list('code', flat=True))

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
        # Support login via either username or email
        username_or_email = attrs.get('username', '')
        if username_or_email:
            user_obj = User.objects.filter(username=username_or_email).first()
            if not user_obj:
                user_obj = User.objects.filter(email__iexact=username_or_email).first()
            if user_obj:
                attrs['username'] = user_obj.username
        data = super().validate(attrs)
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
            is_active=True,
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
