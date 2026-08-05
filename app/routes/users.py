from typing import List, Optional
from datetime import datetime
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status
from prisma import Prisma
from pydantic import BaseModel
from app.core.database import get_db
from app.routes.auth import get_current_user
from app.models.auth import UserProfile, PersonDetail
from app.core.security import get_password_hash

router = APIRouter()

class UserCreateRequest(BaseModel):
    username: str
    password: str
    email: Optional[str] = None
    role: str
    schoolName: Optional[str] = None

class UserUpdateRequest(BaseModel):
    email: Optional[str] = None
    role: Optional[str] = None
    isArchived: Optional[bool] = None
    schoolName: Optional[str] = None

class UserResponse(BaseModel):
    id: str
    username: str
    email: Optional[str]
    role: str
    isArchived: bool
    createdAt: str
    updatedAt: str
    person: Optional[PersonDetail] = None

def format_user_response(user) -> UserResponse:
    person_detail = None
    if hasattr(user, 'person') and user.person:
        person_detail = PersonDetail(
            id=user.person.id,
            biometricId=user.person.biometricId,
            name=user.person.name,
            personType=user.person.personType,
            employmentMode=user.person.employmentMode,
            rateType=user.person.rateType,
            baseRate=float(user.person.baseRate) if user.person.baseRate is not None else 0.0,
            dateStarted=user.person.dateStarted.isoformat() if user.person.dateStarted else None,
            status=user.person.status,
            companyName=user.person.company.name if hasattr(user.person, 'company') and user.person.company else None,
            companyCode=user.person.company.code if hasattr(user.person, 'company') and user.person.company else None,
            departmentName=user.person.department.name if hasattr(user.person, 'department') and user.person.department else None,
            departmentCode=user.person.department.code if hasattr(user.person, 'department') and user.person.department else None,
            schoolName=user.person.schoolName,
            coordinatorContact=user.person.coordinatorContact,
            requiredOjtHours=float(user.person.requiredOjtHours) if user.person.requiredOjtHours is not None else 0.0,
            renderedOjtHours=float(user.person.renderedOjtHours) if user.person.renderedOjtHours is not None else 0.0,
        )

    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        isArchived=user.isArchived,
        createdAt=user.createdAt.isoformat() if user.createdAt else "",
        updatedAt=user.updatedAt.isoformat() if user.updatedAt else "",
        person=person_detail
    )

@router.get("/", response_model=List[UserResponse])
async def list_users(
    include_archived: bool = False,
    current_user: UserProfile = Depends(get_current_user),
    db: Prisma = Depends(get_db)
):
    if current_user.role not in ["SUPER_ADMIN", "ADMIN"]:
        raise HTTPException(status_code=403, detail="Not authorized to view users")

    where_clause = {}
    if not include_archived:
        where_clause["isArchived"] = False

    users = await db.user.find_many(
        where=where_clause,
        include={
            "person": {
                "include": {
                    "company": True,
                    "department": True
                }
            }
        }
    )
    return [format_user_response(user) for user in users]

@router.post("/", response_model=UserResponse)
async def create_user(
    data: UserCreateRequest,
    current_user: UserProfile = Depends(get_current_user),
    db: Prisma = Depends(get_db)
):
    if current_user.role not in ["SUPER_ADMIN", "ADMIN"]:
        raise HTTPException(status_code=403, detail="Not authorized to create users")

    if data.role == "OJT" and (not data.schoolName or not data.schoolName.strip()):
        raise HTTPException(status_code=400, detail="School / University is required when role is OJT")

    if data.role == "SUPER_ADMIN":
        existing_super_admin = await db.user.find_first(where={"role": "SUPER_ADMIN", "isArchived": False})
        if existing_super_admin:
            raise HTTPException(status_code=400, detail="System policy error: There can only be one active Super Admin in the system.")

    existing_user = await db.user.find_unique(where={"username": data.username})
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")

    hashed_password = get_password_hash(data.password)
    new_user = await db.user.create(
        data={
            "username": data.username,
            "email": data.email,
            "passwordHash": hashed_password,
            "role": data.role,
            "isArchived": False
        }
    )

    if data.role == "OJT" or data.schoolName:
        await db.person.create(
            data={
                "userId": new_user.id,
                "name": new_user.username,
                "personType": "OJT",
                "employmentMode": "INTERN",
                "rateType": "HOURLY",
                "baseRate": Decimal("0.00"),
                "dateStarted": datetime.now(),
                "status": "ACTIVE",
                "schoolName": data.schoolName.strip() if data.schoolName else None,
                "requiredOjtHours": Decimal("500.00"),
                "renderedOjtHours": Decimal("0.00"),
            }
        )

    reloaded_user = await db.user.find_unique(
        where={"id": new_user.id},
        include={"person": {"include": {"company": True, "department": True}}}
    )
    return format_user_response(reloaded_user)

@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    data: UserUpdateRequest,
    current_user: UserProfile = Depends(get_current_user),
    db: Prisma = Depends(get_db)
):
    if current_user.role not in ["SUPER_ADMIN", "ADMIN"]:
        raise HTTPException(status_code=403, detail="Not authorized to update users")

    if data.role == "OJT" and data.schoolName is not None and not data.schoolName.strip():
        raise HTTPException(status_code=400, detail="School / University is required when role is OJT")

    if data.role == "SUPER_ADMIN":
        existing_super_admin = await db.user.find_first(where={"role": "SUPER_ADMIN", "isArchived": False, "id": {"not": user_id}})
        if existing_super_admin:
            raise HTTPException(status_code=400, detail="System policy error: There can only be one active Super Admin in the system.")

    user = await db.user.find_unique(where={"id": user_id}, include={"person": True})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = {}
    if data.email is not None:
        update_data["email"] = data.email
    if data.role is not None:
        update_data["role"] = data.role
    if data.isArchived is not None:
        update_data["isArchived"] = data.isArchived

    updated_user = await db.user.update(
        where={"id": user_id},
        data=update_data
    )

    if data.schoolName or data.role == "OJT":
        existing_person = await db.person.find_unique(where={"userId": user_id})
        if existing_person:
            person_update = {}
            if data.schoolName is not None:
                person_update["schoolName"] = data.schoolName.strip()
            if data.role == "OJT":
                person_update["personType"] = "OJT"
            if person_update:
                await db.person.update(where={"id": existing_person.id}, data=person_update)
        else:
            await db.person.create(
                data={
                    "userId": user_id,
                    "name": updated_user.username,
                    "personType": "OJT",
                    "employmentMode": "INTERN",
                    "rateType": "HOURLY",
                    "baseRate": Decimal("0.00"),
                    "dateStarted": datetime.now(),
                    "status": "ACTIVE",
                    "schoolName": data.schoolName.strip() if data.schoolName else None,
                    "requiredOjtHours": Decimal("500.00"),
                    "renderedOjtHours": Decimal("0.00"),
                }
            )

    reloaded_user = await db.user.find_unique(
        where={"id": user_id},
        include={"person": {"include": {"company": True, "department": True}}}
    )
    return format_user_response(reloaded_user)

@router.delete("/{user_id}", response_model=UserResponse)
async def archive_user(
    user_id: str,
    current_user: UserProfile = Depends(get_current_user),
    db: Prisma = Depends(get_db)
):
    if current_user.role not in ["SUPER_ADMIN", "ADMIN"]:
        raise HTTPException(status_code=403, detail="Not authorized to archive users")

    user = await db.user.find_unique(where={"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.role == "SUPER_ADMIN":
        active_super_admins = await db.user.count(where={"role": "SUPER_ADMIN", "isArchived": False})
        if active_super_admins <= 1:
            raise HTTPException(status_code=400, detail="System policy error: Cannot archive the sole active Super Admin in the system.")

    updated_user = await db.user.update(
        where={"id": user_id},
        data={"isArchived": True}
    )
    reloaded_user = await db.user.find_unique(
        where={"id": user_id},
        include={"person": {"include": {"company": True, "department": True}}}
    )
    return format_user_response(reloaded_user)

