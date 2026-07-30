from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from prisma import Prisma
from app.core.database import get_db
from app.models.company import (
    CompanyCreate,
    CompanyUpdate,
    CompanyResponse,
    DepartmentCreate,
    DepartmentUpdate,
    DepartmentResponse,
    OrgCompanyNode,
    OrgDepartmentNode,
    OrgPersonNode,
)

router = APIRouter()

@router.get("/", response_model=List[CompanyResponse])
async def list_companies(db: Prisma = Depends(get_db)):
    """
    List all companies with their departments and personnel headcounts.
    """
    companies = await db.company.find_many(
        include={
            "departments": {
                "include": {
                    "persons": True
                }
            },
            "persons": True
        }
    )

    result = []
    for c in companies:
        dept_list = []
        if c.departments:
            for d in c.departments:
                head_count = len(d.persons) if d.persons else 0
                dept_list.append(
                    DepartmentResponse(
                        id=d.id,
                        companyId=d.companyId,
                        name=d.name,
                        code=d.code,
                        headCount=head_count,
                    )
                )

        total_staff = len(c.persons) if c.persons else 0
        result.append(
            CompanyResponse(
                id=c.id,
                name=c.name,
                code=c.code,
                totalPersonnel=total_staff,
                departments=dept_list,
            )
        )

    return result


@router.post("/", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
async def create_company(payload: CompanyCreate, db: Prisma = Depends(get_db)):
    """
    Create a new company entity.
    """
    if payload.code:
        existing = await db.company.find_unique(where={"code": payload.code})
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Company code '{payload.code}' already exists.",
            )

    new_company = await db.company.create(
        data={
            "name": payload.name,
            "code": payload.code.upper() if payload.code else None,
        }
    )

    return CompanyResponse(
        id=new_company.id,
        name=new_company.name,
        code=new_company.code,
        totalPersonnel=0,
        departments=[],
    )


@router.put("/{company_id}", response_model=CompanyResponse)
async def update_company(
    company_id: str, payload: CompanyUpdate, db: Prisma = Depends(get_db)
):
    """
    Update company details.
    """
    company = await db.company.find_unique(where={"id": company_id})
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Company not found"
        )

    update_data = {}
    if payload.name is not None:
        update_data["name"] = payload.name
    if payload.code is not None:
        if payload.code != company.code:
            existing = await db.company.find_unique(where={"code": payload.code})
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Company code '{payload.code}' is already taken.",
                )
        update_data["code"] = payload.code.upper() if payload.code else None

    updated = await db.company.update(where={"id": company_id}, data=update_data)
    
    # Reload company with relations
    reloaded = await db.company.find_unique(
        where={"id": updated.id},
        include={"departments": {"include": {"persons": True}}, "persons": True},
    )

    dept_list = []
    if reloaded.departments:
        for d in reloaded.departments:
            dept_list.append(
                DepartmentResponse(
                    id=d.id,
                    companyId=d.companyId,
                    name=d.name,
                    code=d.code,
                    headCount=len(d.persons) if d.persons else 0,
                )
            )

    return CompanyResponse(
        id=reloaded.id,
        name=reloaded.name,
        code=reloaded.code,
        totalPersonnel=len(reloaded.persons) if reloaded.persons else 0,
        departments=dept_list,
    )


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company(company_id: str, db: Prisma = Depends(get_db)):
    """
    Delete a company entity and cascade delete associated departments.
    """
    company = await db.company.find_unique(where={"id": company_id})
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Company not found"
        )

    await db.company.delete(where={"id": company_id})
    return None


@router.post(
    "/{company_id}/departments",
    response_model=DepartmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_department(
    company_id: str, payload: DepartmentCreate, db: Prisma = Depends(get_db)
):
    """
    Create a new department under a company.
    """
    company = await db.company.find_unique(where={"id": company_id})
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Company not found"
        )

    new_dept = await db.department.create(
        data={
            "companyId": company_id,
            "name": payload.name,
            "code": payload.code.upper() if payload.code else None,
        }
    )

    return DepartmentResponse(
        id=new_dept.id,
        companyId=new_dept.companyId,
        name=new_dept.name,
        code=new_dept.code,
        headCount=0,
    )


@router.put("/departments/{department_id}", response_model=DepartmentResponse)
async def update_department(
    department_id: str, payload: DepartmentUpdate, db: Prisma = Depends(get_db)
):
    """
    Update department details.
    """
    dept = await db.department.find_unique(
        where={"id": department_id}, include={"persons": True}
    )
    if not dept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Department not found"
        )

    update_data = {}
    if payload.name is not None:
        update_data["name"] = payload.name
    if payload.code is not None:
        update_data["code"] = payload.code.upper() if payload.code else None

    updated = await db.department.update(
        where={"id": department_id}, data=update_data
    )

    return DepartmentResponse(
        id=updated.id,
        companyId=updated.companyId,
        name=updated.name,
        code=updated.code,
        headCount=len(dept.persons) if dept.persons else 0,
    )


@router.delete("/departments/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_department(department_id: str, db: Prisma = Depends(get_db)):
    """
    Delete a department.
    """
    dept = await db.department.find_unique(where={"id": department_id})
    if not dept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Department not found"
        )

    await db.department.delete(where={"id": department_id})
    return None


@router.get("/org-tree", response_model=List[OrgCompanyNode])
async def get_organization_tree(db: Prisma = Depends(get_db)):
    """
    Get full interactive organization tree hierarchy (Companies -> Departments -> Persons).
    """
    companies = await db.company.find_many(
        include={
            "departments": {
                "include": {
                    "persons": True
                }
            },
            "persons": True
        }
    )

    tree = []
    for c in companies:
        dept_nodes = []
        if c.departments:
            for d in c.departments:
                person_nodes = []
                if d.persons:
                    for p in d.persons:
                        person_nodes.append(
                            OrgPersonNode(
                                id=p.id,
                                name=p.name,
                                personType=str(p.personType),
                                employmentMode=str(p.employmentMode),
                                biometricId=p.biometricId,
                                status=str(p.status),
                            )
                        )
                dept_nodes.append(
                    OrgDepartmentNode(
                        id=d.id,
                        name=d.name,
                        code=d.code,
                        headCount=len(person_nodes),
                        persons=person_nodes,
                    )
                )

        tree.append(
            OrgCompanyNode(
                id=c.id,
                name=c.name,
                code=c.code,
                totalPersonnel=len(c.persons) if c.persons else 0,
                departments=dept_nodes,
            )
        )

    return tree

