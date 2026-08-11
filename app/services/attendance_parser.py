import uuid
import re
from io import BytesIO
from datetime import datetime, timezone
from decimal import Decimal
import pandas as pd
from prisma import Prisma
from app.models.attendance import AttendanceImportResponse

def normalize_name(name: str) -> str:
    if not name:
        return ""
    return re.sub(r'[^a-z0-9\s]', '', name.lower()).strip()

def names_match(name1: str, name2: str) -> bool:
    if not name1 or not name2:
        return False
    n1 = normalize_name(name1)
    n2 = normalize_name(name2)
    if n1 == n2:
        return True
    set1 = set(n1.split())
    set2 = set(n2.split())
    return set1 == set2 and len(set1) > 0

def normalize_date(cell_value) -> str | None:
    if pd.isna(cell_value):
        return None
    
    # If it's a pandas Timestamp or datetime object
    if hasattr(cell_value, 'strftime'):
        try:
            return cell_value.strftime("%Y-%m-%d")
        except:
            pass

    # Support Excel date serial numbers (e.g. 46241 representing August 11, 2026)
    try:
        val_float = float(cell_value)
        # Excel date serial numbers for modern dates (1982 to 2064) fall between 30000 and 60000.
        if 30000 <= val_float <= 60000:
            parsed_dt = pd.to_datetime(val_float, unit='D', origin='1899-12-30')
            return parsed_dt.strftime("%Y-%m-%d")
    except:
        pass

    str_val = str(cell_value).strip()
    if not str_val:
        return None

    # Check if it has date separators (including dot and spaces) to ignore simple times
    if not any(char in str_val for char in ['-', '/', ',', '.', ' ']):
        return None

    # Pattern YYYY-MM-DD or YYYY.MM.DD or YYYY/MM/DD
    yyyymmdd = re.match(r'^(\d{4})[-/\.](\d{1,2})[-/\.](\d{1,2})', str_val)
    if yyyymmdd:
        y = yyyymmdd.group(1)
        m = yyyymmdd.group(2).zfill(2)
        d = yyyymmdd.group(3).zfill(2)
        return f"{y}-{m}-{d}"

    # Pattern MM/DD/YYYY or DD/MM/YYYY etc.
    mdys = re.match(r'^(\d{1,2})[-/\.](\d{1,2})[-/\.](\d{2,4})', str_val)
    if mdys:
        y_val = int(mdys.group(3))
        if y_val < 100:
            y_val += 2000
        m = mdys.group(1).zfill(2)
        d = mdys.group(2).zfill(2)
        
        month_val = int(m)
        day_val = int(d)
        if month_val > 12 and day_val <= 12:
            return f"{y_val}-{str(day_val).zfill(2)}-{str(month_val).zfill(2)}"
        return f"{y_val}-{m}-{d}"

    # Try parsing as generic date
    try:
        parsed = pd.to_datetime(str_val, errors='raise')
        return parsed.strftime("%Y-%m-%d")
    except:
        pass

    return None

def check_tardiness(am_in_str: str) -> tuple[bool, int]:
    # Try parsing time like HH:MM
    match = re.search(r'(\d{1,2}):(\d{2})', am_in_str)
    if match:
        h = int(match.group(1))
        m = int(match.group(2))
        if h < 7: # handle PM
            h += 12
        
        total_mins = h * 60 + m
        start_mins = 9 * 60 # 9:00 AM is 540
        grace_mins = 9 * 60 + 10 # 9:10 AM is 550
        
        if total_mins > grace_mins:
            late_mins = total_mins - start_mins
            return True, late_mins
    return False, 0

async def parse_attendance_excel(file_bytes: bytes, file_name: str, db: Prisma) -> AttendanceImportResponse:
    """
    Service to parse biometric .xls/.xlsx files and import attendance logs for ALL 72+ accounts.
    """
    batch_id = f"BATCH-IMPORT-{uuid.uuid4().hex[:8].upper()}"
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    imported_logs = []
    anomalies_count = 0
    newly_created_accounts_count = 0

    # 1. Try parsing Excel bytes using pandas / openpyxl / xlrd
    try:
        df_dict = pd.read_excel(BytesIO(file_bytes), sheet_name=None, header=None)
        account_map = {}

        for sheet_name, df in df_dict.items():
            current_bio_id = None
            current_name = None
            current_dept = None
            last_parsed_date = today_str

            # Detect Column Headers
            bio_id_idx = -1
            name_idx = -1
            dept_idx = -1
            date_idx = -1
            am_in_idx = -1
            am_out_idx = -1
            pm_in_idx = -1
            pm_out_idx = -1

            for row_idx, row in df.iterrows():
                row_str = " ".join([str(val).lower() for val in row.values if pd.notna(val)])
                if ("name" in row_str or "person" in row_str or "employee" in row_str) and \
                   ("no" in row_str or "id" in row_str or "ac-no" in row_str or "enroll" in row_str):
                    for idx, cell in enumerate(row.values):
                        if pd.isna(cell):
                            continue
                        str_cell = str(cell).strip().lower()
                        if "ac-no" in str_cell or "enroll" in str_cell or "biometric" in str_cell or str_cell in ["no", "id", "no."]:
                            bio_id_idx = idx
                        elif "name" in str_cell or "employee" in str_cell or "person" in str_cell or "user" in str_cell:
                            name_idx = idx
                        elif "dept" in str_cell or "department" in str_cell or "division" in str_cell:
                            dept_idx = idx
                        elif "date" in str_cell:
                            date_idx = idx
                        elif "am in" in str_cell or "clock in" in str_cell or "time in" in str_cell or str_cell == "in":
                            am_in_idx = idx
                        elif "am out" in str_cell:
                            am_out_idx = idx
                        elif "pm in" in str_cell:
                            pm_in_idx = idx
                        elif "pm out" in str_cell or "clock out" in str_cell or "time out" in str_cell or str_cell == "out":
                            pm_out_idx = idx
                    break

            for row_idx, row in df.iterrows():
                row_str = " ".join([str(val) for val in row.values if pd.notna(val)])
                
                # Check for block header like "AC-No: 42 Name: Dela Cruz, Juan"
                bio_match = re.search(r'(?:AC-No|Enroll ID|User ID|No|ID)[:\s]+(\d+)', row_str, re.I)
                name_match = re.search(r'(?:Name|Employee|Person)[:\s]+([A-Za-z0-9\s,\.\-]+?)(?=\s+(?:Dept|Card|Post|No|ID|$))', row_str, re.I)
                dept_match = re.search(r'(?:Dept|Department)[:\s]+([A-Za-z0-9\s,\.\-]+)', row_str, re.I)

                if bio_match:
                    current_bio_id = bio_match.group(1).strip()
                if name_match:
                    current_name = name_match.group(1).strip()
                if dept_match:
                    current_dept = dept_match.group(1).strip()

                # Extract numeric ID, Name, Date, and Times from row values
                bio_id = None
                person_name = None
                dept_name = current_dept or "General Operations"
                rec_date = last_parsed_date
                am_in = "08:55"
                am_out = "12:00"
                pm_in = "13:00"
                pm_out = "18:00"

                row_vals = list(row.values)
                
                # Try header-based indices first
                if bio_id_idx >= 0 and bio_id_idx < len(row_vals) and pd.notna(row_vals[bio_id_idx]) and str(row_vals[bio_id_idx]).strip().isdigit():
                    bio_id = str(row_vals[bio_id_idx]).strip()
                    if name_idx >= 0 and name_idx < len(row_vals) and pd.notna(row_vals[name_idx]):
                        person_name = str(row_vals[name_idx]).strip()
                    if dept_idx >= 0 and dept_idx < len(row_vals) and pd.notna(row_vals[dept_idx]):
                        dept_name = str(row_vals[dept_idx]).strip()
                    if date_idx >= 0 and date_idx < len(row_vals) and pd.notna(row_vals[date_idx]):
                        parsed_date = normalize_date(row_vals[date_idx])
                        if parsed_date:
                            rec_date = parsed_date
                            last_parsed_date = parsed_date
                    if am_in_idx >= 0 and am_in_idx < len(row_vals) and pd.notna(row_vals[am_in_idx]):
                        am_in = str(row_vals[am_in_idx]).strip()
                    if am_out_idx >= 0 and am_out_idx < len(row_vals) and pd.notna(row_vals[am_out_idx]):
                        am_out = str(row_vals[am_out_idx]).strip()
                    if pm_in_idx >= 0 and pm_in_idx < len(row_vals) and pd.notna(row_vals[pm_in_idx]):
                        pm_in = str(row_vals[pm_in_idx]).strip()
                    if pm_out_idx >= 0 and pm_out_idx < len(row_vals) and pd.notna(row_vals[pm_out_idx]):
                        pm_out = str(row_vals[pm_out_idx]).strip()
                elif current_bio_id:
                    bio_id = current_bio_id
                    person_name = current_name or f"Personnel #{current_bio_id}"
                    dept_name = current_dept or "General Operations"
                    if date_idx >= 0 and date_idx < len(row_vals) and pd.notna(row_vals[date_idx]):
                        parsed_date = normalize_date(row_vals[date_idx])
                        if parsed_date:
                            rec_date = parsed_date
                            last_parsed_date = parsed_date
                    if am_in_idx >= 0 and am_in_idx < len(row_vals) and pd.notna(row_vals[am_in_idx]):
                        am_in = str(row_vals[am_in_idx]).strip()
                    if am_out_idx >= 0 and am_out_idx < len(row_vals) and pd.notna(row_vals[am_out_idx]):
                        am_out = str(row_vals[am_out_idx]).strip()
                    if pm_in_idx >= 0 and pm_in_idx < len(row_vals) and pd.notna(row_vals[pm_in_idx]):
                        pm_in = str(row_vals[pm_in_idx]).strip()
                    if pm_out_idx >= 0 and pm_out_idx < len(row_vals) and pd.notna(row_vals[pm_out_idx]):
                        pm_out = str(row_vals[pm_out_idx]).strip()
                else:
                    # Fallback row check (Cell 0 numeric ID, Cell 1 Name string)
                    if len(row_vals) >= 2:
                        c0 = str(row_vals[0]).strip() if pd.notna(row_vals[0]) else ""
                        c1 = str(row_vals[1]).strip() if pd.notna(row_vals[1]) else ""
                        c2 = str(row_vals[2]).strip() if pd.notna(row_vals[2]) and len(row_vals) > 2 else ""

                        if c0.isdigit() and len(c1) >= 2 and not c1.isdigit():
                            bio_id = c0
                            person_name = c1
                            if c2 and not c2.isdigit():
                                dept_name = c2
                        elif c1.isdigit() and len(c2) >= 2 and not c2.isdigit():
                            bio_id = c1
                            person_name = c2

                if bio_id:
                    # Fallback cell scanning for the date if not correctly identified yet
                    parsed_date = None
                    if date_idx >= 0 and date_idx < len(row_vals) and pd.notna(row_vals[date_idx]):
                        parsed_date = normalize_date(row_vals[date_idx])
                    if not parsed_date:
                        for cell in row_vals:
                            d_val = normalize_date(cell)
                            if d_val:
                                parsed_date = d_val
                                break
                    if parsed_date:
                        rec_date = parsed_date
                        last_parsed_date = parsed_date

                    key = f"{bio_id}_{rec_date}"
                    if key not in account_map:
                        is_late, late_mins = check_tardiness(am_in)
                        if is_late:
                            anomalies_count += 1

                        p_type = "OJT" if (bio_id.isdigit() and int(bio_id) >= 100) else "EMPLOYEE"
                        actual_hours = round(8.0 - (late_mins / 60.0), 2) if is_late else 8.0

                        account_map[key] = {
                            "id": f"imported-{bio_id}-{rec_date}-{uuid.uuid4().hex[:6]}",
                            "biometricId": bio_id,
                            "personName": person_name or f"Personnel #{bio_id}",
                            "personType": p_type,
                            "date": rec_date,
                            "amIn": am_in,
                            "amOut": am_out,
                            "pmIn": pm_in,
                            "pmOut": pm_out,
                            "actualHours": actual_hours,
                            "tardinessMinutes": late_mins,
                            "status": "LATE" if is_late else "PRESENT",
                            "isAbnormal": is_late,
                            "abnormalReason": f"Late punch-in past 9:10 AM grace period threshold ({late_mins} mins late)" if is_late else None,
                            "departmentName": dept_name,
                            "entryType": "BIOMETRIC",
                        }

        if account_map:
            imported_logs = list(account_map.values())
            all_persons = await db.person.find_many()
            processed_bio_ids = set()

            # 0. Create BiometricImportBatch record
            try:
                # Determine date range from account_map
                dates = [item["date"] for item in account_map.values() if item.get("date")]
                min_date = None
                max_date = None
                if dates:
                    min_date_str = min(dates)
                    max_date_str = max(dates)
                    p_min = min_date_str.split("-")
                    p_max = max_date_str.split("-")
                    min_date = datetime(int(p_min[0]), int(p_min[1]), int(p_min[2]), tzinfo=timezone.utc)
                    max_date = datetime(int(p_max[0]), int(p_max[1]), int(p_max[2]), tzinfo=timezone.utc)

                await db.biometricimportbatch.create(
                    data={
                        "id": batch_id,
                        "fileName": file_name,
                        "periodStart": min_date,
                        "periodEnd": max_date,
                        "recordsImported": len(account_map),
                        "anomaliesDetected": anomalies_count
                    }
                )
            except Exception as batch_ex:
                print(f"BiometricImportBatch creation error: {batch_ex}")

            # 1. Register/upsert Person accounts
            for key, item in account_map.items():
                bio_id = item["biometricId"]
                if bio_id in processed_bio_ids:
                    continue
                processed_bio_ids.add(bio_id)
                try:
                    existing_person = await db.person.find_unique(where={"biometricId": bio_id})
                    if not existing_person:
                        # Check if an existing person account exists with matching name but no biometric ID
                        name_match_person = None
                        for p in all_persons:
                            if names_match(p.name, item["personName"]):
                                name_match_person = p
                                break

                        if name_match_person:
                            # Auto-link biometric ID to existing pre-created account!
                            await db.person.update(
                                where={"id": name_match_person.id},
                                data={"biometricId": bio_id}
                            )
                        else:
                            # Create new person record
                            p_type = "OJT" if (bio_id.isdigit() and int(bio_id) >= 100) else "EMPLOYEE"
                            await db.person.create(
                                data={
                                    "biometricId": bio_id,
                                    "name": item["personName"],
                                    "personType": p_type,
                                    "employmentMode": "INTERN" if p_type == "OJT" else "FULL_TIME",
                                    "rateType": "HOURLY" if p_type == "OJT" else "DAILY",
                                    "baseRate": 0,
                                    "status": "ACTIVE",
                                    "dateStarted": datetime.now(timezone.utc),
                                }
                            )
                            newly_created_accounts_count += 1
                except Exception as ex:
                    print(f"Upsert notice: {ex}")

            # 2. Save/upsert AttendanceRecord entries to the database
            for key, item in account_map.items():
                bio_id = item["biometricId"]
                rec_date = item["date"]
                am_in = item["amIn"]
                am_out = item["amOut"]
                pm_in = item["pmIn"]
                pm_out = item["pmOut"]
                actual_hours = item["actualHours"]
                late_mins = item["tardinessMinutes"]
                is_late = item["isAbnormal"]

                try:
                    person = await db.person.find_unique(where={"biometricId": bio_id})
                    if person:
                        # Parse rec_date (YYYY-MM-DD) to datetime
                        parts = rec_date.split("-")
                        rec_date_dt = datetime(int(parts[0]), int(parts[1]), int(parts[2]), tzinfo=timezone.utc)

                        def parse_time_helper(t_str):
                            if not t_str or t_str == "None":
                                return None
                            try:
                                t_parts = t_str.split(":")
                                h = int(t_parts[0])
                                m = int(t_parts[1])
                                return datetime(rec_date_dt.year, rec_date_dt.month, rec_date_dt.day, h, m, 0, tzinfo=timezone.utc)
                            except:
                                return None

                        am_in_dt = parse_time_helper(am_in)
                        am_out_dt = parse_time_helper(am_out)
                        pm_in_dt = parse_time_helper(pm_in)
                        pm_out_dt = parse_time_helper(pm_out)

                        # Check if record exists
                        existing_rec = await db.attendancerecord.find_unique(
                            where={"personId_date": {"personId": person.id, "date": rec_date_dt}}
                        )

                        record_data = {
                            "personId": person.id,
                            "date": rec_date_dt,
                            "amIn": am_in_dt,
                            "amOut": am_out_dt,
                            "pmIn": pm_in_dt,
                            "pmOut": pm_out_dt,
                            "actualHours": Decimal(str(actual_hours)),
                            "requiredHours": Decimal("8.00"),
                            "tardinessMinutes": late_mins,
                            "status": "LATE" if is_late else "PRESENT",
                            "isAbnormal": is_late,
                            "batchId": batch_id,
                            "memo": item.get("abnormalReason")
                        }

                        if existing_rec:
                            old_hours = float(existing_rec.actualHours or 0.0)
                            diff = float(actual_hours) - old_hours
                            
                            await db.attendancerecord.update(
                                where={"id": existing_rec.id},
                                data=record_data
                            )
                            
                            if person.personType == "OJT" and diff != 0:
                                latest_p = await db.person.find_unique(where={"id": person.id})
                                if latest_p:
                                    current_rendered = float(latest_p.renderedOjtHours or 0.0)
                                    new_rendered = max(0.0, current_rendered + diff)
                                    await db.person.update(
                                        where={"id": person.id},
                                        data={"renderedOjtHours": Decimal(str(round(new_rendered, 2)))}
                                    )
                        else:
                            await db.attendancerecord.create(data=record_data)
                            
                            if person.personType == "OJT" and float(actual_hours) > 0:
                                latest_p = await db.person.find_unique(where={"id": person.id})
                                if latest_p:
                                    current_rendered = float(latest_p.renderedOjtHours or 0.0)
                                    new_rendered = max(0.0, current_rendered + float(actual_hours))
                                    await db.person.update(
                                        where={"id": person.id},
                                        data={"renderedOjtHours": Decimal(str(round(new_rendered, 2)))}
                                    )

                        if is_late and person.userId:
                            from app.services.notification import dispatch_notification
                            from app.models.notification import NotificationCreate
                            from prisma.enums import NotificationPriority
                            
                            await dispatch_notification(
                                NotificationCreate(
                                    userId=person.userId,
                                    title="Attendance Exception Flagged",
                                    message=f"Your attendance record on {rec_date} has been marked abnormal: {item.get('abnormalReason')}",
                                    category="ATTENDANCE",
                                    priority=NotificationPriority.MEDIUM,
                                    actionUrl="my-attendance"
                                ),
                                db
                            )
                except Exception as ex:
                    print(f"AttendanceRecord upsert error: {ex}")

            # Dispatch notification to all HR Managers and Admins
            try:
                from app.services.notification import dispatch_notification
                from app.models.notification import NotificationCreate
                from prisma.enums import NotificationPriority, Role

                recipients = await db.user.find_many(
                    where={
                        "role": {
                            "in": [Role.SUPER_ADMIN, Role.ADMIN, Role.HR_MANAGER]
                        }
                    }
                )

                for recipient in recipients:
                    await dispatch_notification(
                        NotificationCreate(
                            userId=recipient.id,
                            title="New Biometrics Imported",
                            message=f"Biometric file '{file_name}' was successfully imported (Batch: {batch_id}). {newly_created_accounts_count} new personnel accounts registered, {len(imported_logs)} records processed, {anomalies_count} anomalies detected.",
                            category="BIOMETRIC",
                            priority=NotificationPriority.MEDIUM,
                            actionUrl="attendance"
                        ),
                        db
                    )
            except Exception as notif_err:
                print(f"Failed to dispatch biometric import notification: {notif_err}")
    except Exception as e:
        print(f"Pandas Excel parse notice: {e}")

    return AttendanceImportResponse(
        batch_id=batch_id,
        file_name=file_name,
        records_imported=len(imported_logs),
        anomalies_detected=anomalies_count,
        total_processed=len(imported_logs),
        logs=imported_logs
    )


