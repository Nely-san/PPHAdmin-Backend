import json
from decimal import Decimal
from datetime import datetime, date
from typing import Any
from prisma import Prisma

class PrismaEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if hasattr(obj, "__dict__"):
            # Clean up private attributes and sensitive keys
            clean_dict = {}
            for k, v in obj.__dict__.items():
                if not k.startswith("_") and k not in ["passwordHash", "password", "password_hash"]:
                    clean_dict[k] = v
            return clean_dict
        return super().default(obj)

def serialize_data(data: Any) -> str | None:
    if data is None:
        return None
    try:
        # Convert to dictionary if possible
        if hasattr(data, "model_dump"):
            d = data.model_dump()
        elif hasattr(data, "dict"):
            d = data.dict()
        else:
            d = data

        # Remove sensitive fields
        if isinstance(d, dict):
            d = {k: v for k, v in d.items() if k not in ["passwordHash", "password", "password_hash"]}
            
        return json.dumps(d, cls=PrismaEncoder)
    except Exception:
        try:
            return json.dumps(data, cls=PrismaEncoder)
        except Exception:
            return str(data)

async def log_audit_action(
    table_name: str,
    record_id: str,
    action: str, # "CREATE", "UPDATE", "DELETE", "ARCHIVE", "RESTORE", "IMPORT", "RESET", "GENERATE"
    old_data: Any | None,
    new_data: Any | None,
    changed_by: str,
    db: Prisma
) -> None:
    """
    Log structural changes to the audit_logs table.
    """
    old_json = serialize_data(old_data)
    new_json = serialize_data(new_data)
    
    await db.auditlog.create(data={
        "tableName": table_name,
        "recordId": record_id,
        "action": action,
        "oldData": old_json,
        "newData": new_json,
        "changedBy": changed_by
    })
