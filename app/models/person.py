from pydantic import BaseModel, Field
from typing import Optional

class PersonCreateRequest(BaseModel):
    name: str
    userId: Optional[str] = None
    biometricId: Optional[str] = None
    personType: str = "EMPLOYEE" # "EMPLOYEE" or "OJT"
    employmentMode: str = "FULL_TIME" # "FULL_TIME", "PART_TIME", "CONTRACT", "INTERN"
    rateType: str = "DAILY" # "DAILY", "MONTHLY", "HOURLY"
    baseRate: float = 0.0
    dateStarted: Optional[str] = None
    status: str = "ACTIVE" # "ACTIVE", "ARCHIVED", "ON_LEAVE", "COMPLETED"
    companyId: Optional[str] = None
    departmentId: Optional[str] = None
    
    # OJT Specific
    schoolName: Optional[str] = None
    coordinatorContact: Optional[str] = None
    requiredOjtHours: Optional[float] = None
    renderedOjtHours: Optional[float] = None

class PersonUpdateRequest(BaseModel):
    name: Optional[str] = None
    userId: Optional[str] = None
    biometricId: Optional[str] = None
    personType: Optional[str] = None
    employmentMode: Optional[str] = None
    rateType: Optional[str] = None
    baseRate: Optional[float] = None
    dateStarted: Optional[str] = None
    status: Optional[str] = None
    companyId: Optional[str] = None
    departmentId: Optional[str] = None
    
    schoolName: Optional[str] = None
    coordinatorContact: Optional[str] = None
    requiredOjtHours: Optional[float] = None
    renderedOjtHours: Optional[float] = None

class PersonDetailResponse(BaseModel):
    id: str
    userId: Optional[str] = None
    biometricId: Optional[str] = None
    name: str
    personType: str
    employmentMode: str
    rateType: str
    baseRate: float
    dateStarted: Optional[str] = None
    status: str
    companyId: Optional[str] = None
    companyName: Optional[str] = None
    companyCode: Optional[str] = None
    departmentId: Optional[str] = None
    departmentName: Optional[str] = None
    departmentCode: Optional[str] = None
    schoolName: Optional[str] = None
    coordinatorContact: Optional[str] = None
    requiredOjtHours: Optional[float] = None
    renderedOjtHours: Optional[float] = None

class QuickOjtHoursRequest(BaseModel):
    hoursToAdd: float

