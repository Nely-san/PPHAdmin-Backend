from rest_framework import serializers
from settings.models import SystemParameter
from users.models import Role, PagePermission

class SystemParameterSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemParameter
        fields = ['id', 'key', 'value', 'description', 'category', 'created_at', 'updated_at']


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
