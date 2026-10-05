from rest_framework import serializers
from settings.models import SystemParameter, ModuleAccess, AuditLog
from users.models import Role, PagePermission

class SystemParameterSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemParameter
        fields = ['id', 'key', 'value', 'description', 'category', 'created_at', 'updated_at']


class ModuleAccessSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModuleAccess
        fields = [
            'id', 'code', 'name', 'module', 'icon', 'path', 
            'tag', 'is_primary', 'display_order', 'allowed_actions', 'description'
        ]


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
        extra_kwargs = {
            'code': {'required': False, 'validators': []},
            'name': {'required': False, 'validators': []},
        }

    def validate_code(self, value):
        if not value:
            return value
        code = str(value).strip().upper().replace(' ', '_')
        if not code:
            raise serializers.ValidationError("Role identifier code is required.")
        
        existing = Role.objects.filter(code=code, is_archived=False)
        if self.instance:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise serializers.ValidationError(f"Role code '{code}' is already in use by an active role.")
        return code

    def validate_name(self, value):
        if not value:
            return value
        name = str(value).strip()
        if not name:
            raise serializers.ValidationError("Role name is required.")
            
        existing = Role.objects.filter(name__iexact=name, is_archived=False)
        if self.instance:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise serializers.ValidationError(f"Role name '{name}' is already in use by an active role.")
        return name

    def get_allowed_pages(self, obj):
        return list(obj.permissions.values_list('code', flat=True))

    def _resolve_permissions(self, permission_codes):
        perms = []
        for pcode in permission_codes:
            perm = PagePermission.objects.filter(code=pcode).first()
            if not perm:
                parts = pcode.split(':')
                action_tokens = [p for p in parts if p in ('view', 'add', 'edit', 'delete')]
                non_action_tokens = [p for p in parts if p not in ('view', 'add', 'edit', 'delete')]
                base_code = ':'.join(non_action_tokens) if non_action_tokens else parts[0]
                action_desc = ', '.join(a.capitalize() for a in action_tokens) if action_tokens else 'Full'

                base_perm = PagePermission.objects.filter(code=base_code).first()
                clean_name = base_perm.name if base_perm else base_code.replace(':', ' - ').replace('-', ' ').title()

                perm, _ = PagePermission.objects.get_or_create(
                    code=pcode,
                    defaults={
                        'name': f"{clean_name} ({action_desc})",
                        'module': base_perm.module if base_perm else 'SYSTEM',
                        'icon': base_perm.icon if base_perm else 'fi fi-rr-check',
                        'description': f"Permission capabilities ({action_desc}) for {clean_name}"
                    }
                )
            if perm:
                perms.append(perm)
        return perms

    def create(self, validated_data):
        permission_codes = validated_data.pop('permission_codes', [])
        code = str(validated_data.get('code', '')).strip().upper().replace(' ', '_')
        if not code:
            raise serializers.ValidationError({"code": "Role code identifier is required."})
        validated_data['code'] = code

        if 'name' in validated_data:
            name = str(validated_data['name']).strip()
            if not name:
                raise serializers.ValidationError({"name": "Role name is required."})
            validated_data['name'] = name

            # Handle duplicate name collision on archived roles
            archived_name = Role.objects.filter(name=name, is_archived=True).exclude(code=code).first()
            if archived_name:
                archived_name.name = f"{archived_name.name} (Archived {archived_name.id})"
                archived_name.save()

        # Check if an archived role with this code exists; restore and update it
        archived_role = Role.objects.filter(code=code, is_archived=True).first()
        if archived_role:
            archived_role.is_archived = False
            archived_role.archived_at = None
            archived_role.archived_by = None
            for attr, val in validated_data.items():
                setattr(archived_role, attr, val)
            archived_role.save()
            role = archived_role
        else:
            role = Role.objects.create(**validated_data)

        if permission_codes:
            perms = self._resolve_permissions(permission_codes)
            role.permissions.set(perms)
        return role

    def update(self, instance, validated_data):
        if instance.code == 'SUPER_ADMIN' and 'code' in validated_data and validated_data['code'] != 'SUPER_ADMIN':
            raise serializers.ValidationError({"code": "Cannot change system code for Super Admin."})
        
        # System roles have fixed code identifiers
        if instance.is_system_role:
            validated_data.pop('code', None)
        elif 'code' in validated_data:
            validated_data['code'] = str(validated_data['code']).strip().upper().replace(' ', '_')

        if 'name' in validated_data:
            validated_data['name'] = str(validated_data['name']).strip()

        permission_codes = validated_data.pop('permission_codes', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if permission_codes is not None:
            if instance.code == 'SUPER_ADMIN':
                for required_code in ['dashboard', 'user-management', 'roles-permissions']:
                    if required_code not in permission_codes and f"{required_code}:view" not in permission_codes:
                        permission_codes.append(required_code)
            perms = self._resolve_permissions(permission_codes)
            instance.permissions.set(perms)
        return instance


from audit.serializers import AuditLogSerializer

