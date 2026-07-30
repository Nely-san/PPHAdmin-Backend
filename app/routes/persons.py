from fastapi import APIRouter, Depends, HTTPException, status
from app.core.database import get_db
from app.models.person import PersonCreate, PersonUpdate, PersonResponse
from prisma import Prisma

router = APIRouter()

@router.get("/", response_model=list[PersonResponse])
async def list_persons(company_id: str | None = None, db: Prisma = Depends(get_db)):
    """
    List all active and archived employees and OJTs.
    """
    # Once schema.prisma is generated, this will use:
    # persons = await db.persons.find_many(where={"company_id": company_id} if company_id else None)
    return []

@router.post("/", response_model=PersonResponse, status_code=status.HTTP_201_CREATED)
async def create_person(payload: PersonCreate, db: Prisma = Depends(get_db)):
    """
    Create a new employee or OJT.
    """
    # created_person = await db.persons.create(data=payload.dict())
    raise HTTPException(status_code=501, detail="Prisma database sync pending")

@router.patch("/{person_id}", response_model=PersonResponse)
async def update_person(person_id: str, payload: PersonUpdate, db: Prisma = Depends(get_db)):
    """
    Modify an employee or OJT details.
    """
    raise HTTPException(status_code=501, detail="Prisma database sync pending")

@router.patch("/{person_id}/archive", response_model=PersonResponse)
async def archive_person(person_id: str, db: Prisma = Depends(get_db)):
    """
    Archive a person record instead of deleting it.
    """
    raise HTTPException(status_code=501, detail="Prisma database sync pending")
