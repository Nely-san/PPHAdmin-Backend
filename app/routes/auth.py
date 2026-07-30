from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from prisma import Prisma

from app.core.config import settings
from app.core.database import get_db
from app.core.security import verify_password, create_access_token, ALGORITHM
from app.models.auth import Token, LoginRequest, UserProfile, PersonDetail

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

async def get_current_user(token: str = Depends(oauth2_scheme), db: Prisma = Depends(get_db)) -> UserProfile:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = await db.user.find_unique(
        where={"username": username},
        include={
            "person": {
                "include": {
                    "company": True,
                    "department": True
                }
            }
        }
    )
    if user is None:
        raise credentials_exception

    person_detail = None
    if user.person:
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
            companyName=user.person.company.name if user.person.company else None,
            companyCode=user.person.company.code if user.person.company else None,
            departmentName=user.person.department.name if user.person.department else None,
            departmentCode=user.person.department.code if user.person.department else None,
            schoolName=user.person.schoolName,
            coordinatorContact=user.person.coordinatorContact,
            requiredOjtHours=float(user.person.requiredOjtHours) if user.person.requiredOjtHours is not None else 0.0,
            renderedOjtHours=float(user.person.renderedOjtHours) if user.person.renderedOjtHours is not None else 0.0,
        )

    return UserProfile(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        createdAt=user.createdAt.isoformat() if user.createdAt else None,
        person=person_detail
    )

@router.post("/login", response_model=Token)
async def login(request: LoginRequest, db: Prisma = Depends(get_db)):
    # Query database for user by username or email
    user = await db.user.find_first(
        where={
            "OR": [
                {"username": request.username},
                {"email": request.username}
            ]
        }
    )

    if not user or not verify_password(request.password, user.passwordHash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )

    access_token = create_access_token(subject=user.username)
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/logout")
async def logout():
    return {"message": "Successfully logged out"}

@router.get("/me", response_model=UserProfile)
async def get_me(current_user: UserProfile = Depends(get_current_user)):
    return current_user
