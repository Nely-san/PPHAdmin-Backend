from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional, List
from datetime import date
from enum import Enum

router = APIRouter()

class AdjustmentType(str, Enum):
    BONUS = "Bonus"
    DEDUCTION = "Deduction"
    ALLOWANCE = "Allowance"

class AdjustmentStatus(str, Enum):
    PENDING = "Pending"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    RECURRING = "Recurring"

class AdjustmentBase(BaseModel):
    person_id: str
    employee_name: str
    department: str
    type: AdjustmentType
    adjustment_subtype: str
    amount: float
    description: str
    effective_date: date
    status: AdjustmentStatus = AdjustmentStatus.PENDING
    is_recurring: bool = False
    frequency: str = "One-Time"

class AdjustmentCreate(AdjustmentBase):
    pass

class AdjustmentResponse(AdjustmentBase):
    id: str
    created_at: date

# In-memory store for fallback / initial API endpoint testing
MOCK_ADJUSTMENTS_DB: List[dict] = [
    {
        "id": "adj-1",
        "person_id": "1",
        "employee_name": "Alexander Wright",
        "department": "IT & Engineering",
        "type": "Bonus",
        "adjustment_subtype": "Mid-Year Performance Bonus",
        "amount": 5000.00,
        "description": "Mid-Year Performance Bonus",
        "effective_date": "2026-08-15",
        "status": "Approved",
        "is_recurring": False,
        "frequency": "One-Time",
        "created_at": "2026-08-01"
    },
    {
        "id": "adj-2",
        "person_id": "2",
        "employee_name": "Maria Santos",
        "department": "Human Resources",
        "type": "Bonus",
        "adjustment_subtype": "Perfect Attendance Bonus",
        "amount": 1500.00,
        "description": "Perfect Attendance Bonus for July",
        "effective_date": "2026-08-30",
        "status": "Pending",
        "is_recurring": False,
        "frequency": "One-Time",
        "created_at": "2026-08-02"
    }
]

@router.get("", response_model=List[dict])
async def list_adjustments(category: Optional[str] = None):
    """
    List payroll adjustments (bonuses, deductions, recurring allowances).
    """
    if category:
        return [a for a in MOCK_ADJUSTMENTS_DB if a["type"].lower() == category.lower()]
    return MOCK_ADJUSTMENTS_DB

@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_adjustment(payload: AdjustmentCreate):
    """
    Create a new payroll adjustment.
    """
    new_item = {
        "id": f"adj-{len(MOCK_ADJUSTMENTS_DB) + 1}",
        **payload.dict(),
        "created_at": date.today().isoformat()
    }
    MOCK_ADJUSTMENTS_DB.insert(0, new_item)
    return new_item

@router.patch("/{adjustment_id}/status", response_model=dict)
async def update_adjustment_status(adjustment_id: str, status: AdjustmentStatus):
    """
    Update status of an adjustment (Approve or Reject).
    """
    for item in MOCK_ADJUSTMENTS_DB:
        if item["id"] == adjustment_id:
            item["status"] = status.value
            return item
    raise HTTPException(status_code=404, detail="Adjustment record not found")

@router.delete("/{adjustment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_adjustment(adjustment_id: str):
    """
    Delete a payroll adjustment.
    """
    global MOCK_ADJUSTMENTS_DB
    MOCK_ADJUSTMENTS_DB = [a for a in MOCK_ADJUSTMENTS_DB if a["id"] != adjustment_id]
    return None
