import json
from decimal import Decimal
from datetime import date, datetime, time
import uuid
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.core.serializers.json import DjangoJSONEncoder
from audit.middleware import get_current_username

SENSITIVE_FIELDS = {'password', 'token', 'secret', 'access_token', 'refresh_token'}

IGNORED_DIFF_FIELDS = {'updated_at', 'created_at'}

EXCLUDED_MODELS = {
    'AuditLog', 'Session', 'LogEntry', 'ContentType', 'Permission',
    'Notification', 'OutstandingToken', 'BlacklistedToken'
}

AUDITED_APPS = {'users', 'settings', 'payroll', 'leaves_ob'}

class AuditJSONEncoder(DjangoJSONEncoder):
    def default(self, o):
        if isinstance(o, (datetime, date, time)):
            return o.isoformat()
        if isinstance(o, Decimal):
            return float(o)
        if isinstance(o, uuid.UUID):
            return str(o)
        return super().default(o)

def model_to_dict_safe(instance):
    data = {}
    for field in instance._meta.fields:
        if field.name in SENSITIVE_FIELDS:
            data[field.name] = '***REDACTED***'
        else:
            val = getattr(instance, field.name, None)
            if hasattr(val, 'pk'):
                val = str(val.pk)
            elif isinstance(val, (datetime, date, time)):
                val = val.isoformat()
            elif isinstance(val, Decimal):
                val = float(val)
            elif isinstance(val, uuid.UUID):
                val = str(val)
            else:
                try:
                    json.dumps(val, cls=AuditJSONEncoder)
                except (TypeError, ValueError):
                    val = str(val) if val is not None else None
            data[field.name] = val
    return data

def record_audit_log(table_name, record_id, action, old_data=None, new_data=None, changed_by=None):
    from audit.models import AuditLog
    if not changed_by:
        changed_by = get_current_username()

    old_str = json.dumps(old_data, cls=AuditJSONEncoder) if isinstance(old_data, dict) else (str(old_data) if old_data else None)
    new_str = json.dumps(new_data, cls=AuditJSONEncoder) if isinstance(new_data, dict) else (str(new_data) if new_data else None)

    try:
        AuditLog.objects.create(
            table_name=table_name,
            record_id=str(record_id) if record_id is not None else '',
            action=action,
            old_data=old_str,
            new_data=new_str,
            changed_by=changed_by or 'SYSTEM'
        )
    except Exception:
        pass


@receiver(pre_save)
def audit_pre_save(sender, instance, **kwargs):
    """
    Captures snapshot of model state prior to update for diff computation.
    """
    if sender.__name__ in EXCLUDED_MODELS or sender._meta.app_label not in AUDITED_APPS:
        return

    try:
        if instance.pk:
            existing = sender.objects.filter(pk=instance.pk).first()
            if existing:
                instance._old_audit_state = model_to_dict_safe(existing)
            else:
                instance._old_audit_state = None
        else:
            instance._old_audit_state = None
    except Exception:
        instance._old_audit_state = None


@receiver(post_save)
def audit_post_save(sender, instance, created, **kwargs):
    """
    Automatically creates CREATE, UPDATE, ARCHIVE, or RESTORE audit log entries.
    Terminates early if no actual fields changed (no-op update).
    """
    if sender.__name__ in EXCLUDED_MODELS or sender._meta.app_label not in AUDITED_APPS:
        return

    try:
        table_name = instance._meta.db_table
        record_id = str(instance.pk)

        if created:
            new_data = model_to_dict_safe(instance)
            record_audit_log(table_name=table_name, record_id=record_id, action='CREATE', old_data=None, new_data=new_data)
            return

        old_data = getattr(instance, '_old_audit_state', None)
        new_data = model_to_dict_safe(instance)

        if old_data is not None:
            # Check if any field actually changed
            has_changes = False
            for k, v in new_data.items():
                if k in IGNORED_DIFF_FIELDS:
                    continue
                if k not in old_data or old_data[k] != v:
                    has_changes = True
                    break
            
            if not has_changes:
                return  # Skip no-op writes

            old_archived = old_data.get('is_archived')
            new_archived = new_data.get('is_archived')
            if old_archived is False and new_archived is True:
                action = 'ARCHIVE'
            elif old_archived is True and new_archived is False:
                action = 'RESTORE'
            else:
                action = 'UPDATE'
        else:
            action = 'UPDATE'

        record_audit_log(table_name=table_name, record_id=record_id, action=action, old_data=old_data, new_data=new_data)
    except Exception:
        pass


@receiver(post_delete)
def audit_post_delete(sender, instance, **kwargs):
    """
    Logs physical delete operations on audited models.
    """
    if sender.__name__ in EXCLUDED_MODELS or sender._meta.app_label not in AUDITED_APPS:
        return

    try:
        table_name = instance._meta.db_table
        record_id = str(instance.pk)
        old_data = model_to_dict_safe(instance)
        record_audit_log(table_name=table_name, record_id=record_id, action='DELETE', old_data=old_data, new_data=None)
    except Exception:
        pass
