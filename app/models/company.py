from typing import List, Optional
from pydantic import BaseModel

class DepartmentBase(BaseModel):
    name: str
    code: Optional[str] = None

class DepartmentCreate(DepartmentBase):
    pass

class DepartmentUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None

class DepartmentResponse(DepartmentBase):
    id: str
    companyId: str
    headCount: int = 0

    class Config:
        from_attributes = True

class CompanyBase(BaseModel):
    name: str
    code: Optional[str] = None

class CompanyCreate(CompanyBase):
    pass

class CompanyUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None

class CompanyResponse(CompanyBase):
    id: str
    totalPersonnel: int = 0
    departments: List[DepartmentResponse] = []

    class Config:
        from_attributes = True

class OrgPersonNode(BaseModel):
    id: str
    name: str
    personType: str
    employmentMode: str
    biometricId: Optional[str] = None
    status: str

class OrgDepartmentNode(BaseModel):
    id: str
    name: str
    code: Optional[str] = None
    headCount: int = 0
    persons: List[OrgPersonNode] = []

class OrgCompanyNode(BaseModel):
    id: str
    name: str
    code: Optional[str] = None
    totalPersonnel: int = 0
    departments: List[OrgDepartmentNode] = []

