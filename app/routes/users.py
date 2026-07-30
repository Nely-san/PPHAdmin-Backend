from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from prisma import Prisma
from pydantic import BaseModel
from app.core.database import get_db
from app.routes.auth import get_current_user
from app.models.auth import UserProfile
from app.core.security import get_password_hash

router = APIRouter()

class UserCreateRequest(BaseModel):
    username: str
    password: str
    email: Optional[str] = None
    role: str

class UserUpdateRequest(BaseModel):
    email: Optional[str] = None
    role: Optional[str] = None
    isArchived: Optional[bool] = None

class UserResponse(BaseModel):
    id: str
    username: str
    email: Optional[str]
    role: str
    isArchived: bool
    createdAt: str
    updatedAt: str

def format_user_response(user) -> UserResponse:
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        isArchived=user.isArchived,
        createdAt=user.createdAt.isoformat() if user.createdAt else "",
        updatedAt=user.updatedAt.isoformat() if user.updatedAt else ""
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

    users = await db.user.find_many(where=where_clause)
    return [format_user_response(user) for user in users]

@router.post("/", response_model=UserResponse)
async def create_user(
    data: UserCreateRequest,
    current_user: UserProfile = Depends(get_current_user),
    db: Prisma = Depends(get_db)
):
    if current_user.role not in ["SUPER_ADMIN", "ADMIN"]:
        raise HTTPException(status_code=403, detail="Not authorized to create users")

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
    return format_user_response(new_user)

@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    data: UserUpdateRequest,
    current_user: UserProfile = Depends(get_current_user),
    db: Prisma = Depends(get_db)
):
    if current_user.role not in ["SUPER_ADMIN", "ADMIN"]:
        raise HTTPException(status_code=403, detail="Not authorized to update users")

    user = await db.user.find_unique(where={"id": user_id})
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
    return format_user_response(updated_user)

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

    updated_user = await db.user.update(
        where={"id": user_id},
        data={"isArchived": True}
    )
    return format_user_response(updated_user)
