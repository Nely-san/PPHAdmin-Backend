from fastapi import APIRouter, Depends, HTTPException, status
from app.core.database import get_db
from app.models.payroll import PayrollRecordResponse, PayrollGenerateRequest
from app.services.payroll_engine import compute_payroll_cutoff
from prisma import Prisma

router = APIRouter()

@router.post("/generate", response_model=list[PayrollRecordResponse])
async def generate_payroll_draft(payload: PayrollGenerateRequest, db: Prisma = Depends(get_db)):
    """
    Triggers cutoff payroll calculations for the specified dates and entities.
    """
    records = await compute_payroll_cutoff(payload.cutoff_start, payload.cutoff_end, payload.company_id, db)
    
    for record in records:
        person = await db.person.find_unique(where={"id": record.person_id})
        if person and person.userId:
            from app.services.notification import dispatch_notification
            from app.models.notification import NotificationCreate
            from prisma.enums import NotificationPriority

            await dispatch_notification(
                NotificationCreate(
                    userId=person.userId,
                    title="Payroll Summary Ready",
                    message=f"Payroll computation details for the cutoff starting {payload.cutoff_start} have been finalized.",
                    category="PAYROLL",
                    priority=NotificationPriority.LOW,
                    actionUrl="my-payslips"
                ),
                db
            )
            
    return records

@router.patch("/{payroll_id}/approve", response_model=PayrollRecordResponse)
async def approve_payroll(payroll_id: str, db: Prisma = Depends(get_db)):
    """
    Approve payroll records and lock the corresponding attendance logs.
    """
    # payroll = await db.payroll_records.update(where={"id": payroll_id}, data={"status": "APPROVED"})
    # Lock logs: await db.attendance_logs.update_many(where={"payroll_id": payroll_id}, data={"is_locked": True})
    raise HTTPException(status_code=501, detail="Prisma database sync pending")
