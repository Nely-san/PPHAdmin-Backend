from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from app.core.database import get_db
from app.models.attendance import AttendanceLogResponse, AttendanceImportResponse
from app.services.attendance_parser import parse_attendance_excel
from prisma import Prisma

router = APIRouter()

@router.post("/import", response_model=AttendanceImportResponse)
async def import_biometric_data(file: UploadFile = File(...), db: Prisma = Depends(get_db)):
    """
    Upload and parse biometric timecard exports (.xls/.xlsx).
    """
    if not (file.filename.endswith(".xls") or file.filename.endswith(".xlsx")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Please upload .xls or .xlsx biometric files."
        )
    
    contents = await file.read()
    # Call parser service
    results = await parse_attendance_excel(contents, file.filename, db)
    return results

@router.get("/", response_model=list[dict])
async def get_attendance_logs(db: Prisma = Depends(get_db)):
    """
    Query attendance logs, optionally filtering by employee.
    """
    records = await db.attendancerecord.find_many(
        include={
            "person": {
                "include": {
                    "department": True
                }
            }
        },
        order={"date": "desc"}
    )
    
    frontend_logs = []
    for r in records:
        # Format times as "HH:MM"
        am_in_str = r.amIn.strftime("%H:%M") if r.amIn else None
        am_out_str = r.amOut.strftime("%H:%M") if r.amOut else None
        pm_in_str = r.pmIn.strftime("%H:%M") if r.pmIn else None
        pm_out_str = r.pmOut.strftime("%H:%M") if r.pmOut else None
        
        # Format date as YYYY-MM-DD
        date_str = r.date.strftime("%Y-%m-%d")
        
        dept_name = "General Operations"
        if r.person and r.person.department:
            dept_name = r.person.department.name
            
        frontend_logs.append({
            "id": r.id,
            "biometricId": r.person.biometricId if r.person else None,
            "personName": r.person.name if r.person else "Unknown",
            "personType": r.person.personType if r.person else "EMPLOYEE",
            "date": date_str,
            "amIn": am_in_str,
            "amOut": am_out_str,
            "pmIn": pm_in_str,
            "pmOut": pm_out_str,
            "actualHours": float(r.actualHours),
            "tardinessMinutes": r.tardinessMinutes,
            "status": r.status,  # "PRESENT" or "LATE"
            "isAbnormal": r.isAbnormal,
            "abnormalReason": r.memo,
            "departmentName": dept_name,
            "entryType": "BIOMETRIC",
            "batchId": r.batchId
        })
        
    return frontend_logs

@router.post("/reset")
async def reset_attendance_and_imported_persons(db: Prisma = Depends(get_db)):
    """
    Reset biometric attendance records and clean out imported biometric personnel accounts from database.
    """
    try:
        await db.attendancerecord.delete_many()
    except Exception as e:
        print(f"Delete attendance notice: {e}")

    try:
        seed_ids = ["1", "4", "13", "66", "77", "88", "101", "102", "104", "105"]
        await db.person.delete_many(
            where={
                "biometricId": {
                    "not_in": seed_ids
                }
            }
        )
    except Exception as e:
        print(f"Delete imported persons notice: {e}")

    return {"status": "success", "message": "Biometric attendance records and imported accounts reset cleanly."}

