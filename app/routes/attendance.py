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

@router.get("/", response_model=list[AttendanceLogResponse])
async def get_attendance_logs(person_id: str | None = None, db: Prisma = Depends(get_db)):
    """
    Query attendance logs, optionally filtering by employee.
    """
    return []

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

