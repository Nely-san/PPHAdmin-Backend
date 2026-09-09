import json
from decimal import Decimal
from datetime import date, datetime, time
import uuid
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.core.serializers.json import DjangoJSONEncoder
from audit.middleware import get_current_username

SENSITIVE_FIELDS = {'password', 'token', 'secret', 'access_token', 'refresh_token'}

EXCLUDED_MODELS = {'AuditLog', 'Session', 'LogEntry', 'ContentType', 'Permission'}

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
            if isinstance(val, (datetime, date, time)):
                data[field.name] = val.isoformat()
            elif isinstance(val, Decimal):
                data[field.name] = float(val)
            elif isinstance(val, uuid.UUID):
                data[field.name] = str(val)
            else:
                try:
                    json.dumps(val, cls=AuditJSONEncoder)
                    data[field.name] = val
                except (TypeError, ValueError):
                    data[field.name] = str(val) if val is not None else None
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
    except Exception as e:
        pass
