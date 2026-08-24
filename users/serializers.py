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

    def create(self, validated_data):
        permission_codes = validated_data.pop('permission_codes', [])
        role = Role.objects.create(**validated_data)
        if permission_codes:
            perms = PagePermission.objects.filter(code__in=permission_codes)
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
            perms = PagePermission.objects.filter(code__in=permission_codes)
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
        data = super().validate(attrs)
        data['user'] = UserProfileSerializer(self.user).data
        return data
