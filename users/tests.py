from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from users.models import User, Role, PagePermission, Person


class AccountApprovalTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Seed Page Permissions
        self.perm_dash = PagePermission.objects.create(code='dashboard', name='Dashboard', module='SYSTEM')
        self.perm_emp = PagePermission.objects.create(code='employees', name='Employees', module='HR')
        self.perm_payroll = PagePermission.objects.create(code='payroll', name='Payroll', module='PAYROLL')
        self.perm_users = PagePermission.objects.create(code='user-management', name='User Management', module='SYSTEM')

        # Seed Roles
        self.sa_role = Role.objects.create(name='Super Admin', code='SUPER_ADMIN', is_system_role=True)
        self.hr_role = Role.objects.create(name='HR Manager', code='HR_MANAGER')
        self.hr_role.permissions.add(self.perm_dash, self.perm_emp)

        self.emp_role = Role.objects.create(name='Employee', code='EMPLOYEE')
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


