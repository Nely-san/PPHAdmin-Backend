from pydantic import BaseModel, EmailStr
from typing import Optional, Any

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class LoginRequest(BaseModel):
    username: str
    password: str

class PersonDetail(BaseModel):
    id: str
    biometricId: Optional[str] = None
    name: str
    personType: str
    employmentMode: str
    rateType: str
    baseRate: float
    dateStarted: Optional[str] = None
    status: str
    companyName: Optional[str] = None
    companyCode: Optional[str] = None
    departmentName: Optional[str] = None
    departmentCode: Optional[str] = None
    schoolName: Optional[str] = None
    coordinatorContact: Optional[str] = None
    requiredOjtHours: Optional[float] = None
    renderedOjtHours: Optional[float] = None

class UserProfile(BaseModel):
    id: str
    username: str
    email: Optional[str] = None
    role: str
    createdAt: Optional[str] = None
    person: Optional[PersonDetail] = None
