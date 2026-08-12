import asyncio
import os
import sys
import json
from datetime import datetime, date, timezone, timedelta
from decimal import Decimal

# Ensure backend directory is in sys.path so app modules can be imported
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.security import get_password_hash
from prisma import Prisma
from prisma.enums import (
    Role,
    PersonType,
    EmploymentMode,
    RateType,
    PersonStatus,
    LogType,
    ScheduleType,
    AttendanceStatus,
    AbnormalStatus,
    PayrollStatus,
    PayrollItemType,
    NotificationPriority,
)


async def seed():
    print("=== Starting PPHAdmin Database Seeding ===")

    db = Prisma()
    await db.connect()

    try:
        # ==========================================
        # 1. CLEAN EXISTING DATABASE (Reverse Order)
        # ==========================================
        print("[1/10] Cleaning existing database records...")
        await db.payrollitem.delete_many()
        await db.payrollrecord.delete_many()
        await db.attendancesummary.delete_many()
        await db.attendanceperiod.delete_many()
        await db.abnormalclocking.delete_many()
        await db.attendancerecord.delete_many()
        await db.biometriclog.delete_many()
        await db.biometricimportbatch.delete_many()
        await db.schedule.delete_many()
        await db.shift.delete_many()
        await db.person.delete_many()
        await db.department.delete_many()
        await db.company.delete_many()
        await db.notificationpreference.delete_many()
        await db.notification.delete_many()
        await db.user.delete_many()
        print(" -> Clean completed.")

        # ==========================================
        # 2. CREATE SYSTEM USERS (ADMINS & MANAGERS)
        # ==========================================
        print("[2/10] Creating Administrative Users...")
        default_admin_password = get_password_hash("Admin@123")
        default_user_password = get_password_hash("User@123")

        super_admin_user = await db.user.create(
            data={
                "username": "superadmin",
                "email": "superadmin@gmail.com",
                "passwordHash": default_admin_password,
                "role": Role.SUPER_ADMIN,
            }
        )

        admin_user = await db.user.create(
            data={
                "username": "admin",
                "email": "admin@gmail.com",
                "passwordHash": default_admin_password,
                "role": Role.ADMIN,
            }
        )

        hr_admin_user = await db.user.create(
            data={
                "username": "hradmin",
                "email": "hr@gmail.com",
                "passwordHash": default_admin_password,
                "role": Role.HR_MANAGER,
            }
        )

        payroll_officer_user = await db.user.create(
            data={
                "username": "payroll",
                "email": "payroll@gmail.com",
                "passwordHash": default_admin_password,
                "role": Role.PAYROLL_OFFICER,
            }
        )



        # Create account entries for staff members
        jerald_user = await db.user.create(
            data={
                "username": "jerald",
                "email": "jerald.cruz@gmail.com",
                "passwordHash": default_user_password,
                "role": Role.EMPLOYEE,
            }
        )

        chabs_user = await db.user.create(
            data={
                "username": "chabs",
                "email": "chabs.santos@gmail.com",
                "passwordHash": default_user_password,
                "role": Role.EMPLOYEE,
            }
        )

        famela_user = await db.user.create(
            data={
                "username": "famela",
                "email": "famela.valena@gmail.com",
                "passwordHash": default_user_password,
                "role": Role.EMPLOYEE,
            }
        )

        alex_ojt_user = await db.user.create(
            data={
                "username": "ojt_alex",
                "email": "alex.rivera@gmail.com",
                "passwordHash": default_user_password,
                "role": Role.OJT,
            }
        )

        maria_ojt_user = await db.user.create(
            data={
                "username": "ojt_maria",
                "email": "maria.santos@gmail.com",
                "passwordHash": default_user_password,
                "role": Role.OJT,
            }
        )

        kaye_user = await db.user.create(
            data={
                "username": "kaye",
                "email": "kaye.mendoza@gmail.com",
                "passwordHash": default_user_password,
                "role": Role.EMPLOYEE,
            }
        )

        david_ojt_user = await db.user.create(
            data={
                "username": "ojt_david",
                "email": "david.tan@gmail.com",
                "passwordHash": default_user_password,
                "role": Role.OJT,
            }
        )

        # ==========================================
        # 3. CREATE COMPANIES & DEPARTMENTS (Skipped)
        # ==========================================
        print("[3/10] Skipped creating companies & departments (Disabled)...")

        # ==========================================
        # 4. CREATE SHIFTS
        # ==========================================
        print("[4/10] Creating Work Shifts...")
        reg_day_shift = await db.shift.create(
            data={
                "code": "REG-DAY",
                "name": "Standard Day Shift (8:00 AM - 5:00 PM)",
                "startTime": "08:00",
                "endTime": "17:00",
                "breakStartTime": "12:00",
                "breakEndTime": "13:00",
                "workHours": Decimal("8.00"),
                "isFlexible": False,
            }
        )

        flexi_shift = await db.shift.create(
            data={
                "code": "FLEXI-DAY",
                "name": "Flexible Work Shift (9:00 AM - 6:00 PM)",
                "startTime": "09:00",
                "endTime": "18:00",
                "breakStartTime": "12:00",
                "breakEndTime": "13:00",
                "workHours": Decimal("8.00"),
                "isFlexible": True,
            }
        )

        part_time_shift = await db.shift.create(
            data={
                "code": "PART-TIME",
                "name": "Part-Time Morning Shift (8:00 AM - 12:00 PM)",
                "startTime": "08:00",
                "endTime": "12:00",
                "workHours": Decimal("4.00"),
                "isFlexible": False,
            }
        )

        # ==========================================
        # 5. CREATE PERSONS (EMPLOYEES & OJTs)
        # ==========================================
        print("[5/10] Creating Employees & Trainees (Persons)...")
        # Employee 1: Jerald Cruz (Monthly Full-Time Dev)
        jerald_person = await db.person.create(
            data={
                "biometricId": "1",
                "name": "Jerald Cruz",
                "personType": PersonType.EMPLOYEE,
                "employmentMode": EmploymentMode.FULL_TIME,
                "rateType": RateType.MONTHLY,
                "baseRate": Decimal("35000.00"),
                "dateStarted": datetime(2024, 1, 15, tzinfo=timezone.utc),
                "status": PersonStatus.ACTIVE,
                "userId": jerald_user.id,
            }
        )

        # Employee 2: Chabs Santos (Daily Sales Officer)
        chabs_person = await db.person.create(
            data={
                "biometricId": "4",
                "name": "Chabs Santos",
                "personType": PersonType.EMPLOYEE,
                "employmentMode": EmploymentMode.FULL_TIME,
                "rateType": RateType.DAILY,
                "baseRate": Decimal("850.00"),
                "dateStarted": datetime(2024, 3, 1, tzinfo=timezone.utc),
                "status": PersonStatus.ACTIVE,
                "userId": chabs_user.id,
            }
        )

        # Employee 3: Famela Valena (Monthly QA Specialist)
        famela_person = await db.person.create(
            data={
                "biometricId": "13",
                "name": "Famela Valena",
                "personType": PersonType.EMPLOYEE,
                "employmentMode": EmploymentMode.FULL_TIME,
                "rateType": RateType.MONTHLY,
                "baseRate": Decimal("28000.00"),
                "dateStarted": datetime(2024, 6, 1, tzinfo=timezone.utc),
                "status": PersonStatus.ACTIVE,
                "userId": famela_user.id,
            }
        )

        # Employee 4: Mark Anthony (Daily Property Specialist)
        mark_person = await db.person.create(
            data={
                "biometricId": "66",
                "name": "Mark Anthony",
                "personType": PersonType.EMPLOYEE,
                "employmentMode": EmploymentMode.CONTRACT,
                "rateType": RateType.DAILY,
                "baseRate": Decimal("750.00"),
                "dateStarted": datetime(2025, 2, 1, tzinfo=timezone.utc),
                "status": PersonStatus.ACTIVE,
            }
        )

        # Trainee 1: Alex Rivera (OJT Intern Dev)
        alex_ojt_person = await db.person.create(
            data={
                "biometricId": "101",
                "name": "Alex Rivera",
                "personType": PersonType.OJT,
                "employmentMode": EmploymentMode.INTERN,
                "rateType": RateType.HOURLY,
                "baseRate": Decimal("0.00"),
                "dateStarted": datetime(2026, 6, 1, tzinfo=timezone.utc),
                "status": PersonStatus.ACTIVE,
                "userId": alex_ojt_user.id,
                "schoolName": "Polytechnic University of the Philippines",
                "coordinatorContact": "Prof. Garcia (0917-123-4567)",
                "requiredOjtHours": Decimal("500.00"),
                "renderedOjtHours": Decimal("184.50"),
            }
        )

        # Trainee 2: Maria Santos (OJT Intern Design)
        maria_ojt_person = await db.person.create(
            data={
                "biometricId": "102",
                "name": "Maria Santos",
                "personType": PersonType.OJT,
                "employmentMode": EmploymentMode.INTERN,
                "rateType": RateType.HOURLY,
                "baseRate": Decimal("0.00"),
                "dateStarted": datetime(2026, 6, 15, tzinfo=timezone.utc),
                "status": PersonStatus.ACTIVE,
                "userId": maria_ojt_user.id,
                "schoolName": "Technological University of the Philippines",
                "coordinatorContact": "Dr. Reyes (0918-987-6543)",
                "requiredOjtHours": Decimal("480.00"),
                "renderedOjtHours": Decimal("210.00"),
            }
        )

        # Unassigned Employee 1: Kaye Mendoza (Unassigned Company & Dept)
        kaye_person = await db.person.create(
            data={
                "biometricId": "77",
                "name": "Kaye Mendoza",
                "personType": PersonType.EMPLOYEE,
                "employmentMode": EmploymentMode.FULL_TIME,
                "rateType": RateType.MONTHLY,
                "baseRate": Decimal("30000.00"),
                "dateStarted": datetime(2026, 5, 1, tzinfo=timezone.utc),
                "status": PersonStatus.ACTIVE,
                "companyId": None,
                "departmentId": None,
                "userId": kaye_user.id,
            }
        )

        # Unassigned Employee 2: Christian Flores (Unassigned Company & Dept)
        christian_person = await db.person.create(
            data={
                "biometricId": "88",
                "name": "Christian Flores",
                "personType": PersonType.EMPLOYEE,
                "employmentMode": EmploymentMode.CONTRACT,
                "rateType": RateType.DAILY,
                "baseRate": Decimal("800.00"),
                "dateStarted": datetime(2026, 6, 1, tzinfo=timezone.utc),
                "status": PersonStatus.ACTIVE,
                "companyId": None,
                "departmentId": None,
            }
        )

        # Unassigned Trainee 1: David Tan (Unassigned OJT Intern)
        david_ojt_person = await db.person.create(
            data={
                "biometricId": "104",
                "name": "David Tan",
                "personType": PersonType.OJT,
                "employmentMode": EmploymentMode.INTERN,
                "rateType": RateType.HOURLY,
                "baseRate": Decimal("0.00"),
                "dateStarted": datetime(2026, 7, 1, tzinfo=timezone.utc),
                "status": PersonStatus.ACTIVE,
                "companyId": None,
                "departmentId": None,
                "userId": david_ojt_user.id,
                "schoolName": "Mapúa University",
                "coordinatorContact": "Dr. Alonzo (0919-555-0192)",
                "requiredOjtHours": Decimal("500.00"),
                "renderedOjtHours": Decimal("45.00"),
            }
        )

        # Unassigned Trainee 2: Patricia Gomez (Unassigned OJT Intern)
        patricia_ojt_person = await db.person.create(
            data={
                "biometricId": "105",
                "name": "Patricia Gomez",
                "personType": PersonType.OJT,
                "employmentMode": EmploymentMode.INTERN,
                "rateType": RateType.HOURLY,
                "baseRate": Decimal("0.00"),
                "dateStarted": datetime(2026, 7, 10, tzinfo=timezone.utc),
                "status": PersonStatus.ACTIVE,
                "companyId": None,
                "departmentId": None,
                "schoolName": "University of Santo Tomas",
                "coordinatorContact": "Prof. Villanueva (0920-888-7711)",
                "requiredOjtHours": Decimal("400.00"),
                "renderedOjtHours": Decimal("120.00"),
            }
        )

        # ==========================================
        # 6. CREATE SCHEDULES FOR CUTOFF PERIOD
        # ==========================================
        print("[6/10] Seeding Work Schedules for Period (2026-07-01 to 2026-07-14)...")
        sample_persons = [jerald_person, chabs_person, famela_person, mark_person, alex_ojt_person, maria_ojt_person]

        for day in range(1, 15):
            curr_date = datetime(2026, 7, day, tzinfo=timezone.utc)
            is_weekend = curr_date.weekday() >= 5  # 5=Sat, 6=Sun

            for person in sample_persons:
                await db.schedule.create(
                    data={
                        "personId": person.id,
                        "shiftId": reg_day_shift.id if not is_weekend else None,
                        "date": curr_date,
                        "scheduleType": ScheduleType.REST_DAY if is_weekend else ScheduleType.REGULAR,
                        "note": "Weekend Rest Day" if is_weekend else "Standard Regular Schedule",
                    }
                )

        # ==========================================
        # 7. BIOMETRIC IMPORT BATCH & LOGS
        # ==========================================
        print("[7/10] Creating Biometric Import Batch & Timecard Logs...")
        import_batch = await db.biometricimportbatch.create(
            data={
                "fileName": "07Statistic.xls",
                "periodStart": datetime(2026, 7, 1, tzinfo=timezone.utc),
                "periodEnd": datetime(2026, 7, 14, tzinfo=timezone.utc),
                "recordsImported": 84,
                "anomaliesDetected": 2,
            }
        )

        # Create sample raw logs for July 1 (Wednesday)
        # Jerald Check-in / Out
        await db.biometriclog.create(
            data={
                "personId": jerald_person.id,
                "biometricId": "1",
                "timestamp": datetime(2026, 7, 1, 7, 55, 0, tzinfo=timezone.utc),
                "logType": LogType.CHECK_IN,
                "deviceId": "DEV-01",
                "batchId": import_batch.id,
            }
        )
        await db.biometriclog.create(
            data={
                "personId": jerald_person.id,
                "biometricId": "1",
                "timestamp": datetime(2026, 7, 1, 17, 5, 0, tzinfo=timezone.utc),
                "logType": LogType.CHECK_OUT,
                "deviceId": "DEV-01",
                "batchId": import_batch.id,
            }
        )

        # Chabs Check-in (Late on July 3)
        await db.biometriclog.create(
            data={
                "personId": chabs_person.id,
                "biometricId": "4",
                "timestamp": datetime(2026, 7, 3, 8, 35, 0, tzinfo=timezone.utc),
                "logType": LogType.CHECK_IN,
                "deviceId": "DEV-01",
                "batchId": import_batch.id,
            }
        )

        # ==========================================
        # 8. ATTENDANCE PERIOD & DAILY RECORDS
        # ==========================================
        print("[8/10] Creating Attendance Period & Detailed Records...")
        period = await db.attendanceperiod.create(
            data={
                "name": "2026/07/01 ~ 07/14 (PPH)",
                "startDate": datetime(2026, 7, 1, tzinfo=timezone.utc),
                "endDate": datetime(2026, 7, 14, tzinfo=timezone.utc),
                "isClosed": False,
            }
        )

        # Create Attendance Records for employees for July 1..10 (workdays)
        for day in [1, 2, 3, 6, 7, 8, 9, 10, 13, 14]:
            rec_date = datetime(2026, 7, day, tzinfo=timezone.utc)
            is_chabs_late_day = (day == 3)

            # Jerald Record
            await db.attendancerecord.create(
                data={
                    "personId": jerald_person.id,
                    "date": rec_date,
                    "amIn": datetime(2026, 7, day, 7, 55, 0, tzinfo=timezone.utc),
                    "amOut": datetime(2026, 7, day, 12, 0, 0, tzinfo=timezone.utc),
                    "pmIn": datetime(2026, 7, day, 13, 0, 0, tzinfo=timezone.utc),
                    "pmOut": datetime(2026, 7, day, 17, 5, 0, tzinfo=timezone.utc),
                    "actualHours": Decimal("8.00"),
                    "requiredHours": Decimal("8.00"),
                    "tardinessMinutes": 0,
                    "status": AttendanceStatus.PRESENT,
                    "batchId": import_batch.id,
                }
            )

            # Chabs Record
            chabs_tardiness = 35 if is_chabs_late_day else 0
            chabs_status = AttendanceStatus.LATE if is_chabs_late_day else AttendanceStatus.PRESENT

            ch_rec = await db.attendancerecord.create(
                data={
                    "personId": chabs_person.id,
                    "date": rec_date,
                    "amIn": datetime(2026, 7, day, 8, 35 if is_chabs_late_day else 7, 58, 0, tzinfo=timezone.utc),
                    "amOut": datetime(2026, 7, day, 12, 0, 0, tzinfo=timezone.utc),
                    "pmIn": datetime(2026, 7, day, 13, 0, 0, tzinfo=timezone.utc),
                    "pmOut": datetime(2026, 7, day, 17, 0, 0, tzinfo=timezone.utc),
                    "actualHours": Decimal("7.42") if is_chabs_late_day else Decimal("8.00"),
                    "requiredHours": Decimal("8.00"),
                    "tardinessMinutes": chabs_tardiness,
                    "tardinessCount": 1 if is_chabs_late_day else 0,
                    "status": chabs_status,
                    "isAbnormal": is_chabs_late_day,
                    "batchId": import_batch.id,
                }
            )

            # If Chabs was late on July 3, create Abnormal Clocking entry
            if is_chabs_late_day:
                await db.abnormalclocking.create(
                    data={
                        "attendanceRecordId": ch_rec.id,
                        "personId": chabs_person.id,
                        "date": rec_date,
                        "amIn": "08:35",
                        "amOut": "12:00",
                        "pmIn": "13:00",
                        "pmOut": "17:00",
                        "tardinessMinutes": 35,
                        "totalAbnormalMinutes": 35,
                        "reason": "Traffic congestion along EDSA due to heavy rain",
                        "status": AbnormalStatus.PENDING,
                    }
                )

        # ==========================================
        # 9. ATTENDANCE SUMMARIES (PERIOD TOTALS)
        # ==========================================
        print("[9/10] Creating Attendance Summaries...")
        await db.attendancesummary.create(
            data={
                "periodId": period.id,
                "personId": jerald_person.id,
                "batchId": import_batch.id,
                "requiredHours": Decimal("80.00"),
                "actualHours": Decimal("80.00"),
                "tardinessCount": 0,
                "tardinessMinutes": 0,
                "earlyLeaveCount": 0,
                "earlyLeaveMinutes": 0,
                "overtimeRegular": Decimal("2.50"),
                "requiredDays": 10,
                "actualDays": 10,
                "actualPay": Decimal("17500.00"),
                "memo": "Perfect attendance for July 1-14 cutoff",
            }
        )

        await db.attendancesummary.create(
            data={
                "periodId": period.id,
                "personId": chabs_person.id,
                "batchId": import_batch.id,
                "requiredHours": Decimal("80.00"),
                "actualHours": Decimal("79.42"),
                "tardinessCount": 1,
                "tardinessMinutes": 35,
                "earlyLeaveCount": 0,
                "earlyLeaveMinutes": 0,
                "requiredDays": 10,
                "actualDays": 10,
                "payDeduction": Decimal("185.94"),
                "actualPay": Decimal("8314.06"),
                "memo": "1 late clock-in incident recorded",
            }
        )

        await db.attendancesummary.create(
            data={
                "periodId": period.id,
                "personId": alex_ojt_person.id,
                "batchId": import_batch.id,
                "requiredHours": Decimal("80.00"),
                "actualHours": Decimal("80.00"),
                "requiredDays": 10,
                "actualDays": 10,
                "memo": "OJT Intern rendered 80 hrs towards 500 hr target",
            }
        )

        # ==========================================
        # 10. PAYROLL RECORDS & BREAKDOWN ITEMS
        # ==========================================
        print("[10/10] Seeding Semi-Monthly Payroll Records & Line Items...")
        cutoff_start = datetime(2026, 7, 1, tzinfo=timezone.utc)
        cutoff_end = datetime(2026, 7, 14, tzinfo=timezone.utc)

        # Payroll 1: Jerald Cruz (Monthly 35,000 PHP => Base 17,500 PHP)
        jerald_payroll = await db.payrollrecord.create(
            data={
                "personId": jerald_person.id,
                "cutoffStart": cutoff_start,
                "cutoffEnd": cutoff_end,
                "grossPay": Decimal("18046.88"),  # Base 17,500 + OT
                "totalDeductions": Decimal("1850.00"),
                "netPay": Decimal("16196.88"),
                "status": PayrollStatus.APPROVED,
            }
        )

        await db.payrollitem.create_many(
            data=[
                {
                    "payrollRecordId": jerald_payroll.id,
                    "itemType": PayrollItemType.EARNING,
                    "description": "Basic Semi-Monthly Salary",
                    "amount": Decimal("17500.00"),
                },
                {
                    "payrollRecordId": jerald_payroll.id,
                    "itemType": PayrollItemType.EARNING,
                    "description": "Regular Overtime Pay (2.5 hrs)",
                    "amount": Decimal("546.88"),
                },
                {
                    "payrollRecordId": jerald_payroll.id,
                    "itemType": PayrollItemType.DEDUCTION,
                    "description": "SSS Contribution",
                    "amount": Decimal("1000.00"),
                },
                {
                    "payrollRecordId": jerald_payroll.id,
                    "itemType": PayrollItemType.DEDUCTION,
                    "description": "PhilHealth Contribution",
                    "amount": Decimal("450.00"),
                },
                {
                    "payrollRecordId": jerald_payroll.id,
                    "itemType": PayrollItemType.DEDUCTION,
                    "description": "Pag-IBIG Contribution",
                    "amount": Decimal("200.00"),
                },
                {
                    "payrollRecordId": jerald_payroll.id,
                    "itemType": PayrollItemType.DEDUCTION,
                    "description": "Withholding Tax",
                    "amount": Decimal("200.00"),
                },
            ]
        )

        # Payroll 2: Chabs Santos (Daily 850 PHP x 10 days = 8,500 PHP)
        chabs_payroll = await db.payrollrecord.create(
            data={
                "personId": chabs_person.id,
                "cutoffStart": cutoff_start,
                "cutoffEnd": cutoff_end,
                "grossPay": Decimal("8500.00"),
                "totalDeductions": Decimal("685.94"),
                "netPay": Decimal("7814.06"),
                "status": PayrollStatus.DRAFT,
            }
        )

        await db.payrollitem.create_many(
            data=[
                {
                    "payrollRecordId": chabs_payroll.id,
                    "itemType": PayrollItemType.EARNING,
                    "description": "Daily Rate Base Pay (10 days)",
                    "amount": Decimal("8500.00"),
                },
                {
                    "payrollRecordId": chabs_payroll.id,
                    "itemType": PayrollItemType.DEDUCTION,
                    "description": "Tardiness Deduction (35 mins)",
                    "amount": Decimal("185.94"),
                },
                {
                    "payrollRecordId": chabs_payroll.id,
                    "itemType": PayrollItemType.DEDUCTION,
                    "description": "SSS Contribution",
                    "amount": Decimal("300.00"),
                },
                {
                    "payrollRecordId": chabs_payroll.id,
                    "itemType": PayrollItemType.DEDUCTION,
                    "description": "PhilHealth Contribution",
                    "amount": Decimal("200.00"),
                },
            ]
        )

        # ==========================================
        # 11. CREATE NOTIFICATIONS & PREFERENCES
        # ==========================================
        print("[11/10] Seeding Notification Preferences & Notifications...")
        all_users = [
            super_admin_user,
            admin_user,
            hr_admin_user,
            payroll_officer_user,
            jerald_user,
            chabs_user,
            famela_user,
            alex_ojt_user,
            maria_ojt_user,
            kaye_user,
            david_ojt_user,
        ]

        for u in all_users:
            await db.notificationpreference.create(
                data={
                    "userId": u.id,
                    "enableInApp": True,
                    "notifyAttendance": True,
                    "notifyPayroll": True,
                    "notifyLeave": True,
                }
            )

        notifications_data = [
            # HR Manager Notifications
            {
                "userId": hr_admin_user.id,
                "title": "Pending Abnormal Clocking Request",
                "message": "Chabs Santos submitted an abnormal clocking request for 2026-07-03 (35 mins late). Reason: Traffic congestion along EDSA due to heavy rain.",
                "category": "ATTENDANCE",
                "priority": NotificationPriority.HIGH,
                "actionUrl": "attendance-exceptions",
                "createdAt": datetime(2026, 7, 3, 9, 0, 0, tzinfo=timezone.utc),
            },
            {
                "userId": hr_admin_user.id,
                "title": "Biometric Import Complete",
                "message": "Import batch '07Statistic.xls' successfully processed: 84 records imported, 2 anomalies detected.",
                "category": "BIOMETRIC",
                "priority": NotificationPriority.MEDIUM,
                "actionUrl": "attendance",
                "createdAt": datetime(2026, 7, 14, 18, 0, 0, tzinfo=timezone.utc),
            },
            {
                "userId": hr_admin_user.id,
                "title": "Unassigned Personnel Detected",
                "message": "There are 4 active personnel (Kaye Mendoza, Christian Flores, David Tan, Patricia Gomez) without a company or department assignment.",
                "category": "HR",
                "priority": NotificationPriority.MEDIUM,
                "actionUrl": "employees",
                "createdAt": datetime(2026, 7, 10, 10, 0, 0, tzinfo=timezone.utc),
            },
            # Admin Notifications
            {
                "userId": admin_user.id,
                "title": "Pending Abnormal Clocking Request",
                "message": "Chabs Santos submitted an abnormal clocking request for 2026-07-03 (35 mins late). Reason: Traffic congestion along EDSA due to heavy rain.",
                "category": "ATTENDANCE",
                "priority": NotificationPriority.HIGH,
                "actionUrl": "dashboard",
                "createdAt": datetime(2026, 7, 3, 9, 0, 0, tzinfo=timezone.utc),
            },
            {
                "userId": admin_user.id,
                "title": "Unassigned Personnel Detected",
                "message": "There are 4 active personnel (Kaye Mendoza, Christian Flores, David Tan, Patricia Gomez) without a company or department assignment.",
                "category": "HR",
                "priority": NotificationPriority.MEDIUM,
                "actionUrl": "employees",
                "createdAt": datetime(2026, 7, 10, 10, 0, 0, tzinfo=timezone.utc),
            },
            # Payroll Officer Notifications
            {
                "userId": payroll_officer_user.id,
                "title": "Payroll Review Required",
                "message": "Payroll for Chabs Santos (Period: 2026-07-01 to 2026-07-14) is currently in DRAFT status. Deductions applied: 185.94 PHP.",
                "category": "PAYROLL",
                "priority": NotificationPriority.HIGH,
                "actionUrl": "payroll",
                "createdAt": datetime(2026, 7, 14, 17, 30, 0, tzinfo=timezone.utc),
            },
            {
                "userId": payroll_officer_user.id,
                "title": "Payroll Record Approved",
                "message": "Payroll record for Jerald Cruz (Period: 2026-07-01 to 2026-07-14) has been APPROVED. Net Pay: 16,196.88 PHP.",
                "category": "PAYROLL",
                "priority": NotificationPriority.MEDIUM,
                "actionUrl": "payroll",
                "createdAt": datetime(2026, 7, 14, 17, 15, 0, tzinfo=timezone.utc),
            },

            # Employee: Jerald Cruz
            {
                "userId": jerald_user.id,
                "title": "Payslip Available",
                "message": "Your payroll for period 2026-07-01 to 2026-07-14 has been approved. Net Pay: 16,196.88 PHP.",
                "category": "PAYROLL",
                "priority": NotificationPriority.MEDIUM,
                "actionUrl": "my-payslips",
                "createdAt": datetime(2026, 7, 14, 17, 20, 0, tzinfo=timezone.utc),
            },
            {
                "userId": jerald_user.id,
                "title": "Overtime Approved",
                "message": "Your overtime request of 2.50 hours for the July 1-14 cutoff has been approved.",
                "category": "ATTENDANCE",
                "priority": NotificationPriority.LOW,
                "actionUrl": "my-attendance",
                "createdAt": datetime(2026, 7, 14, 16, 0, 0, tzinfo=timezone.utc),
            },
            # Employee: Chabs Santos
            {
                "userId": chabs_user.id,
                "title": "Late Clock-in Warning",
                "message": "You were marked LATE on July 3, 2026 (Clock-in: 08:35 AM). Please file an abnormal clocking request if you have a valid reason.",
                "category": "ATTENDANCE",
                "priority": NotificationPriority.MEDIUM,
                "actionUrl": "my-attendance",
                "createdAt": datetime(2026, 7, 3, 8, 40, 0, tzinfo=timezone.utc),
            },
            {
                "userId": chabs_user.id,
                "title": "Abnormal Clocking Submitted",
                "message": "Your abnormal clocking explanation for July 3, 2026, has been submitted and is PENDING review.",
                "category": "ATTENDANCE",
                "priority": NotificationPriority.LOW,
                "actionUrl": "my-attendance",
                "createdAt": datetime(2026, 7, 3, 9, 0, 0, tzinfo=timezone.utc),
            },
            {
                "userId": chabs_user.id,
                "title": "Payroll Generated (Draft)",
                "message": "Your semi-monthly payroll draft is ready. Net Pay: 7,814.06 PHP (Deductions: 685.94 PHP).",
                "category": "PAYROLL",
                "priority": NotificationPriority.LOW,
                "actionUrl": "my-payslips",
                "createdAt": datetime(2026, 7, 14, 17, 35, 0, tzinfo=timezone.utc),
            },
            # Employee: Famela Valena
            {
                "userId": famela_user.id,
                "title": "Work Schedule Updated",
                "message": "Your regular work schedule for period 2026-07-01 to 2026-07-14 has been posted.",
                "category": "ATTENDANCE",
                "priority": NotificationPriority.LOW,
                "actionUrl": "my-roster",
                "createdAt": datetime(2026, 7, 1, 8, 0, 0, tzinfo=timezone.utc),
            },
            # Employee: Alex Rivera (OJT)
            {
                "userId": alex_ojt_user.id,
                "title": "OJT Progress Update",
                "message": "You have rendered 80.00 hours during this cutoff. Total Rendered: 184.50 / 500.00 hours (36.9% completed).",
                "category": "OJT",
                "priority": NotificationPriority.LOW,
                "actionUrl": "my-internship-hours",
                "createdAt": datetime(2026, 7, 14, 17, 5, 0, tzinfo=timezone.utc),
            },
            # Employee: Maria Santos (OJT)
            {
                "userId": maria_ojt_user.id,
                "title": "OJT Progress Update",
                "message": "You have rendered 210.00 hours towards your required 480.00 hours target (43.8% completed).",
                "category": "OJT",
                "priority": NotificationPriority.LOW,
                "actionUrl": "my-internship-hours",
                "createdAt": datetime(2026, 7, 14, 17, 5, 0, tzinfo=timezone.utc),
            },
            # Employee: Kaye Mendoza
            {
                "userId": kaye_user.id,
                "title": "Unassigned Profile Action Required",
                "message": "You are not assigned to a Company or Department. Please update your profile or contact HR.",
                "category": "HR",
                "priority": NotificationPriority.HIGH,
                "actionUrl": "dashboard",
                "createdAt": datetime(2026, 7, 10, 10, 5, 0, tzinfo=timezone.utc),
            },
            # Employee: David Tan (OJT)
            {
                "userId": david_ojt_user.id,
                "title": "Unassigned Profile Action Required",
                "message": "You are not assigned to a Company or Department. Please contact HR to resolve your OJT placement.",
                "category": "HR",
                "priority": NotificationPriority.HIGH,
                "actionUrl": "dashboard",
                "createdAt": datetime(2026, 7, 10, 10, 5, 0, tzinfo=timezone.utc),
            },
        ]

        for notif in notifications_data:
            await db.notification.create(data=notif)

        # ==========================================
        # 11. CREATE AUDIT LOGS (NEW)
        # ==========================================
        print("[11/10] Seeding System Audit Logs...")
        await db.auditlog.delete_many() # Clear existing logs
        
        audit_logs_data = [
            # 1. Super Admin creates an Employee account (Jerald)
            {
                "tableName": "users",
                "recordId": jerald_user.id,
                "action": "CREATE",
                "oldData": None,
                "newData": json.dumps({
                    "id": jerald_user.id,
                    "username": "jerald",
                    "email": "jerald.cruz@gmail.com",
                    "role": "EMPLOYEE",
                    "isArchived": False
                }),
                "changedBy": "superadmin",
                "createdAt": datetime(2026, 7, 1, 9, 0, 0, tzinfo=timezone.utc),
            },
            # 2. Admin creates employee profile (Chabs Santos)
            {
                "tableName": "persons",
                "recordId": chabs_person.id,
                "action": "CREATE",
                "oldData": None,
                "newData": json.dumps({
                    "id": chabs_person.id,
                    "name": "Chabs Santos",
                    "personType": "EMPLOYEE",
                    "employmentMode": "FULL_TIME",
                    "rateType": "DAILY",
                    "baseRate": 850.00,
                    "status": "ACTIVE",
                    "userId": chabs_user.id
                }),
                "changedBy": "admin",
                "createdAt": datetime(2026, 7, 1, 10, 15, 0, tzinfo=timezone.utc),
            },
            # 3. HR Admin updates Jerald Cruz base salary rate (Merit promotion)
            {
                "tableName": "persons",
                "recordId": jerald_person.id,
                "action": "UPDATE",
                "oldData": json.dumps({
                    "id": jerald_person.id,
                    "name": "Jerald Cruz",
                    "personType": "EMPLOYEE",
                    "baseRate": 25000.00,
                    "rateType": "MONTHLY",
                    "status": "ACTIVE"
                }),
                "newData": json.dumps({
                    "id": jerald_person.id,
                    "name": "Jerald Cruz",
                    "personType": "EMPLOYEE",
                    "baseRate": 27500.00,
                    "rateType": "MONTHLY",
                    "status": "ACTIVE"
                }),
                "changedBy": "hradmin",
                "createdAt": datetime(2026, 7, 12, 14, 30, 0, tzinfo=timezone.utc),
            },
            # 4. Biometric spreadsheet imports log
            {
                "tableName": "biometric_import_batches",
                "recordId": "batch-cutoff-jul-1",
                "action": "IMPORT",
                "oldData": None,
                "newData": json.dumps({
                    "fileName": "07Statistic_July_1_14.xls",
                    "recordsImported": 124,
                    "anomaliesDetected": 3,
                    "totalProcessed": 124
                }),
                "changedBy": "hradmin",
                "createdAt": datetime(2026, 7, 14, 17, 30, 0, tzinfo=timezone.utc),
            },
            # 5. Payroll Officer generates draft payroll cutoff
            {
                "tableName": "payroll_records",
                "recordId": "cutoff_2026-07-01_to_2026-07-14",
                "action": "GENERATE",
                "oldData": None,
                "newData": json.dumps({
                    "cutoffStart": "2026-07-01",
                    "cutoffEnd": "2026-07-14",
                    "recordsCount": 6,
                    "grossTotal": 145000.00,
                    "deductionsTotal": 4200.00,
                    "netTotal": 140800.00
                }),
                "changedBy": "payroll",
                "createdAt": datetime(2026, 7, 15, 10, 0, 0, tzinfo=timezone.utc),
            },
            # 6. Admin archives David Tan OJT (Completed/Finished)
            {
                "tableName": "persons",
                "recordId": david_ojt_person.id,
                "action": "ARCHIVE",
                "oldData": json.dumps({
                    "id": david_ojt_person.id,
                    "name": "David Tan",
                    "personType": "OJT",
                    "status": "ACTIVE"
                }),
                "newData": json.dumps({
                    "id": david_ojt_person.id,
                    "name": "David Tan",
                    "personType": "OJT",
                    "status": "ARCHIVED"
                }),
                "changedBy": "admin",
                "createdAt": datetime(2026, 7, 16, 11, 20, 0, tzinfo=timezone.utc),
            }
        ]

        for audit in audit_logs_data:
            await db.auditlog.create(data=audit)

        print("\n==================================================")
        print("   Database Seeding Completed Successfully!       ")
        print("==================================================")
        print("\nSeeded Accounts Summary:")
        print("  Super Admin : superadmin / Admin@123")
        print("  Admin       : admin / Admin@123")
        print("  HR Manager  : hradmin / Admin@123")
        print("  Payroll     : payroll / Admin@123")
        print("  Employee    : jerald / User@123 (Monthly Rate)")
        print("  Employee    : chabs / User@123 (Daily Rate)")
        print("  Employee    : famela / User@123 (Monthly Rate)")
        print("  OJT Intern  : ojt_alex / User@123 (500 Hr Target)")
        print("  OJT Intern  : ojt_maria / User@123 (480 Hr Target)")
        print("--------------------------------------------------\n")

    except Exception as e:
        print(f"[ERROR] Error during database seeding: {e}")
        raise e
    finally:
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(seed())
