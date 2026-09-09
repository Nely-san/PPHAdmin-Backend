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
