from pydantic import BaseModel
from datetime import date, time
from decimal import Decimal

class AttendanceLogBase(BaseModel):
    person_id: str
    log_date: date
    time_in: time | None = None
    time_out: time | None = None
    computed_hours: Decimal = Decimal("0.00")
    is_late: bool = False

class AttendanceLogCreate(AttendanceLogBase):
    batch_id: str

class AttendanceLogUpdate(BaseModel):
    time_in: time | None = None
    time_out: time | None = None
    computed_hours: Decimal | None = None
    is_late: bool | None = None

class AttendanceLogResponse(AttendanceLogBase):
    id: str
    batch_id: str | None = None
    payroll_id: str | None = None
    is_locked: bool

    class Config:
        from_attributes = True

class AttendanceImportResponse(BaseModel):
    batch_id: str
    file_name: str
    records_imported: int
    anomalies_detected: int
    total_processed: int = 0
    logs: list[dict] = []

