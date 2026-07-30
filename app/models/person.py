from pydantic import BaseModel, Field
from datetime import date
from decimal import Decimal
from enum import Enum

class PersonType(str, Enum):
    EMPLOYEE = "EMPLOYEE"
    OJT = "OJT"

class EmploymentMode(str, Enum):
    FULL_TIME = "FULL_TIME"
    PART_TIME = "PART_TIME"
    CONTRACT = "CONTRACT"

class RateType(str, Enum):
    DAILY = "DAILY"
    MONTHLY = "MONTHLY"

class PersonStatus(str, Enum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"

class PersonBase(BaseModel):
    name: str
    company_id: str
    biometric_device_id: str | None = None
    person_type: PersonType
    employment_mode: EmploymentMode
    rate_type: RateType
    base_rate: Decimal = Field(default=Decimal("0.00"), max_digits=10, decimal_places=2)
    date_started: date
    date_ended: date | None = None
    
    # OJT Specific Fields
    school_name: str | None = None
    coordinator_contact: str | None = None
    required_ojt_hours: int | None = None

class PersonCreate(PersonBase):
    pass

class PersonUpdate(BaseModel):
    name: str | None = None
    company_id: str | None = None
    biometric_device_id: str | None = None
    person_type: PersonType | None = None
    employment_mode: EmploymentMode | None = None
    rate_type: RateType | None = None
    base_rate: Decimal | None = None
    date_started: date | None = None
    date_ended: date | None = None
    status: PersonStatus | None = None
    
    school_name: str | None = None
    coordinator_contact: str | None = None
    required_ojt_hours: int | None = None

class PersonResponse(PersonBase):
    id: str
    status: PersonStatus

    class Config:
        from_attributes = True
