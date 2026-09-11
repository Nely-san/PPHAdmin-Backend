import uuid
from django.db import models

class AuditLog(models.Model):
    """
    Automated Security and Mutation Audit Trail capturing table, record, action, JSON diff, and actor.
    """
    ACTION_CHOICES = [
        ('CREATE', 'Created New Record'),
        ('UPDATE', 'Updated Existing Record'),
        ('ARCHIVE', 'Soft-Archived Record'),
        ('RESTORE', 'Restored Archived Record'),
        ('IMPORT', 'Imported Biometric Batch'),
        ('RESET', 'Password / Key Reset'),
        ('GENERATE', 'Generated Payroll Draft'),
        ('APPROVE', 'Approved Transaction'),
        ('REJECT', 'Rejected Transaction'),
        ('LOCK', 'Locked Cutoff Records'),
        ('PURGE', 'Permanent Purge'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    table_name = models.CharField(max_length=100, db_index=True)
    record_id = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    action = models.CharField(max_length=50, db_index=True)
    old_data = models.TextField(null=True, blank=True)
    new_data = models.TextField(null=True, blank=True)
    changed_by = models.CharField(max_length=150, default='SYSTEM', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'audit_logs'
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.action}] {self.table_name} ({self.record_id}) by {self.changed_by} at {self.created_at}"
