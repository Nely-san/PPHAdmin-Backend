import json
from rest_framework.test import APITestCase
from rest_framework import status
from users.models import User, Role
from audit.models import AuditLog
from audit.signals import record_audit_log

class AuditTests(APITestCase):
    def setUp(self):
        self.role, _ = Role.objects.get_or_create(code='AUDITOR', defaults={'name': 'Auditor'})
        self.user = User.objects.create_user(username='audit_inspector', password='password123', role=self.role)
        self.client.force_authenticate(user=self.user)

    def test_audit_log_creation_and_query(self):
        record_audit_log(
            table_name='payroll_records',
            record_id='12345',
            action='LOCK',
            old_data={'status': 'DRAFT'},
            new_data={'status': 'LOCKED'},
            changed_by='audit_inspector'
        )

        res = self.client.get('/api/audit-logs/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(res.data['total'], 1)
        self.assertEqual(res.data['logs'][0]['table_name'], 'payroll_records')
        self.assertEqual(res.data['logs'][0]['action'], 'LOCK')

    def test_automatic_user_create_and_update_signals(self):
        initial_log_count = AuditLog.objects.filter(table_name='users').count()

        # 1. Create a new user -> should generate CREATE audit log
        new_user = User.objects.create_user(
            username='johndoe',
            email='john@example.com',
            password='secretpassword123'
        )

        create_log = AuditLog.objects.filter(table_name='users', record_id=str(new_user.pk), action='CREATE').first()
        self.assertIsNotNone(create_log)
        new_data = json.loads(create_log.new_data)
        self.assertEqual(new_data['username'], 'johndoe')
        self.assertEqual(new_data['password'], '***REDACTED***')

        # 2. Update user -> should generate UPDATE audit log with diff
        current_count = AuditLog.objects.filter(table_name='users').count()
        new_user.email = 'john.doe.updated@example.com'
        new_user.save()

        update_log = AuditLog.objects.filter(table_name='users', record_id=str(new_user.pk), action='UPDATE').first()
        self.assertIsNotNone(update_log)
        old_data = json.loads(update_log.old_data)
        new_data = json.loads(update_log.new_data)
        self.assertEqual(old_data['email'], 'john@example.com')
        self.assertEqual(new_data['email'], 'john.doe.updated@example.com')

        # 3. No-op save -> should NOT generate another audit log
        count_before_noop = AuditLog.objects.filter(table_name='users').count()
        new_user.save()
        count_after_noop = AuditLog.objects.filter(table_name='users').count()
        self.assertEqual(count_before_noop, count_after_noop)

        # 4. Soft-archive user -> should generate ARCHIVE audit log
        new_user.is_archived = True
        new_user.save()
        archive_log = AuditLog.objects.filter(table_name='users', record_id=str(new_user.pk), action='ARCHIVE').first()
        self.assertIsNotNone(archive_log)

