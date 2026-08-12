from fastapi import APIRouter, Depends, HTTPException, status
from prisma import Prisma
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from app.core.database import get_db
from app.routes.auth import get_current_user
from app.models.auth import UserProfile
from app.services.audit_logger import log_audit_action

router = APIRouter()

class SystemParameterResponse(BaseModel):
    id: str
    key: str
    value: str
    description: Optional[str] = None
    category: str
    createdAt: datetime
    updatedAt: datetime

class ParameterUpdateItem(BaseModel):
    key: str
    value: str

class BulkParameterUpdateRequest(BaseModel):
    updates: List[ParameterUpdateItem]

DEFAULT_PARAMETERS = [
    # GENERAL
    {"key": "system_name", "value": "PPHAdmin", "description": "System title shown in navigation and page headers", "category": "GENERAL"},
    {"key": "company_name", "value": "Prime Power House", "description": "Legal company name used on payslips and official documents", "category": "GENERAL"},
    {"key": "support_email", "value": "support@primepowerhouse.com", "description": "Contact email address for administrative or IT support", "category": "GENERAL"},
    {"key": "currency", "value": "PHP", "description": "Primary currency code for payroll calculations", "category": "GENERAL"},
    
    # ATTENDANCE
    {"key": "attendance_grace_period", "value": "15", "description": "Allowed late offset in minutes for clock-ins before penalty applies", "category": "ATTENDANCE"},
    {"key": "attendance_overtime_threshold", "value": "60", "description": "Minimum rendered work in minutes beyond shift to count as Overtime", "category": "ATTENDANCE"},
    {"key": "attendance_undertime_threshold", "value": "30", "description": "Threshold in minutes for early departures to count as Under-time", "category": "ATTENDANCE"},
    {"key": "standard_daily_hours", "value": "8.0", "description": "Standard daily work duration in hours excluding breaks", "category": "ATTENDANCE"},
    {"key": "auto_break_deduction", "value": "60", "description": "Automatic lunch break deduction in minutes for shifts > 5 hours", "category": "ATTENDANCE"},
    
    # SECURITY
    {"key": "security_min_password_length", "value": "8", "description": "Minimum required characters for user passwords", "category": "SECURITY"},
    {"key": "security_max_login_attempts", "value": "5", "description": "Number of failed login attempts allowed before locking account temporarily", "category": "SECURITY"},
    {"key": "security_session_timeout", "value": "30", "description": "Inactive session timeout duration in minutes", "category": "SECURITY"},
]

def validate_parameter_value(key: str, value: str):
    val_stripped = value.strip()
    if not val_stripped:
        raise ValueError("Value cannot be empty.")
        
    # GENERAL
    if key == "support_email":
        if "@" not in val_stripped or "." not in val_stripped:
            raise ValueError("Must be a valid email address.")
            
    # ATTENDANCE
    elif key in ["attendance_grace_period", "attendance_overtime_threshold", "attendance_undertime_threshold", "auto_break_deduction"]:
        try:
            val_int = int(val_stripped)
            if val_int < 0:
                raise ValueError("Must be a non-negative integer.")
        except ValueError:
            raise ValueError("Must be a valid integer.")
            
    elif key == "standard_daily_hours":
        try:
            val_float = float(val_stripped)
            if val_float <= 0.0 or val_float > 24.0:
                raise ValueError("Must be a float between 0.0 and 24.0.")
        except ValueError:
            raise ValueError("Must be a valid number.")
            
    # SECURITY
    elif key == "security_min_password_length":
        try:
            val_int = int(val_stripped)
            if val_int < 4 or val_int > 64:
                raise ValueError("Password length must be between 4 and 64.")
        except ValueError:
            raise ValueError("Must be a valid integer.")
            
    elif key == "security_max_login_attempts":
        try:
            val_int = int(val_stripped)
            if val_int < 1 or val_int > 20:
                raise ValueError("Login attempts must be between 1 and 20.")
        except ValueError:
            raise ValueError("Must be a valid integer.")
            
    elif key == "security_session_timeout":
        try:
            val_int = int(val_stripped)
            if val_int < 1 or val_int > 1440:
                raise ValueError("Session timeout must be between 1 and 1440 minutes.")
        except ValueError:
            raise ValueError("Must be a valid integer.")

@router.get("/", response_model=List[SystemParameterResponse])
async def get_system_parameters(
    db: Prisma = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user)
):
    if current_user.role != "SUPER_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Only Super Admins can manage system parameters."
        )

    # Fetch existing
    existing = await db.systemparameter.find_many()
    existing_keys = {p.key for p in existing}
    
    # Clean up obsolete parameters from database (e.g. payroll)
    default_keys = {p["key"] for p in DEFAULT_PARAMETERS}
    obsolete_keys = existing_keys - default_keys
    if obsolete_keys:
        await db.systemparameter.delete_many(
            where={
                "key": {
                    "in": list(obsolete_keys)
                }
            }
        )
        existing = [p for p in existing if p.key not in obsolete_keys]
        existing_keys = {p.key for p in existing}

    # Check if any defaults are missing
    missing_defaults = [p for p in DEFAULT_PARAMETERS if p["key"] not in existing_keys]
    if missing_defaults:
        for item in missing_defaults:
            await db.systemparameter.create(data=item)
        # Fetch again to get the full list
        existing = await db.systemparameter.find_many()
        
    return existing

@router.put("/", response_model=List[SystemParameterResponse])
async def update_system_parameters(
    data: BulkParameterUpdateRequest,
    db: Prisma = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user)
):
    if current_user.role != "SUPER_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Only Super Admins can manage system parameters."
        )

    # Validate all items first to ensure atomicity
    for item in data.updates:
        # Check if parameter exists
        existing = await db.systemparameter.find_unique(where={"key": item.key})
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"System parameter '{item.key}' not found."
            )
            
        try:
            validate_parameter_value(item.key, item.value)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid value for '{item.key}': {str(e)}"
            )

    # Perform updates and audit logs
    for item in data.updates:
        existing = await db.systemparameter.find_unique(where={"key": item.key})
        if existing and existing.value != item.value:
            updated = await db.systemparameter.update(
                where={"key": item.key},
                data={"value": item.value}
            )
            
            # Log audit trail
            await log_audit_action(
                table_name="system_parameters",
                record_id=existing.id,
                action="UPDATE",
                old_data={"key": existing.key, "value": existing.value, "category": existing.category},
                new_data={"key": updated.key, "value": updated.value, "category": updated.category},
                changed_by=current_user.username,
                db=db
            )
            
    # Return re-fetched list
    all_params = await db.systemparameter.find_many()
    return all_params
