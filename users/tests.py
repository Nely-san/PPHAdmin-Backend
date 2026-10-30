from django.apps import apps
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection
from django.db.migrations.executor import MigrationExecutor
from django.db.models.signals import post_save
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch
from users.models import (
    User,
    Role,
    PagePermission,
    Person,
    PersonProfile,
    CharacterReference,
    ensure_person_profile,
)
from biometrics_attendance.models import BiometricEnrollment


class CurrentUserPrivacyTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.employee_role, _ = Role.objects.get_or_create(
            code='EMPLOYEE',
            defaults={'name': 'Employee'},
        )

    def test_auth_me_masks_person_biometric_ids(self):
        employee = User.objects.create_user(
            username='privacy_employee',
            password='Password123!',
            role=self.employee_role,
        )
        person = Person.objects.filter(user=employee).first()
        if person is None:
            person = Person.objects.create(
                user=employee,
                name='Privacy Employee',
                biometric_id='BIO-SECRET-123',
                status='ACTIVE',
            )
        else:
            person.name = 'Privacy Employee'
            person.biometric_id = 'BIO-SECRET-123'
            person.status = 'ACTIVE'
            person.save(update_fields=['name', 'biometric_id', 'status'])
        employee = User.objects.get(pk=employee.pk)

        self.client.force_authenticate(employee)
        response = self.client.get('/api/auth/me/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        person = response.data['person']
        self.assertNotIn('biometric_id', person)
        self.assertNotIn('biometricId', person)
        self.assertEqual(
            response.data['biometrics'],
            {'is_enrolled': True, 'status': 'ENROLLED'},
        )

    def test_auth_me_handles_missing_person(self):
        employee = User.objects.create_user(
            username='no_person_admin',
            password='Password123!',
            role=self.employee_role,
        )
        auto_person = Person.objects.filter(user=employee).first()
        if auto_person is not None:
            auto_person.delete()
        employee = User.objects.get(pk=employee.pk)

        self.client.force_authenticate(employee)
        response = self.client.get('/api/auth/me/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data['person'])
        self.assertEqual(
            response.data['biometrics'],
            {'is_enrolled': False, 'status': 'NOT_ENROLLED'},
        )

    def test_admin_person_endpoint_keeps_both_biometric_keys(self):
        admin = User.objects.create_superuser(
            username='privacy_super_admin',
            password='Password123!',
        )
        employee = User.objects.create_user(
            username='admin_view_employee',
            password='Password123!',
            role=self.employee_role,
        )
        person = Person.objects.filter(user=employee).first()
        if person is None:
            person = Person.objects.create(
                user=employee,
                name='Admin View Employee',
                biometric_id='BIO-ADMIN-123',
                status='ACTIVE',
            )
        else:
            person.name = 'Admin View Employee'
            person.biometric_id = 'BIO-ADMIN-123'
            person.status = 'ACTIVE'
            person.save(update_fields=['name', 'biometric_id', 'status'])

        self.client.force_authenticate(admin)
        response = self.client.get(f'/api/persons/{person.id}/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['biometric_id'], 'BIO-ADMIN-123')
        self.assertEqual(response.data['biometricId'], 'BIO-ADMIN-123')


class BiometricEndpointTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.hr_role, _ = Role.objects.get_or_create(
            code='HR_MANAGER',
            defaults={'name': 'HR Manager'},
        )
        self.employee_role, _ = Role.objects.get_or_create(
            code='EMPLOYEE',
            defaults={'name': 'Employee'},
        )
        self.edit_permission, _ = PagePermission.objects.get_or_create(
            code='employees:edit',
            defaults={'name': 'Employees Edit', 'module': 'HR'},
        )
        self.delete_permission, _ = PagePermission.objects.get_or_create(
            code='employees:delete',
            defaults={'name': 'Employees Delete', 'module': 'HR'},
        )
        self.add_permission, _ = PagePermission.objects.get_or_create(
            code='employees:add',
            defaults={'name': 'Employees Add', 'module': 'HR'},
        )
        self.admin = User.objects.create_superuser(
            username='biometric_admin',
            password='Password123!',
        )
        self.person = Person.objects.create(
            name='Endpoint Employee',
            status='ACTIVE',
        )

    def test_link_creates_enrollment_and_updates_person(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            f'/api/persons/{self.person.id}/link-biometric/',
            {'external_biometric_id': ' LINK-100 '},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.person.refresh_from_db()
        self.assertEqual(self.person.biometric_id, 'LINK-100')
        enrollment = BiometricEnrollment.objects.get(person=self.person)
        self.assertEqual(enrollment.external_biometric_id, 'LINK-100')
        self.assertEqual(enrollment.status, 'ENROLLED')
        self.assertTrue(enrollment.is_active)

    def test_link_duplicate_external_id_returns_400_without_write(self):
        other = Person.objects.create(name='Other Person', status='ACTIVE')
        BiometricEnrollment.objects.create(
            person=other,
            external_biometric_id='DUPLICATE-ID',
            status='ENROLLED',
            is_active=True,
        )
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            f'/api/persons/{self.person.id}/link-biometric/',
            {'external_biometric_id': 'DUPLICATE-ID'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data['detail'],
            'This biometric ID is already actively enrolled to another person.',
        )
        self.person.refresh_from_db()
        self.assertIsNone(self.person.biometric_id)

    def test_link_duplicate_active_person_returns_400_without_write(self):
        old = BiometricEnrollment.objects.create(
            person=self.person,
            external_biometric_id='OLD-ID',
            status='ENROLLED',
            is_active=True,
        )
        self.person.biometric_id = 'OLD-ID'
        self.person.save(update_fields=['biometric_id'])
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            f'/api/persons/{self.person.id}/link-biometric/',
            {'external_biometric_id': 'NEW-ID'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data['detail'],
            'This person already has an active biometric enrollment.',
        )
        old.refresh_from_db()
        self.person.refresh_from_db()
        self.assertEqual(old.status, 'ENROLLED')
        self.assertTrue(old.is_active)
        self.assertEqual(self.person.biometric_id, 'OLD-ID')

    def test_link_database_failure_rolls_back_person_and_enrollment(self):
        self.client.force_authenticate(self.admin)
        with patch(
            'biometrics_attendance.models.BiometricEnrollment.objects.create',
            side_effect=IntegrityError('database failure'),
        ):
            response = self.client.post(
                f'/api/persons/{self.person.id}/link-biometric/',
                {'external_biometric_id': 'ROLLBACK-ID'},
                format='json',
            )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.person.refresh_from_db()
        self.assertIsNone(self.person.biometric_id)
        self.assertFalse(
            BiometricEnrollment.objects.filter(person=self.person).exists()
        )

    def test_link_second_write_failure_rolls_back_first_write(self):
        old = BiometricEnrollment.objects.create(
            person=self.person,
            external_biometric_id='OLD-ROLLBACK-ID',
            status='ENROLLED',
            is_active=True,
        )
        self.person.biometric_id = 'OLD-ROLLBACK-ID'
        self.person.save(update_fields=['biometric_id'])
        self.client.force_authenticate(self.admin)

        with patch(
            'biometrics_attendance.models.BiometricEnrollment.objects.create',
            side_effect=IntegrityError('forced second-write failure'),
        ):
            response = self.client.post(
                f'/api/persons/{self.person.id}/link-biometric/',
                {'external_biometric_id': 'NEW-ROLLBACK-ID'},
                format='json',
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        old.refresh_from_db()
        self.person.refresh_from_db()
        self.assertEqual(old.status, 'ENROLLED')
        self.assertTrue(old.is_active)
        self.assertEqual(self.person.biometric_id, 'OLD-ROLLBACK-ID')
        self.assertFalse(
            BiometricEnrollment.objects.filter(
                person=self.person,
                external_biometric_id='NEW-ROLLBACK-ID',
            ).exists()
        )

    def test_link_lock_order_is_person_then_enrollment(self):
        calls = []
        original_person_lock = Person.objects.select_for_update
        original_enrollment_lock = BiometricEnrollment.objects.select_for_update

        def lock_person():
            calls.append('person')
            return original_person_lock()

        def lock_enrollment():
            calls.append('enrollment')
            return original_enrollment_lock()

        self.client.force_authenticate(self.admin)
        with patch.object(
            Person.objects,
            'select_for_update',
            side_effect=lock_person,
        ), patch.object(
            BiometricEnrollment.objects,
            'select_for_update',
            side_effect=lock_enrollment,
        ):
            response = self.client.post(
                f'/api/persons/{self.person.id}/link-biometric/',
                {'external_biometric_id': 'LOCK-ORDER-ID'},
                format='json',
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(calls[:2], ['person', 'enrollment'])

    def test_link_add_only_user_forbidden(self):
        user = User.objects.create_user(
            username='add_only_biometric',
            password='Password123!',
            role=self.hr_role,
        )
        user.custom_permissions.add(self.add_permission)
        self.client.force_authenticate(user)
        response = self.client.post(
            f'/api/persons/{self.person.id}/link-biometric/',
            {'external_biometric_id': 'ADD-ONLY-ID'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unlink_revokes_and_clears_person(self):
        enrollment = BiometricEnrollment.objects.create(
            person=self.person,
            external_biometric_id='UNLINK-ID',
            status='ENROLLED',
            is_active=True,
        )
        self.person.biometric_id = 'UNLINK-ID'
        self.person.save(update_fields=['biometric_id'])
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            f'/api/persons/{self.person.id}/unlink-biometric/',
            {},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        enrollment.refresh_from_db()
        self.person.refresh_from_db()
        self.assertEqual(enrollment.status, 'REVOKED')
        self.assertFalse(enrollment.is_active)
        self.assertIsNone(self.person.biometric_id)

    def test_unlink_edit_only_user_forbidden(self):
        user = User.objects.create_user(
            username='edit_only_biometric',
            password='Password123!',
            role=self.hr_role,
        )
        user.custom_permissions.add(self.edit_permission)
        self.client.force_authenticate(user)
        response = self.client.post(
            f'/api/persons/{self.person.id}/unlink-biometric/',
            {},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unlink_second_write_failure_rolls_back(self):
        enrollment = BiometricEnrollment.objects.create(
            person=self.person,
            external_biometric_id='UNLINK-ROLLBACK-ID',
            status='ENROLLED',
            is_active=True,
        )
        self.person.biometric_id = 'UNLINK-ROLLBACK-ID'
        self.person.save(update_fields=['biometric_id'])
        self.client.force_authenticate(self.admin)
        self.client.raise_request_exception = False

        with patch.object(
            Person,
            'save',
            side_effect=IntegrityError('forced unlink second-write failure'),
        ):
            response = self.client.post(
                f'/api/persons/{self.person.id}/unlink-biometric/',
                {},
                format='json',
            )

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        enrollment.refresh_from_db()
        self.person.refresh_from_db()
        self.assertEqual(enrollment.status, 'ENROLLED')
        self.assertTrue(enrollment.is_active)
        self.assertEqual(self.person.biometric_id, 'UNLINK-ROLLBACK-ID')

    def test_unlink_lock_order_is_person_then_enrollment(self):
        BiometricEnrollment.objects.create(
            person=self.person,
            external_biometric_id='UNLINK-LOCK-ID',
            status='ENROLLED',
            is_active=True,
        )
        self.person.biometric_id = 'UNLINK-LOCK-ID'
        self.person.save(update_fields=['biometric_id'])
        calls = []
        original_person_lock = Person.objects.select_for_update
        original_enrollment_lock = BiometricEnrollment.objects.select_for_update

        def lock_person():
            calls.append('person')
            return original_person_lock()

        def lock_enrollment():
            calls.append('enrollment')
            return original_enrollment_lock()

        self.client.force_authenticate(self.admin)
        with patch.object(
            Person.objects,
            'select_for_update',
            side_effect=lock_person,
        ), patch.object(
            BiometricEnrollment.objects,
            'select_for_update',
            side_effect=lock_enrollment,
        ):
            response = self.client.post(
                f'/api/persons/{self.person.id}/unlink-biometric/',
                {},
                format='json',
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(calls[:2], ['person', 'enrollment'])

    def test_unlink_without_active_enrollment_returns_404(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            f'/api/persons/{self.person.id}/unlink-biometric/',
            {},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_put_with_biometric_id_ignores_write(self):
        self.person.biometric_id = 'UNCHANGED-ID'
        self.person.save(update_fields=['biometric_id'])
        self.client.force_authenticate(self.admin)
        response = self.client.put(
            f'/api/persons/{self.person.id}/',
            {'name': 'Updated Name', 'biometricId': '101'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.person.refresh_from_db()
        self.assertEqual(self.person.name, 'Updated Name')
        self.assertEqual(self.person.biometric_id, 'UNCHANGED-ID')
        self.assertFalse(
            BiometricEnrollment.objects.filter(person=self.person).exists()
        )

    def test_link_audit_failure_does_not_roll_back(self):
        from unittest.mock import patch
        self.client.force_authenticate(self.admin)
        with patch('users.views.record_audit_log', side_effect=RuntimeError('audit unavailable')):
            response = self.client.post(
                f'/api/persons/{self.person.id}/link-biometric/',
                {'external_biometric_id': 'AUDIT-LINK-ID'},
                format='json',
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.person.refresh_from_db()
        self.assertEqual(self.person.biometric_id, 'AUDIT-LINK-ID')

    def test_unlink_audit_failure_does_not_roll_back(self):
        from unittest.mock import patch
        BiometricEnrollment.objects.create(
            person=self.person,
            external_biometric_id='AUDIT-UNLINK-ID',
            status='ENROLLED',
            is_active=True,
        )
        self.person.biometric_id = 'AUDIT-UNLINK-ID'
        self.person.save(update_fields=['biometric_id'])
        self.client.force_authenticate(self.admin)
        with patch('users.views.record_audit_log', side_effect=RuntimeError('audit unavailable')):
            response = self.client.post(
                f'/api/persons/{self.person.id}/unlink-biometric/',
                {},
                format='json',
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.person.refresh_from_db()
        self.assertIsNone(self.person.biometric_id)


class AccountApprovalTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

        # Seed Page Permissions
        self.perm_dash, _ = PagePermission.objects.get_or_create(code='dashboard', defaults={'name': 'Dashboard', 'module': 'SYSTEM'})
        self.perm_emp, _ = PagePermission.objects.get_or_create(code='employees', defaults={'name': 'Employees', 'module': 'HR'})
        self.perm_payroll, _ = PagePermission.objects.get_or_create(code='payroll', defaults={'name': 'Payroll', 'module': 'PAYROLL'})
        self.perm_users, _ = PagePermission.objects.get_or_create(code='user-management', defaults={'name': 'User Management', 'module': 'SYSTEM'})

        # Seed Roles
        self.sa_role, _ = Role.objects.get_or_create(code='SUPER_ADMIN', defaults={'name': 'Super Admin', 'is_system_role': True})
        self.hr_role, _ = Role.objects.get_or_create(code='HR_MANAGER', defaults={'name': 'HR Manager'})
        self.hr_role.permissions.add(self.perm_dash, self.perm_emp)

        self.emp_role, _ = Role.objects.get_or_create(code='EMPLOYEE', defaults={'name': 'Employee'})
        self.emp_role.permissions.add(self.perm_dash)

        # Create Super Admin User
        self.super_admin = User.objects.create_superuser(
            username='admin_boss',
            password='Password123!'
        )

    def test_registration_creates_pending_user(self):
        response = self.client.post('/api/auth/register/', {
            'username': 'new_applicant',
            'email': 'applicant@example.com',
            'password': 'Password123!'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        user = User.objects.get(username='new_applicant')
        self.assertEqual(user.approval_status, 'PENDING')
        self.assertFalse(user.is_active)

    def test_pending_approvals_list(self):
        # Register a pending user
        self.client.post('/api/auth/register/', {
            'username': 'applicant1',
            'email': 'applicant1@example.com',
            'password': 'Password123!'
        })

        self.client.force_authenticate(user=self.super_admin)
        response = self.client.get('/api/users/pending-approvals/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['username'], 'applicant1')
        self.assertEqual(response.data[0]['approval_status'], 'PENDING')

    def test_approve_user_with_role_and_custom_pages(self):
        reg_response = self.client.post('/api/auth/register/', {
            'username': 'hr_applicant',
            'email': 'hr@example.com',
            'password': 'Password123!'
        })
        user_id = reg_response.data['id']

        self.client.force_authenticate(user=self.super_admin)
        approve_response = self.client.post(f'/api/users/{user_id}/approve/', {
            'role_code': 'HR_MANAGER',
            'page_codes': ['payroll']  # Additional custom page
        }, format='json')
        self.assertEqual(approve_response.status_code, status.HTTP_200_OK)
        
        user = User.objects.get(id=user_id)
        self.assertEqual(user.approval_status, 'APPROVED')
        self.assertTrue(user.is_active)
        self.assertEqual(user.role.code, 'HR_MANAGER')
        self.assertEqual(user.approved_by, self.super_admin)
        self.assertIsNotNone(user.approved_at)

        # Allowed pages includes HR role pages (dashboard, employees) + custom (payroll)
        allowed_pages = approve_response.data['allowed_pages']
        self.assertIn('dashboard', allowed_pages)
        self.assertIn('employees', allowed_pages)
        self.assertIn('payroll', allowed_pages)

    def test_reject_user_with_reason(self):
        reg_response = self.client.post('/api/auth/register/', {
            'username': 'bad_applicant',
            'email': 'bad@example.com',
            'password': 'Password123!'
        })
        user_id = reg_response.data['id']

        self.client.force_authenticate(user=self.super_admin)
        reject_response = self.client.post(f'/api/users/{user_id}/reject/', {
            'rejection_reason': 'Invalid company affiliation.'
        }, format='json')
        self.assertEqual(reject_response.status_code, status.HTTP_200_OK)

        user = User.objects.get(id=user_id)
        self.assertEqual(user.approval_status, 'REJECTED')
        self.assertFalse(user.is_active)
        self.assertEqual(user.rejection_reason, 'Invalid company affiliation.')
        self.assertEqual(user.approved_by, self.super_admin)

    def test_unauthorized_user_cannot_approve_or_reject_account(self):
        # Create unprivileged employee
        emp_user = User.objects.create_user(username='regular_emp', password='password123', role=self.emp_role)
        # Create pending candidate
        candidate = User.objects.create_user(username='candidate_user', password='password123', role=self.emp_role)

        # Authenticate as employee (no user-management:edit permission)
        self.client.force_authenticate(user=emp_user)
        approve_res = self.client.post(f'/api/users/{candidate.id}/approve/', {
            'role_id': self.emp_role.id
        })
        self.assertEqual(approve_res.status_code, status.HTTP_403_FORBIDDEN)

        reject_res = self.client.post(f'/api/users/{candidate.id}/reject/', {
            'rejection_reason': 'Unauthorized rejection attempt'
        })
        self.assertEqual(reject_res.status_code, status.HTTP_403_FORBIDDEN)

        # Unauthenticated request
        self.client.force_authenticate(user=None)
        unauth_res = self.client.post(f'/api/users/{candidate.id}/approve/', {
            'role_id': self.emp_role.id
        })
        self.assertEqual(unauth_res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_pending_approvals_view_permission_gating(self):
        """
        Gating test for GET /api/users/pending-approvals/:
        - Unauthenticated -> 401
        - Authenticated without 'user-management:view' -> 403
        - Authenticated with 'user-management:view' -> 200
        """
        # Register a pending user
        self.client.post('/api/auth/register/', {
            'username': 'pending_candidate_view',
            'email': 'cand_view@example.com',
            'password': 'Password123!'
        })

        # 1. Unauthenticated request -> 401
        self.client.force_authenticate(user=None)
        res_unauth = self.client.get('/api/users/pending-approvals/')
        self.assertEqual(res_unauth.status_code, status.HTTP_401_UNAUTHORIZED)

        # 2. Authenticated user without user-management view -> 403
        unprivileged_user = User.objects.create_user(
            username='viewer_denied',
            password='password123',
            role=self.emp_role
        )
        self.client.force_authenticate(user=unprivileged_user)
        res_denied = self.client.get('/api/users/pending-approvals/')
        self.assertEqual(res_denied.status_code, status.HTTP_403_FORBIDDEN)

        # 3. Authenticated user with 'user-management:view' custom permission -> 200
        perm_view, _ = PagePermission.objects.get_or_create(
            code='user-management:view',
            defaults={'name': 'User Management View', 'module': 'SYSTEM'}
        )
        unprivileged_user.custom_permissions.add(perm_view)
        res_allowed = self.client.get('/api/users/pending-approvals/')
        self.assertEqual(res_allowed.status_code, status.HTTP_200_OK)

    def test_user_lifecycle_actions_permission_gating(self):
        """
        Gating test for archive_user, unarchive_user, and destroy:
        - archive_user requires 'user-management:delete' (or ADMIN/SUPER_ADMIN)
        - unarchive_user requires 'user-management:edit' (or ADMIN/SUPER_ADMIN)
        - destroy requires 'user-management:delete' (or ADMIN/SUPER_ADMIN)
        """
        emp_user = User.objects.create_user(username='regular_staff', password='password123', role=self.emp_role)
        target = User.objects.create_user(username='target_subject', password='password123', role=self.emp_role)

        perm_delete, _ = PagePermission.objects.get_or_create(
            code='user-management:delete',
            defaults={'name': 'User Management Delete', 'module': 'SYSTEM'}
        )
        perm_edit, _ = PagePermission.objects.get_or_create(
            code='user-management:edit',
            defaults={'name': 'User Management Edit', 'module': 'SYSTEM'}
        )

        # --- Test archive_user ---
        self.client.force_authenticate(user=emp_user)
        res_arch_denied = self.client.post(f'/api/users/{target.id}/archive/')
        self.assertEqual(res_arch_denied.status_code, status.HTTP_403_FORBIDDEN)

        emp_user.custom_permissions.add(perm_delete)
        res_arch_allowed = self.client.post(f'/api/users/{target.id}/archive/')
        self.assertEqual(res_arch_allowed.status_code, status.HTTP_200_OK)
        target.refresh_from_db()
        self.assertTrue(target.is_archived)

        # --- Test unarchive_user ---
        emp_user.custom_permissions.remove(perm_delete)
        self.client.force_authenticate(user=emp_user)
        res_unarch_denied = self.client.post(f'/api/users/{target.id}/unarchive/')
        self.assertEqual(res_unarch_denied.status_code, status.HTTP_403_FORBIDDEN)

        emp_user.custom_permissions.add(perm_edit)
        res_unarch_allowed = self.client.post(f'/api/users/{target.id}/unarchive/')
        self.assertEqual(res_unarch_allowed.status_code, status.HTTP_200_OK)
        target.refresh_from_db()
        self.assertFalse(target.is_archived)

        # --- Test destroy ---
        emp_user.custom_permissions.remove(perm_edit)
        res_del_denied = self.client.delete(f'/api/users/{target.id}/')
        self.assertEqual(res_del_denied.status_code, status.HTTP_403_FORBIDDEN)

        emp_user.custom_permissions.add(perm_delete)
        res_del_allowed = self.client.delete(f'/api/users/{target.id}/')
        self.assertEqual(res_del_allowed.status_code, status.HTTP_204_NO_CONTENT)

    def test_cannot_reject_super_admin(self):
        self.client.force_authenticate(user=self.super_admin)
        reject_response = self.client.post(f'/api/users/{self.super_admin.id}/reject/', {
            'rejection_reason': 'Try to reject super admin'
        })
        self.assertEqual(reject_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_pending_user_cannot_login(self):
        # Register a new user
        self.client.post('/api/auth/register/', {
            'username': 'pending_guy',
            'email': 'pending@example.com',
            'password': 'SecretPassword123!'
        })

        # Attempt to login via username
        login_response = self.client.post('/api/auth/login/', {
            'username': 'pending_guy',
            'password': 'SecretPassword123!'
        })
        self.assertEqual(login_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('pending approval', str(login_response.data).lower())

        # Attempt to login via email
        login_email_response = self.client.post('/api/auth/login/', {
            'username': 'pending@example.com',
            'password': 'SecretPassword123!'
        })
        self.assertEqual(login_email_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('pending approval', str(login_email_response.data).lower())

    def test_rejected_user_cannot_login(self):
        # Register a new user
        reg_response = self.client.post('/api/auth/register/', {
            'username': 'rejected_guy',
            'email': 'rejected@example.com',
            'password': 'SecretPassword123!'
        })
        user_id = reg_response.data['id']

        # Super admin rejects user
        self.client.force_authenticate(user=self.super_admin)
        self.client.post(f'/api/users/{user_id}/reject/', {
            'rejection_reason': 'Not eligible.'
        })
        self.client.force_authenticate(user=None)

        # Attempt to login
        login_response = self.client.post('/api/auth/login/', {
            'username': 'rejected_guy',
            'password': 'SecretPassword123!'
        })
        self.assertEqual(login_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('rejected', str(login_response.data).lower())

    def test_approved_user_can_login(self):
        # Register a new user
        reg_response = self.client.post('/api/auth/register/', {
            'username': 'approved_guy',
            'email': 'approved@example.com',
            'password': 'SecretPassword123!'
        })
        user_id = reg_response.data['id']

        # Super admin approves user
        self.client.force_authenticate(user=self.super_admin)
        self.client.post(f'/api/users/{user_id}/approve/', {
            'role_code': 'EMPLOYEE',
            'page_codes': ['dashboard']
        })
        self.client.force_authenticate(user=None)

        # Approved user can successfully login
        login_response = self.client.post('/api/auth/login/', {
            'username': 'approved_guy',
            'password': 'SecretPassword123!'
        })
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        self.assertIn('access', login_response.data)
        self.assertEqual(login_response.data['user']['username'], 'approved_guy')
        self.assertEqual(login_response.data['user']['approval_status'], 'APPROVED')
        self.assertTrue(login_response.data['user']['is_active'])

    def test_nonexistent_user_login_error(self):
        login_response = self.client.post('/api/auth/login/', {
            'username': 'nonexistent_user_12345',
            'password': 'SomePassword123!'
        })
        self.assertEqual(login_response.status_code, status.HTTP_400_BAD_REQUEST)
        detail = login_response.data.get('detail')
        detail_str = detail[0] if isinstance(detail, list) else detail
        self.assertEqual(detail_str, 'No account found with that username or email.')

    def test_wrong_password_login_error(self):
        login_response = self.client.post('/api/auth/login/', {
            'username': 'admin_boss',
            'password': 'WrongPassword123!'
        })
        self.assertEqual(login_response.status_code, status.HTTP_400_BAD_REQUEST)
        detail = login_response.data.get('detail')
        detail_str = detail[0] if isinstance(detail, list) else detail
        self.assertEqual(detail_str, 'Incorrect password. Please try again.')


class NotificationAndAttendanceTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.role, _ = Role.objects.get_or_create(code='SUPER_ADMIN', defaults={'name': 'Super Admin'})
        self.user, _ = User.objects.get_or_create(
            username='notify_user',
            defaults={
                'email': 'notify@example.com',
                'role': self.role,
                'approval_status': 'APPROVED',
                'is_active': True
            }
        )
        self.client.force_authenticate(user=self.user)

        from users.models import Notification
        self.notif1 = Notification.objects.create(
            user=self.user,
            title='Attendance Alert',
            message='Clock-in missing',
            is_read=False,
            category='ATTENDANCE'
        )
        self.notif2 = Notification.objects.create(
            user=self.user,
            title='Payroll Generated',
            message='Payroll batch locked',
            is_read=False,
            category='PAYROLL'
        )

    def test_notifications_list_and_unread_count(self):
        # List
        res = self.client.get('/api/notifications/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 2)
        self.assertEqual(res.data[0]['userId'], str(self.user.id))

        # Unread count
        count_res = self.client.get('/api/notifications/unread-count')
        self.assertEqual(count_res.status_code, status.HTTP_200_OK)
        self.assertEqual(count_res.data['unreadCount'], 2)

    def test_mark_single_notification_read(self):
        res = self.client.put(f'/api/notifications/{self.notif1.id}/read')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data['isRead'])

        count_res = self.client.get('/api/notifications/unread-count')
        self.assertEqual(count_res.data['unreadCount'], 1)

    def test_mark_all_notifications_read(self):
        res = self.client.put('/api/notifications/read-all')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['count'], 2)

        count_res = self.client.get('/api/notifications/unread-count')
        self.assertEqual(count_res.data['unreadCount'], 0)

    def test_notification_preferences_get_and_update(self):
        # GET default
        res = self.client.get('/api/notifications/preferences')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data['enableInApp'])

        # PUT update
        update_res = self.client.put('/api/notifications/preferences', {
            'enableInApp': False,
            'notifyAttendance': False
        }, format='json')
        self.assertEqual(update_res.status_code, status.HTTP_200_OK)
        self.assertFalse(update_res.data['enableInApp'])
        self.assertFalse(update_res.data['notifyAttendance'])
        self.assertTrue(update_res.data['notifyPayroll'])

    def test_attendance_reset(self):
        # Create a newly imported temporary person
        Person.objects.create(
            name='Temp Import Bio',
            biometric_id='9999',
            is_newly_imported=True,
            status='ACTIVE'
        )

        res = self.client.post('/api/attendance/reset/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['status'], 'success')

        # Verify person is archived
        p = Person.objects.get(name='Temp Import Bio')
        self.assertTrue(p.is_archived)

    def test_archive_and_restore_user_account_via_patch_and_endpoint(self):
        emp_role, _ = Role.objects.get_or_create(code='EMPLOYEE', defaults={'name': 'Employee'})
        # Create a regular active user
        target_user = User.objects.create_user(
            username='staff_member',
            password='Password123!',
            role=emp_role,
            is_active=True,
            approval_status='APPROVED'
        )
        self.client.force_authenticate(user=self.user)

        # 1. Archive via PATCH with isArchived / is_archived
        patch_res = self.client.patch(f'/api/users/{target_user.id}/', {
            'isArchived': True
        }, format='json')
        self.assertEqual(patch_res.status_code, status.HTTP_200_OK)
        target_user.refresh_from_db()
        self.assertTrue(target_user.is_archived)
        self.assertIsNotNone(target_user.archived_at)

        # 2. Restore via PATCH
        patch_res2 = self.client.patch(f'/api/users/{target_user.id}/', {
            'isArchived': False
        }, format='json')
        self.assertEqual(patch_res2.status_code, status.HTTP_200_OK)
        target_user.refresh_from_db()
        self.assertFalse(target_user.is_archived)
        self.assertIsNone(target_user.archived_at)

        # 3. Archive via POST /archive/
        archive_res = self.client.post(f'/api/users/{target_user.id}/archive/')
        self.assertEqual(archive_res.status_code, status.HTTP_200_OK)
        target_user.refresh_from_db()
        self.assertTrue(target_user.is_archived)

        # 4. Unarchive via POST /unarchive/
        unarchive_res = self.client.post(f'/api/users/{target_user.id}/unarchive/')
        self.assertEqual(unarchive_res.status_code, status.HTTP_200_OK)
        target_user.refresh_from_db()
        self.assertFalse(target_user.is_archived)


from unittest.mock import patch, MagicMock
from users import views as user_views

class GoogleAuthSecurityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.emp_role, _ = Role.objects.get_or_create(code='EMPLOYEE', defaults={'name': 'Employee'})

    def test_rejects_unverified_raw_email_payload(self):
        # Attempting to login by passing raw email without a Google token must be rejected
        response = self.client.post('/api/auth/google-login/', {
            'email': 'spoofed@example.com',
            'name': 'Spoofed User'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('credential is required', response.data.get('error', '').lower())

    def test_rejects_invalid_google_id_token(self):
        response = self.client.post('/api/auth/google-login/', {
            'id_token': 'invalid.fake.jwt_token_payload'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('invalid google id token', response.data.get('error', '').lower())

    def test_google_signup_provisions_pending_user(self):
        mock_id_token = MagicMock()
        mock_id_token.verify_oauth2_token.return_value = {
            'email': 'new_google_user@example.com',
            'given_name': 'Google',
            'family_name': 'User',
            'name': 'Google User',
            'email_verified': True
        }
        mock_google_requests = MagicMock()
        with patch.object(user_views, 'id_token', mock_id_token), patch.object(user_views, 'google_requests', mock_google_requests):
            response = self.client.post('/api/auth/google-login/', {
                'id_token': 'valid_simulated_jwt_token'
            }, format='json')

            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            self.assertTrue(response.data.get('is_new_user'))
            self.assertEqual(response.data.get('approval_status'), 'PENDING')

            user = User.objects.get(email='new_google_user@example.com')
            self.assertEqual(user.approval_status, 'PENDING')
            self.assertFalse(user.is_active)
            self.assertTrue(Person.objects.filter(user=user).exists())

    def test_google_login_approved_user(self):
        mock_id_token = MagicMock()
        mock_id_token.verify_oauth2_token.return_value = {
            'email': 'existing_user@example.com',
            'name': 'Existing Verified User',
            'email_verified': True
        }
        mock_google_requests = MagicMock()

        user = User.objects.create(
            username='existing_google',
            email='existing_user@example.com',
            role=self.emp_role,
            approval_status='APPROVED',
            is_active=True
        )

        with patch.object(user_views, 'id_token', mock_id_token), patch.object(user_views, 'google_requests', mock_google_requests):
            response = self.client.post('/api/auth/google-login/', {
                'id_token': 'valid_simulated_jwt_token'
            }, format='json')

            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIn('access', response.data)
            self.assertFalse(response.data.get('is_new_user'))


class UserManagementSchoolTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.sa_role, _ = Role.objects.get_or_create(code='SUPER_ADMIN', defaults={'name': 'Super Admin', 'is_system_role': True})
        self.ojt_role, _ = Role.objects.get_or_create(code='OJT', defaults={'name': 'OJT / Intern', 'is_system_role': False})
        self.emp_role, _ = Role.objects.get_or_create(code='EMPLOYEE', defaults={'name': 'Employee', 'is_system_role': False})

        self.super_admin = User.objects.create_superuser(
            username='admin_boss',
            password='Password123!'
        )
        self.client.force_authenticate(user=self.super_admin)

    def test_create_ojt_user_saves_school_name(self):
        response = self.client.post('/api/users/', {
            'username': 'ojt_user_test',
            'email': 'ojt@university.edu',
            'password': 'Password123!',
            'role': 'OJT',
            'school_name': 'Polytechnic University of the Philippines'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        user = User.objects.get(username='ojt_user_test')
        self.assertEqual(user.role.code, 'OJT')
        self.assertIsNotNone(user.person)
        self.assertEqual(user.person.school_name, 'Polytechnic University of the Philippines')
        self.assertEqual(user.person.person_type, 'OJT')

    def test_create_ojt_user_with_linked_person_saves_school_name(self):
        person = Person.objects.create(
            name='Jane Doe',
            person_type='EMPLOYEE',
            status='ACTIVE'
        )

        response = self.client.post('/api/users/', {
            'username': 'janedoe',
            'email': 'janedoe@university.edu',
            'password': 'Password123!',
            'role': 'OJT',
            'person_id': str(person.id),
            'school_name': 'University of the Philippines'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        user = User.objects.get(username='janedoe')
        person.refresh_from_db()
        self.assertEqual(person.user, user)
        self.assertEqual(person.school_name, 'University of the Philippines')
        self.assertEqual(person.person_type, 'OJT')

    def test_update_user_updates_school_name(self):
        user = User.objects.create(
            username='update_school_user',
            email='school@test.com',
            role=self.ojt_role,
            approval_status='APPROVED',
            is_active=True
        )
        person = user.person
        person.school_name = 'Old University'
        person.save()

        response = self.client.patch(f'/api/users/{user.id}/', {
            'schoolName': 'New University of Science and Tech'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        person.refresh_from_db()
        self.assertEqual(person.school_name, 'New University of Science and Tech')


class PersonProfileSelfServiceApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.role, _ = Role.objects.get_or_create(
            code='EMPLOYEE',
            defaults={'name': 'Employee'},
        )
        self.user = User.objects.create_user(
            username='profile_api_employee',
            password='Password123!',
            role=self.role,
        )
        self.person = Person.objects.filter(user=self.user).first()
        if self.person is None:
            self.person = Person.objects.create(
                user=self.user,
                name='Profile API Employee',
                status='ACTIVE',
            )
        self.profile = self.person.profile_extension
        self.client.force_authenticate(self.user)

    def test_patch_profile_updates_allowed_fields(self):
        response = self.client.patch('/api/auth/me/', {
            'house_number': '123',
            'city_municipality': 'Quezon City',
            'highest_education_attainment': 'College',
            'course': 'Computer Science',
            'year_graduated': 2024,
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.house_number, '123')
        self.assertEqual(self.profile.city_municipality, 'Quezon City')
        self.assertEqual(self.profile.course, 'Computer Science')
        self.assertEqual(self.profile.year_graduated, 2024)
        self.assertEqual(response.data['profile']['house_number'], '123')

    def test_patch_profile_rejects_locked_fields(self):
        self.profile.tin_number = 'OLD-TIN'
        self.profile.property_status = 'OLD-STATUS'
        self.profile.save()

        response = self.client.patch('/api/auth/me/', {
            'tin_number': 'NEW-TIN',
            'property_status': 'ACCREDITED',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.tin_number, 'OLD-TIN')
        self.assertEqual(self.profile.property_status, 'OLD-STATUS')

    def test_patch_character_references_crud(self):
        first = CharacterReference.objects.create(
            person_profile=self.profile,
            name='Old Reference',
            contact_number='09170000001',
        )
        deleted = CharacterReference.objects.create(
            person_profile=self.profile,
            name='Delete Reference',
            contact_number='09170000002',
        )

        response = self.client.patch('/api/auth/me/', {
            'character_references': [
                {
                    'id': str(first.id),
                    'name': 'Updated Reference',
                    'contact_number': '09179999999',
                    'relationship': 'Former Manager',
                },
                {
                    'name': 'New Reference',
                    'contact_number': '09178888888',
                    'relationship': 'Colleague',
                },
            ],
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        first.refresh_from_db()
        self.assertEqual(first.name, 'Updated Reference')
        self.assertEqual(first.contact_number, '09179999999')
        self.assertFalse(CharacterReference.objects.filter(pk=deleted.pk).exists())
        self.assertTrue(CharacterReference.objects.filter(
            person_profile=self.profile,
            name='New Reference',
        ).exists())

    def test_patch_rejects_more_than_5_references(self):
        response = self.client.patch('/api/auth/me/', {
            'character_references': [
                {'name': f'Reference {index}', 'contact_number': f'0917000000{index}'}
                for index in range(6)
            ],
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(
            CharacterReference.objects.filter(person_profile=self.profile).exists()
        )

    def test_patch_atomicity(self):
        self.profile.house_number = 'Before'
        self.profile.save()
        old_reference_count = CharacterReference.objects.filter(
            person_profile=self.profile
        ).count()

        with patch(
            'users.serializers.CharacterReference.save',
            side_effect=IntegrityError('forced reference failure'),
        ):
            response = self.client.patch('/api/auth/me/', {
                'house_number': 'After',
                'character_references': [
                    {'name': 'Atomic Reference', 'contact_number': '09171111111'}
                ],
            }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.house_number, 'Before')
        self.assertEqual(
            CharacterReference.objects.filter(person_profile=self.profile).count(),
            old_reference_count,
        )


class PersonProfileModelTests(TestCase):
    def test_creating_person_creates_profile_via_signal(self):
        person = Person.objects.create(name='Signal Profile Employee')

        self.assertTrue(PersonProfile.objects.filter(person=person).exists())

    def test_person_save_does_not_create_duplicate_profile(self):
        person = Person.objects.create(name='Single Profile Employee')
        first_profile = person.profile_extension

        person.name = 'Renamed Profile Employee'
        person.save()

        person.refresh_from_db()
        self.assertEqual(person.profile_extension.pk, first_profile.pk)
        self.assertEqual(PersonProfile.objects.filter(person=person).count(), 1)

    def test_deleting_person_cascades_profile(self):
        person = Person.objects.create(name='Cascade Profile Employee')
        profile = person.profile_extension

        person.delete()

        self.assertFalse(PersonProfile.objects.filter(pk=profile.pk).exists())

    def test_character_reference_creates_for_profile(self):
        person = Person.objects.create(name='Reference Employee')

        reference = CharacterReference.objects.create(
            person_profile=person.profile_extension,
            name='Jane Reference',
            relationship='Former Supervisor',
            contact_number='09171234567',
        )

        self.assertEqual(
            person.profile_extension.character_references.get().pk,
            reference.pk,
        )

    def test_sixth_character_reference_exceeds_limit(self):
        person = Person.objects.create(name='Reference Limit Employee')
        profile = person.profile_extension
        for index in range(5):
            CharacterReference.objects.create(
                person_profile=profile,
                name=f'Reference {index + 1}',
                contact_number=f'0917000000{index}',
                display_order=index,
            )

        sixth = CharacterReference(
            person_profile=profile,
            name='Reference 6',
            contact_number='09170000006',
            display_order=5,
        )
        with self.assertRaises(ValidationError):
            sixth.clean()

    def test_archived_character_reference_does_not_count_toward_limit(self):
        person = Person.objects.create(name='Archived Reference Employee')
        profile = person.profile_extension
        for index in range(5):
            CharacterReference.objects.create(
                person_profile=profile,
                name=f'Reference {index + 1}',
                contact_number=f'0918000000{index}',
                is_archived=index == 0,
                display_order=index,
            )

        replacement = CharacterReference(
            person_profile=profile,
            name='Replacement Reference',
            contact_number='09180000005',
            display_order=5,
        )
        replacement.clean()

    def test_deleting_profile_cascades_character_references(self):
        person = Person.objects.create(name='Reference Cascade Employee')
        profile = person.profile_extension
        reference = CharacterReference.objects.create(
            person_profile=profile,
            name='Cascade Reference',
            contact_number='09191234567',
        )

        profile.delete()

        self.assertFalse(CharacterReference.objects.filter(pk=reference.pk).exists())

    def test_profile_accepts_nullable_contact_education_and_hr_fields(self):
        person = Person.objects.create(name='Nullable Profile Employee')
        profile = person.profile_extension

        profile.house_number = None
        profile.highest_education_attainment = None
        profile.prc_license_number = None
        profile.save()
        profile.refresh_from_db()

        self.assertIsNone(profile.house_number)
        self.assertIsNone(profile.highest_education_attainment)
        self.assertIsNone(profile.prc_license_number)

    def test_negative_year_graduated_is_rejected_by_clean(self):
        person = Person.objects.create(name='Negative Year Employee')
        profile = person.profile_extension
        profile.year_graduated = -1

        with self.assertRaises(ValidationError) as context:
            profile.clean()

        self.assertIn('year_graduated', context.exception.message_dict)

    def test_profile_locked_hr_and_property_fields_save_without_person_changes(self):
        person = Person.objects.create(
            name='HR Property Employee',
            status='ACTIVE',
        )
        profile = person.profile_extension
        profile.prc_license_number = 'PRC-12345'
        profile.hlurb_license_number = 'HLURB-67890'
        profile.partners_recruiter = 'Recruiter One'
        profile.team_director = 'Director One'
        profile.property_status = 'ACCREDITED'
        profile.save()

        person.refresh_from_db()
        profile.refresh_from_db()
        self.assertEqual(person.name, 'HR Property Employee')
        self.assertEqual(person.status, 'ACTIVE')
        self.assertEqual(profile.prc_license_number, 'PRC-12345')
        self.assertEqual(profile.hlurb_license_number, 'HLURB-67890')
        self.assertEqual(profile.property_status, 'ACCREDITED')

    def test_profile_contact_and_education_fields_save(self):
        person = Person.objects.create(name='Editable Profile Employee')
        profile = person.profile_extension
        profile.house_number = '123'
        profile.street = 'Phase 2 Street'
        profile.highest_education_attainment = 'College'
        profile.course = 'Computer Science'
        profile.education_school = 'Phase 2 University'
        profile.year_graduated = 2024
        profile.save()

        profile.refresh_from_db()
        self.assertEqual(profile.house_number, '123')
        self.assertEqual(profile.course, 'Computer Science')
        self.assertEqual(profile.year_graduated, 2024)


class PersonProfileMigrationTests(TransactionTestCase):
    migrate_from = [('users', '0005_remove_person_company_name_and_more')]
    migrate_to = [('users', '0006_personprofile_characterreference')]

    def setUp(self):
        super().setUp()
        self.executor = MigrationExecutor(connection)
        self.executor.migrate(self.migrate_from)
        post_save.disconnect(ensure_person_profile, sender=Person)

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        post_save.connect(ensure_person_profile, sender=Person)
        super().tearDown()

    def test_migration_backfills_profiles_for_existing_persons_without_changes(self):
        Person = apps.get_model('users', 'Person')
        person = Person.objects.create(
            name='Migrated Existing Employee',
            status='ACTIVE',
        )
        person_id = person.id
        original_name = person.name

        self.executor = MigrationExecutor(connection)
        self.executor.migrate(self.migrate_to)
        new_apps = self.executor.loader.project_state(self.migrate_to).apps
        NewPerson = new_apps.get_model('users', 'Person')
        NewPersonProfile = new_apps.get_model('users', 'PersonProfile')

        migrated_person = NewPerson.objects.get(pk=person_id)
        profile = NewPersonProfile.objects.get(person_id=person_id)
        self.assertEqual(migrated_person.name, original_name)
        self.assertEqual(migrated_person.status, 'ACTIVE')
        self.assertEqual(profile.person_id, person_id)

    def test_migration_reverse_removes_extension_data_without_changing_person(self):
        Person = apps.get_model('users', 'Person')
        person = Person.objects.create(
            name='Migration Reverse Employee',
            status='ACTIVE',
        )
        person_id = person.id

        self.executor = MigrationExecutor(connection)
        self.executor.migrate(self.migrate_to)
        new_apps = self.executor.loader.project_state(self.migrate_to).apps
        NewPerson = new_apps.get_model('users', 'Person')
        NewPersonProfile = new_apps.get_model('users', 'PersonProfile')

        self.assertTrue(NewPersonProfile.objects.filter(person_id=person_id).exists())

        self.executor = MigrationExecutor(connection)
        self.executor.migrate(self.migrate_from)
        historical_apps = self.executor.loader.project_state(self.migrate_from).apps
        HistoricalPerson = historical_apps.get_model('users', 'Person')
        migrated_person = HistoricalPerson.objects.get(pk=person_id)
        self.assertEqual(migrated_person.name, 'Migration Reverse Employee')
        self.assertEqual(migrated_person.status, 'ACTIVE')
