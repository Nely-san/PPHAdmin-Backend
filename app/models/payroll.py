from pydantic import BaseModel
from datetime import date
from decimal import Decimal
from enum import Enum

class PayrollStatus(str, Enum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    PAID = "PAID"

class PayrollItemType(str, Enum):
    EARNING = "EARNING"
    DEDUCTION = "DEDUCTION"
    ADVANCE = "ADVANCE"
    REIMBURSEMENT = "REIMBURSEMENT"

class PayrollItemBase(BaseModel):
    item_type: PayrollItemType
    description: str
    amount: Decimal

class PayrollItemCreate(PayrollItemBase):
    pass

class PayrollItemResponse(PayrollItemBase):
    id: str
    payroll_record_id: str

    class Config:
        from_attributes = True

class PayrollRecordResponse(BaseModel):
    id: str
    person_id: str
    cutoff_start: date
    cutoff_end: date
    gross_pay: Decimal
    total_deductions: Decimal
    net_pay: Decimal
    status: PayrollStatus
    items: list[PayrollItemResponse] = []

    class Config:
        from_attributes = True

class PayrollGenerateRequest(BaseModel):
    cutoff_start: date
    cutoff_end: date
    company_id: str | None = None
