from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from app.models.auth import Token, LoginRequest
from app.core.security import verify_password, create_access_token

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

@router.post("/login", response_model=Token)
async def login(request: LoginRequest):
    # Mock authentication - to be wired with MySQL / Prisma
    if request.username == "admin" and request.password == "admin123":
        access_token = create_access_token(subject=request.username)
        return {"access_token": access_token, "token_type": "bearer"}
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password"
    )

@router.post("/logout")
async def logout():
    return {"message": "Successfully logged out"}

@router.get("/me")
async def get_me(token: str = Depends(oauth2_scheme)):
    # To be resolved with Prisma DB logic
    return {"username": "admin", "role": "ADMIN"}
