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


from unittest.mock import patch

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

    @patch('google.oauth2.id_token.verify_oauth2_token')
    def test_google_signup_provisions_pending_user(self, mock_verify):
        mock_verify.return_value = {
            'email': 'new_google_user@example.com',
            'given_name': 'Google',
            'family_name': 'User',
            'name': 'Google User',
            'email_verified': True
        }

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

    @patch('google.oauth2.id_token.verify_oauth2_token')
    def test_google_login_approved_user(self, mock_verify):
        mock_verify.return_value = {
            'email': 'existing_user@example.com',
            'name': 'Existing Verified User',
            'email_verified': True
        }

        user = User.objects.create(
            username='existing_google',
            email='existing_user@example.com',
            role=self.emp_role,
            approval_status='APPROVED',
            is_active=True
        )

        response = self.client.post('/api/auth/google-login/', {
            'id_token': 'valid_simulated_jwt_token'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertFalse(response.data.get('is_new_user'))




