from fastapi import APIRouter, Depends, HTTPException, Query, status
from prisma import Prisma
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from app.core.database import get_db
from app.routes.auth import get_current_user
from app.models.auth import UserProfile

router = APIRouter()

class AuditLogResponse(BaseModel):
    id: str
    tableName: str
    recordId: str
    action: str
    oldData: Optional[str] = None
    newData: Optional[str] = None
    changedBy: str
    createdAt: datetime

class PaginatedAuditLogsResponse(BaseModel):
    total: int
    page: int
    limit: int
    logs: List[AuditLogResponse]

@router.get("/", response_model=PaginatedAuditLogsResponse)
async def list_audit_logs(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    tableName: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    changedBy: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Prisma = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user)
):
    if current_user.role != "SUPER_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Only Super Admins can access system audit logs."
        )

    where = {}
    if tableName:
        where["tableName"] = tableName
    if action:
        where["action"] = action
    if changedBy:
        where["changedBy"] = changedBy
        
    if search:
        where["OR"] = [
            {"tableName": {"contains": search}},
            {"changedBy": {"contains": search}},
            {"action": {"contains": search}},
            {"recordId": {"contains": search}},
            {"oldData": {"contains": search}},
            {"newData": {"contains": search}},
        ]

    total = await db.auditlog.count(where=where)
    logs = await db.auditlog.find_many(
        where=where,
        skip=(page - 1) * limit,
        take=limit,
        order={"createdAt": "desc"}
    )

    return PaginatedAuditLogsResponse(
        total=total,
        page=page,
        limit=limit,
        logs=[
            AuditLogResponse(
                id=log.id,
                tableName=log.tableName,
                recordId=log.recordId,
                action=log.action,
                oldData=log.oldData,
                newData=log.newData,
                changedBy=log.changedBy,
                createdAt=log.createdAt
            )
            for log in logs
        ]
    )
