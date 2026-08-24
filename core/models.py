import uuid
from django.db import models
from django.utils import timezone

class BaseModel(models.Model):
    """
    Abstract base model providing UUID primary keys, audit timestamps,
    and soft-delete archiving lifecycle fields (Zero Hard-Delete Policy).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_archived = models.BooleanField(default=False, db_index=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    archived_by = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        abstract = True

    def archive(self, user_identifier: str = None):
        """Soft-deletes the record preserving database integrity."""
        self.is_archived = True
        self.archived_at = timezone.now()
        self.archived_by = user_identifier
        self.save(update_fields=['is_archived', 'archived_at', 'archived_by', 'updated_at'])

    def restore(self):
        """Restores a soft-archived record back to active state."""
        self.is_archived = False
        self.archived_at = None
        self.archived_by = None
        self.save(update_fields=['is_archived', 'archived_at', 'archived_by', 'updated_at'])
