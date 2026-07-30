from fastapi import APIRouter, Depends
from app.core.database import get_db
from app.models.company import CompanyResponse
from prisma import Prisma

router = APIRouter()

@router.get("/", response_model=list[CompanyResponse])
async def list_companies(db: Prisma = Depends(get_db)):
    """
    List company entities.
    """
    return [
        {"id": "1", "name": "Company Entity 1 (Real Estate)"},
        {"id": "2", "name": "Company Entity 2 (Real Estate)"},
        {"id": "3", "name": "Company Entity 3 (Web Tech)"},
        {"id": "4", "name": "Company Entity 4 (Tech Support)"}
    ]
