from typing import List, Optional
from datetime import datetime, date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status
from prisma import Prisma
from app.core.database import get_db
from app.models.person import (
    PersonCreateRequest,
    PersonUpdateRequest,
    PersonDetailResponse,
    QuickOjtHoursRequest,
)

router = APIRouter()

def format_person_response(p) -> PersonDetailResponse:
    date_started_str = None
    if p.dateStarted:
        if isinstance(p.dateStarted, (datetime, date)):
            date_started_str = p.dateStarted.strftime("%Y-%m-%d")
        else:
            date_started_str = str(p.dateStarted)

    base_rate_val = float(p.baseRate) if p.baseRate is not None else 0.0
    required_hours_val = float(p.requiredOjtHours) if p.requiredOjtHours is not None else None
    rendered_hours_val = float(p.renderedOjtHours) if p.renderedOjtHours is not None else None

    return PersonDetailResponse(
        id=p.id,
        userId=p.userId,
        biometricId=p.biometricId,
        name=p.name,
        personType=str(p.personType),
        employmentMode=str(p.employmentMode),
        rateType=str(p.rateType),
        baseRate=base_rate_val,
        dateStarted=date_started_str,
        status=str(p.status),
        companyId=p.companyId,
        companyName=p.company.name if p.company else None,
        companyCode=p.company.code if p.company else None,
        departmentId=p.departmentId,
        departmentName=p.department.name if p.department else None,
        departmentCode=p.department.code if p.department else None,
        schoolName=p.schoolName,
        coordinatorContact=p.coordinatorContact,
        requiredOjtHours=required_hours_val,
        renderedOjtHours=rendered_hours_val,
    )

@router.get("/", response_model=List[PersonDetailResponse])
async def list_persons(
    company_id: Optional[str] = None,
    person_type: Optional[str] = None,
    status_filter: Optional[str] = None,
    db: Prisma = Depends(get_db)
):
    """
    List employees and OJTs.
    """
    where_clause = {}
    if company_id:
        if company_id.upper() == "UNASSIGNED":
            where_clause["companyId"] = None
        else:
            where_clause["companyId"] = company_id
    if person_type:
        where_clause["personType"] = person_type
    if status_filter:
        where_clause["status"] = status_filter

    persons = await db.person.find_many(
        where=where_clause,
        include={
            "company": True,
            "department": True,
        },
        order={"name": "asc"}
    )
    return [format_person_response(p) for p in persons]

@router.get("/{person_id}", response_model=PersonDetailResponse)
async def get_person(person_id: str, db: Prisma = Depends(get_db)):
    """
    Get person details by ID.
    """
    person = await db.person.find_unique(
        where={"id": person_id},
        include={"company": True, "department": True}
    )
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    return format_person_response(person)

@router.post("/", response_model=PersonDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_person(payload: PersonCreateRequest, db: Prisma = Depends(get_db)):
    """
    Create a new employee or OJT intern profile.
    """
    company_id_val = payload.companyId if payload.companyId and payload.companyId.strip() else None
    dept_id_val = payload.departmentId if payload.departmentId and payload.departmentId.strip() else None

    if company_id_val:
        company = await db.company.find_unique(where={"id": company_id_val})
        if not company:
            raise HTTPException(status_code=400, detail="Specified company does not exist")

    if dept_id_val:
        dept = await db.department.find_unique(where={"id": dept_id_val})
        if not dept:
            raise HTTPException(status_code=400, detail="Specified department does not exist")

    if payload.biometricId:
        existing_bio = await db.person.find_unique(where={"biometricId": payload.biometricId})
        if existing_bio:
            raise HTTPException(status_code=400, detail=f"Biometric ID '{payload.biometricId}' is already assigned to {existing_bio.name}")

    date_started_val = datetime.now()
    if payload.dateStarted:
        try:
            date_started_val = datetime.strptime(payload.dateStarted, "%Y-%m-%d")
        except ValueError:
            pass

    if payload.personType == "OJT" and (not payload.schoolName or not payload.schoolName.strip()):
        raise HTTPException(status_code=400, detail="School / University is required when person type is OJT")

    data_create = {
        "name": payload.name,
        "userId": payload.userId or None,
        "biometricId": payload.biometricId or None,
        "personType": payload.personType,
        "employmentMode": payload.employmentMode,
        "rateType": payload.rateType,
        "baseRate": Decimal(str(payload.baseRate or 0.0)),
        "dateStarted": date_started_val,
        "status": payload.status,
        "companyId": company_id_val,
        "departmentId": dept_id_val,
        "schoolName": payload.schoolName.strip() if payload.personType == "OJT" and payload.schoolName else None,
        "coordinatorContact": payload.coordinatorContact if payload.personType == "OJT" else None,
        "requiredOjtHours": Decimal(str(payload.requiredOjtHours or 0.0)) if payload.personType == "OJT" and payload.requiredOjtHours is not None else None,
        "renderedOjtHours": Decimal(str(payload.renderedOjtHours or 0.0)) if payload.personType == "OJT" and payload.renderedOjtHours is not None else Decimal("0.0"),
    }

    created = await db.person.create(data=data_create)
    
    reloaded = await db.person.find_unique(
        where={"id": created.id},
        include={"company": True, "department": True}
    )
    return format_person_response(reloaded)

@router.put("/{person_id}", response_model=PersonDetailResponse)
@router.patch("/{person_id}", response_model=PersonDetailResponse)
async def update_person(person_id: str, payload: PersonUpdateRequest, db: Prisma = Depends(get_db)):
    """
    Modify an employee or OJT profile.
    """
    existing = await db.person.find_unique(where={"id": person_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Person record not found")

    update_data = {}
    if payload.name is not None:
        update_data["name"] = payload.name
    if payload.biometricId is not None:
        if payload.biometricId != existing.biometricId and payload.biometricId != "":
            dup = await db.person.find_unique(where={"biometricId": payload.biometricId})
            if dup:
                raise HTTPException(status_code=400, detail=f"Biometric ID '{payload.biometricId}' is already assigned")
        update_data["biometricId"] = payload.biometricId if payload.biometricId != "" else None
    if payload.personType is not None:
        update_data["personType"] = payload.personType
    if payload.employmentMode is not None:
        update_data["employmentMode"] = payload.employmentMode
    if payload.rateType is not None:
        update_data["rateType"] = payload.rateType
    if payload.baseRate is not None:
        update_data["baseRate"] = Decimal(str(payload.baseRate))
    if payload.dateStarted is not None:
        try:
            update_data["dateStarted"] = datetime.strptime(payload.dateStarted, "%Y-%m-%d")
        except ValueError:
            pass
    if payload.status is not None:
        update_data["status"] = payload.status
    if payload.companyId is not None:
        update_data["companyId"] = payload.companyId if payload.companyId and payload.companyId.strip() else None
    if payload.departmentId is not None:
        update_data["departmentId"] = payload.departmentId if payload.departmentId and payload.departmentId.strip() else None
    if payload.schoolName is not None:
        update_data["schoolName"] = payload.schoolName
    if payload.coordinatorContact is not None:
        update_data["coordinatorContact"] = payload.coordinatorContact
    if payload.requiredOjtHours is not None:
        update_data["requiredOjtHours"] = Decimal(str(payload.requiredOjtHours))
    if payload.renderedOjtHours is not None:
        update_data["renderedOjtHours"] = Decimal(str(payload.renderedOjtHours))

    updated = await db.person.update(where={"id": person_id}, data=update_data)

    reloaded = await db.person.find_unique(
        where={"id": updated.id},
        include={"company": True, "department": True}
    )
    return format_person_response(reloaded)

@router.patch("/{person_id}/ojt-hours", response_model=PersonDetailResponse)
async def update_ojt_hours(person_id: str, payload: QuickOjtHoursRequest, db: Prisma = Depends(get_db)):
    """
    Add rendered OJT hours to a trainee's total progress.
    """
    existing = await db.person.find_unique(where={"id": person_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Person record not found")

    current_hours = float(existing.renderedOjtHours or 0.0)
    new_hours = max(0.0, current_hours + payload.hoursToAdd)

    updated = await db.person.update(
        where={"id": person_id},
        data={"renderedOjtHours": Decimal(str(new_hours))}
    )

    reloaded = await db.person.find_unique(
        where={"id": updated.id},
        include={"company": True, "department": True}
    )
    return format_person_response(reloaded)

@router.delete("/{person_id}", response_model=PersonDetailResponse)
@router.patch("/{person_id}/archive", response_model=PersonDetailResponse)
async def archive_person(person_id: str, db: Prisma = Depends(get_db)):
    """
    Archive a person record instead of permanently deleting it.
    """
    existing = await db.person.find_unique(where={"id": person_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Person record not found")

    updated = await db.person.update(
        where={"id": person_id},
        data={"status": "ARCHIVED"}
    )
    reloaded = await db.person.find_unique(
        where={"id": updated.id},
        include={"company": True, "department": True}
    )
    return format_person_response(reloaded)

@router.patch("/{person_id}/unarchive", response_model=PersonDetailResponse)
@router.patch("/{person_id}/restore", response_model=PersonDetailResponse)
async def unarchive_person(person_id: str, db: Prisma = Depends(get_db)):
    """
    Unarchive / restore an archived person record back to ACTIVE status.
    """
    existing = await db.person.find_unique(where={"id": person_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Person record not found")

    updated = await db.person.update(
        where={"id": person_id},
        data={"status": "ACTIVE"}
    )

    reloaded = await db.person.find_unique(
        where={"id": updated.id},
        include={"company": True, "department": True}
    )
    return format_person_response(reloaded)
