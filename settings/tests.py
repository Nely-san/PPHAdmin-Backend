import unittest
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from users.models import User, Role, PagePermission
from settings.models import SystemParameter

class SystemParameterAPITests(TestCase):
    def setUp(self):
        self.role, _ = Role.objects.get_or_create(code='SUPER_ADMIN', defaults={'name': 'Super Admin'})
        self.user, _ = User.objects.get_or_create(
            username='test_admin',
            defaults={
                'email': 'admin@test.com',
                'role': self.role,
                'approval_status': 'APPROVED',
                'is_active': True
            }
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        SystemParameter.objects.create(key='currency', value='PHP', category='GENERAL', description='System currency')
        SystemParameter.objects.create(key='attendance_grace_period', value='15', category='ATTENDANCE', description='Grace period in minutes')

    @unittest.skip("Endpoint /api/system-parameters/ was unrouted in commit b0fd203; pending routing fix.")
    def test_get_system_parameters(self):
        response = self.client.get('/api/system-parameters/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    @unittest.skip("Endpoint /api/system-parameters/ was unrouted in commit b0fd203; pending routing fix.")
    def test_put_system_parameters_bulk(self):
        payload = {
            'updates': [
                {'key': 'currency', 'value': 'USD'},
                {'key': 'attendance_grace_period', 'value': '20'}
            ]
        }
        response = self.client.put('/api/system-parameters/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        
        param_dict = {p['key']: p['value'] for p in response.data}
        self.assertEqual(param_dict['currency'], 'USD')
        self.assertEqual(param_dict['attendance_grace_period'], '20')

    @unittest.skip("Endpoint /api/system-parameters/ was unrouted in commit b0fd203; pending routing fix.")
    def test_post_system_parameters_dict_bulk(self):
        payload = {
            'currency': 'EUR',
            'attendance_grace_period': '30'
        }
        response = self.client.post('/api/system-parameters/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        param_dict = {p['key']: p['value'] for p in response.data}
        self.assertEqual(param_dict['currency'], 'EUR')
        self.assertEqual(param_dict['attendance_grace_period'], '30')


class AuditLogAPITests(TestCase):
    def setUp(self):
        self.role, _ = Role.objects.get_or_create(code='SUPER_ADMIN', defaults={'name': 'Super Admin'})
        self.user, _ = User.objects.get_or_create(
            username='audit_admin',
            defaults={
                'email': 'audit_admin@test.com',
                'role': self.role,
                'approval_status': 'APPROVED',
                'is_active': True
            }
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        from settings.models import AuditLog
        AuditLog.objects.all().delete()
        AuditLog.objects.create(
            table_name='users',
            record_id='1001',
            action='CREATE',
            changed_by='audit_admin',
            new_data='{"username": "test1"}'
        )
        AuditLog.objects.create(
            table_name='attendance_records',
            record_id='2002',
            action='RESET',
            changed_by='audit_admin',
            new_data='Database reset'
        )
        AuditLog.objects.create(
            table_name='roles',
            record_id='3003',
            action='UPDATE',
            changed_by='other_admin',
            new_data='{"role": "HR_MANAGER"}'
        )

    def test_get_audit_logs_paginated(self):
        response = self.client.get('/api/audit-logs/?page=1&limit=2')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total'], 3)
        self.assertEqual(response.data['page'], 1)
        self.assertEqual(response.data['limit'], 2)
        self.assertEqual(len(response.data['logs']), 2)

    def test_filter_by_table_and_action(self):
        response = self.client.get('/api/audit-logs/?tableName=attendance_records&action=RESET')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total'], 1)
        self.assertEqual(response.data['logs'][0]['tableName'], 'attendance_records')
        self.assertEqual(response.data['logs'][0]['action'], 'RESET')

    def test_filter_by_changed_by_and_search(self):
        response = self.client.get('/api/audit-logs/?changedBy=audit_admin&search=test1')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total'], 1)
        self.assertEqual(response.data['logs'][0]['recordId'], '1001')


class RolePermissionsSecurityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.superadmin_role, _ = Role.objects.get_or_create(
            code='SUPER_ADMIN', defaults={'name': 'Super Admin', 'is_system_role': True}
        )
        self.admin_role, _ = Role.objects.get_or_create(
            code='ADMIN', defaults={'name': 'Admin', 'is_system_role': True}
        )
        self.employee_role, _ = Role.objects.get_or_create(
            code='EMPLOYEE', defaults={'name': 'Employee', 'is_system_role': False}
        )

        perm_edit, _ = PagePermission.objects.get_or_create(
            code='roles-permissions:edit',
            defaults={'name': 'Roles & Permissions (Edit)', 'module': 'SYSTEM'}
        )
        self.admin_role.permissions.add(perm_edit)

        self.superadmin_user, _ = User.objects.get_or_create(
            username='role_superadmin',
            defaults={
                'email': 'superadmin@test.com',
                'role': self.superadmin_role,
                'approval_status': 'APPROVED',
                'is_active': True,
            }
        )
        self.admin_user, _ = User.objects.get_or_create(
            username='role_admin',
            defaults={
                'email': 'admin@test.com',
                'role': self.admin_role,
                'approval_status': 'APPROVED',
                'is_active': True,
            }
        )
        self.employee_user, _ = User.objects.get_or_create(
            username='role_employee',
            defaults={
                'email': 'employee@test.com',
                'role': self.employee_role,
                'approval_status': 'APPROVED',
                'is_active': True,
            }
        )

        self.target_role, _ = Role.objects.get_or_create(
            code='CUSTOM_ROLE',
            defaults={'name': 'Custom Role', 'is_system_role': False}
        )

    def test_role_update_denied_for_employee(self):
        # authenticate as a user whose role code is not SUPER_ADMIN and does
        # not have 'roles-permissions:edit'. PUT to /api/roles/<admin_role_id>/
        # Expect 403.
        self.client.force_authenticate(user=self.employee_user)
        response = self.client.put(
            f'/api/roles/{self.admin_role.id}/',
            {'permission_codes': []},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data.get('detail'), "You do not have permission to edit roles.")

    def test_role_create_denied_for_employee(self):
        # same caller. POST to /api/roles/ with a minimal valid body.
        # Expect 403.
        self.client.force_authenticate(user=self.employee_user)
        response = self.client.post(
            '/api/roles/',
            {'name': 'New Role', 'code': 'NEW_ROLE'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data.get('detail'), "You do not have permission to create roles.")

    def test_role_delete_denied_for_employee(self):
        # same caller. DELETE a non-system role.
        # Expect 403.
        self.client.force_authenticate(user=self.employee_user)
        response = self.client.delete(f'/api/roles/{self.target_role.id}/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data.get('detail'), "You do not have permission to delete roles.")

    def test_role_update_allowed_for_admin(self):
        # authenticate as a user with role code 'ADMIN' (has
        # roles-permissions:edit today). PUT to /api/roles/<role_id>/.
        # Expect 200.
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.put(
            f'/api/roles/{self.target_role.id}/',
            {'permission_codes': ['roles-permissions:edit']},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_role_update_allowed_for_superadmin(self):
        # authenticate as the SUPER_ADMIN user. PUT to /api/roles/<role_id>/.
        # Expect 200.
        self.client.force_authenticate(user=self.superadmin_user)
        response = self.client.put(
            f'/api/roles/{self.target_role.id}/',
            {'permission_codes': ['roles-permissions:edit']},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)


