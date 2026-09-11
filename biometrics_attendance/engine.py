import io
import csv
import re
from datetime import datetime, date, time, timedelta
from decimal import Decimal
from django.utils import timezone
from django.db import transaction
try:
    import openpyxl
except ImportError:
    openpyxl = None

try:
    import xlrd
except ImportError:
    xlrd = None

from users.models import Person
from scheduling.models import Shift, Schedule
from biometrics_attendance.models import (
    BiometricImportBatch, BiometricLog, AttendanceRecord, AbnormalClocking
)

def make_aware_if_needed(dt):
    if dt and timezone.is_naive(dt):
        return timezone.make_aware(dt)
    return dt

def parse_time_str(val):
    if not val:
        return None
    val = str(val).strip()
    if not val or val.lower() in ('none', 'null', '-', '--:--', ''):
        return None
    formats = ['%H:%M:%S', '%H:%M', '%I:%M:%S %p', '%I:%M %p', '%I:%M%p']
    for fmt in formats:
        try:
            return datetime.strptime(val, fmt).time()
        except ValueError:
            pass
    m = re.search(r'(\d{1,2}):(\d{2})', val)
    if m:
        try:
            return time(hour=int(m.group(1)), minute=int(m.group(2)))
        except ValueError:
            pass
    return None

def parse_date_str(val):
    if not val:
        return None
    if isinstance(val, (datetime, date)):
        return val.date() if isinstance(val, datetime) else val
    val = str(val).strip()
    formats = ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d', '%d-%m-%Y', '%b %d, %Y', '%B %d, %Y']
    for fmt in formats:
        try:
            return datetime.strptime(val, fmt).date()
        except ValueError:
            pass
    m = re.search(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})', val)
    if m:
        try:
            return date(year=int(m.group(1)), month=int(m.group(2)), day=int(m.group(3)))
        except ValueError:
            pass
    return None

def extract_rows_from_file(file_obj, file_name):
    content = file_obj.read()
    file_obj.seek(0)
    lower_name = file_name.lower()
    records = []

    if lower_name.endswith('.xls') or lower_name.endswith('.html'):
        try:
            text = content.decode('utf-8', errors='ignore')
            if '<table' in text.lower() or '<tr' in text.lower():
                records = parse_html_statistic(text)
                if records:
                    return records
        except Exception:
            pass

    if lower_name.endswith('.xlsx'):
        try:
            wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
            ws = wb.active
            headers = []
            for row_idx, row in enumerate(ws.iter_rows(values_only=True)):
                if row_idx == 0:
                    headers = [str(c).strip().lower() if c is not None else '' for c in row]
                    continue
                row_dict = {}
                for h, val in zip(headers, row):
                    if h:
                        row_dict[h] = val
                if any(row_dict.values()):
                    records.append(normalize_raw_row(row_dict))
            return records
        except Exception:
            pass

    if lower_name.endswith('.xls'):
        try:
            book = xlrd.open_workbook(file_contents=content)
            sheet = book.sheet_by_index(0)
            if sheet.nrows > 0:
                headers = [str(sheet.cell_value(0, c)).strip().lower() for c in range(sheet.ncols)]
                for r in range(1, sheet.nrows):
                    row_dict = {}
                    for c in range(sheet.ncols):
                        h = headers[c]
                        if h:
                            row_dict[h] = sheet.cell_value(r, c)
                    if any(row_dict.values()):
                        records.append(normalize_raw_row(row_dict))
                return records
        except Exception:
            pass

    try:
        text = content.decode('utf-8', errors='ignore')
        reader = csv.DictReader(io.StringIO(text))
        for row in reader:
            normalized_row = {k.strip().lower(): v for k, v in row.items() if k}
            if any(normalized_row.values()):
                records.append(normalize_raw_row(normalized_row))
    except Exception:
        pass

    return records


def parse_html_statistic(html_text):
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html_text, re.DOTALL | re.IGNORECASE)
    records = []
    current_bio_id = None
    current_name = None

    for r in rows:
        cols = [re.sub(r'<[^>]+>', '', c).strip() for c in re.findall(r'<td[^>]*>(.*?)</td>', r, re.DOTALL | re.IGNORECASE)]
        if not cols:
            continue
        line = " ".join(cols)
        id_match = re.search(r'(?:No\.|ID|User ID|Enroll ID)\s*[:：]\s*(\d+)', line, re.IGNORECASE)
        name_match = re.search(r'Name\s*[:：]\s*([A-Za-z0-9\s._-]+)', line, re.IGNORECASE)
        if id_match:
            current_bio_id = id_match.group(1).strip()
        if name_match:
            current_name = name_match.group(1).strip()

        date_val = None
        for col in cols:
            d = parse_date_str(col)
            if d:
                date_val = d
                break

        if date_val and (current_bio_id or len(cols) >= 3):
            times = []
            for col in cols:
                t = parse_time_str(col)
                if t:
                    times.append(t)
            
            am_in = times[0] if len(times) > 0 else None
            am_out = times[1] if len(times) > 1 else None
            pm_in = times[2] if len(times) > 2 else None
            pm_out = times[3] if len(times) > 3 else (times[1] if len(times) == 2 and times[1].hour >= 13 else None)
            ot_in = times[4] if len(times) > 4 else None
            ot_out = times[5] if len(times) > 5 else None

            records.append({
                'biometric_id': current_bio_id or cols[0],
                'name': current_name or (cols[1] if len(cols) > 1 else 'Employee'),
                'date': date_val,
                'am_in': am_in,
                'am_out': am_out,
                'pm_in': pm_in,
                'pm_out': pm_out,
                'overtime_in': ot_in,
                'overtime_out': ot_out,
            })
    return records


def normalize_raw_row(row_dict):
    bio_id = None
    name = None
    for k in ('biometric_id', 'biometricid', 'enroll_id', 'enrollid', 'userid', 'user_id', 'id', 'pin', 'no.', 'no'):
        if k in row_dict and row_dict[k]:
            bio_id = str(row_dict[k]).replace('.0', '').strip()
            break

    for k in ('name', 'person_name', 'employee_name', 'full_name', 'employee'):
        if k in row_dict and row_dict[k]:
            name = str(row_dict[k]).strip()
            break

    date_val = None
    for k in ('date', 'work_date', 'workdate', 'attendance_date', 'att_date', 'day'):
        if k in row_dict and row_dict[k]:
            date_val = parse_date_str(row_dict[k])
            if date_val:
                break

    am_in = parse_time_str(row_dict.get('am_in') or row_dict.get('amin') or row_dict.get('clock_in') or row_dict.get('time_in') or row_dict.get('in'))
    am_out = parse_time_str(row_dict.get('am_out') or row_dict.get('amout') or row_dict.get('break_out') or row_dict.get('lunch_out'))
    pm_in = parse_time_str(row_dict.get('pm_in') or row_dict.get('pmin') or row_dict.get('break_in') or row_dict.get('lunch_in'))
    pm_out = parse_time_str(row_dict.get('pm_out') or row_dict.get('pmout') or row_dict.get('clock_out') or row_dict.get('time_out') or row_dict.get('out'))
    ot_in = parse_time_str(row_dict.get('overtime_in') or row_dict.get('otin') or row_dict.get('ot_in'))
    ot_out = parse_time_str(row_dict.get('overtime_out') or row_dict.get('otout') or row_dict.get('ot_out'))

    return {
        'biometric_id': bio_id,
        'name': name or f'Biometric User #{bio_id}' if bio_id else 'Employee',
        'date': date_val or timezone.now().date(),
        'am_in': am_in,
        'am_out': am_out,
        'pm_in': pm_in,
        'pm_out': pm_out,
        'overtime_in': ot_in,
        'overtime_out': ot_out,
    }


def compute_daily_attendance(person, record_date, am_in_t, am_out_t, pm_in_t, pm_out_t, ot_in_t, ot_out_t, shift=None):
    grace_mins = shift.grace_period_mins if shift else 10
    start_str = shift.start_time if shift else '09:00'
    end_str = shift.end_time if shift else '18:00'
    shift_start_t = parse_time_str(start_str) or time(9, 0)
    shift_end_t = parse_time_str(end_str) or time(18, 0)

    # 1. Combine date + time to make datetimes
    dt_am_in = make_aware_if_needed(datetime.combine(record_date, am_in_t)) if am_in_t else None
    dt_am_out = make_aware_if_needed(datetime.combine(record_date, am_out_t)) if am_out_t else None
    dt_pm_in = make_aware_if_needed(datetime.combine(record_date, pm_in_t)) if pm_in_t else None
    dt_pm_out = make_aware_if_needed(datetime.combine(record_date, pm_out_t)) if pm_out_t else None
    dt_ot_in = make_aware_if_needed(datetime.combine(record_date, ot_in_t)) if ot_in_t else None
    dt_ot_out = make_aware_if_needed(datetime.combine(record_date, ot_out_t)) if ot_out_t else None

    shift_start_dt = make_aware_if_needed(datetime.combine(record_date, shift_start_t))
    shift_end_dt = make_aware_if_needed(datetime.combine(record_date, shift_end_t))

    if dt_am_in and not dt_pm_out and dt_am_out and dt_am_out.time().hour >= 13:
        dt_pm_out = dt_am_out
        dt_am_out = None

    # 2. Tardiness calculation
    tardiness_mins = 0
    if dt_am_in:
        grace_limit = shift_start_dt + timedelta(minutes=grace_mins)
        if dt_am_in > grace_limit:
            tardiness_mins = int((dt_am_in - shift_start_dt).total_seconds() / 60)

    # 3. Regular Work hours calculation (effective shift start/end cap for non-flexible shifts)
    effective_am_in = dt_am_in
    if dt_am_in and shift_start_dt and dt_am_in < shift_start_dt and not (shift and shift.is_flexible):
        effective_am_in = shift_start_dt

    effective_pm_out = dt_pm_out
    if dt_pm_out and shift_end_dt and dt_pm_out > shift_end_dt and not (shift and shift.is_flexible):
        effective_pm_out = shift_end_dt

    worked_mins = 0
    if effective_am_in and effective_pm_out and effective_pm_out > effective_am_in:
        total_span = (effective_pm_out - effective_am_in).total_seconds() / 60
        if dt_am_out and dt_pm_in and dt_pm_in > dt_am_out:
            break_span = (dt_pm_in - dt_am_out).total_seconds() / 60
            worked_mins = max(0, total_span - break_span)
        else:
            if total_span >= 300:
                worked_mins = max(0, total_span - 60)
            else:
                worked_mins = total_span
    elif effective_am_in and dt_am_out and dt_am_out > effective_am_in:
        worked_mins = (dt_am_out - effective_am_in).total_seconds() / 60
    elif dt_pm_in and effective_pm_out and effective_pm_out > dt_pm_in:
        worked_mins = (effective_pm_out - dt_pm_in).total_seconds() / 60

    required_hours = shift.work_hours if shift else Decimal('8.00')
    actual_hours = round(Decimal(worked_mins) / Decimal(60), 2)
    actual_hours = min(actual_hours, required_hours)

    # 4. Early Leave (Undertime) & Overtime calculation
    early_leave_mins = 0
    if dt_pm_out and shift_end_dt and dt_pm_out < shift_end_dt and not (shift and shift.is_flexible):
        early_leave_mins = max(0, int((shift_end_dt - dt_pm_out).total_seconds() / 60))

    ot_mins = 0
    if dt_ot_in and dt_ot_out and dt_ot_out > dt_ot_in:
        ot_mins = int((dt_ot_out - dt_ot_in).total_seconds() / 60)
    elif dt_pm_out and shift_end_dt and dt_pm_out > shift_end_dt:
        ot_mins = int((dt_pm_out - shift_end_dt).total_seconds() / 60)

    # 5. Status & Anomaly Determination
    status = 'PRESENT'
    is_abnormal = False
    is_absent = False
    anomaly_reason = None

    if not dt_am_in and not dt_pm_out:
        status = 'ABSENT'
        is_absent = True
        is_abnormal = True
        actual_hours = Decimal('0.00')
        anomaly_reason = 'Unexcused absence / no biometric clocking'
    elif not dt_am_in and dt_pm_out:
        status = 'PRESENT'
        is_abnormal = True
        anomaly_reason = 'Missing AM clock-in punch'
    elif dt_am_in and not dt_pm_out:
        status = 'PRESENT'
        is_abnormal = True
        anomaly_reason = 'Missing PM clock-out punch'
    elif tardiness_mins > 0 and early_leave_mins > 0:
        status = 'LATE'
        is_abnormal = True
        anomaly_reason = f"Late arrival ({tardiness_mins} mins) & early departure ({early_leave_mins} mins)"
    elif tardiness_mins > 0:
        status = 'LATE'
        is_abnormal = True
        anomaly_reason = f"Late arrival ({tardiness_mins} mins)"
    elif early_leave_mins > 0:
        status = 'PRESENT'
        is_abnormal = True
        anomaly_reason = f"Early departure ({early_leave_mins} mins)"
    elif actual_hours < (required_hours / Decimal(2)):
        status = 'HALF_DAY'
        is_abnormal = True
        anomaly_reason = f"Half day rendered ({actual_hours} hrs)"

    return {
        'am_in': dt_am_in,
        'am_out': dt_am_out,
        'pm_in': dt_pm_in,
        'pm_out': dt_pm_out,
        'overtime_in': dt_ot_in,
        'overtime_out': dt_ot_out,
        'actual_hours': actual_hours,
        'required_hours': required_hours,
        'tardiness_minutes': tardiness_mins,
        'tardiness_count': 1 if tardiness_mins > 0 else 0,
        'early_leave_minutes': early_leave_mins,
        'early_leave_count': 1 if early_leave_mins > 0 else 0,
        'overtime_regular_minutes': ot_mins,
        'status': status,
        'is_absent': is_absent,
        'is_abnormal': is_abnormal,
        'anomaly_reason': anomaly_reason,
    }


def process_biometric_import(file_obj, file_name, user_identifier='SYSTEM'):
    raw_records = extract_rows_from_file(file_obj, file_name)
    if not raw_records:
        return {
            'success': False,
            'message': 'No valid biometric timecard rows could be parsed from the file.',
            'records_imported': 0,
        }

    dates = [r['date'] for r in raw_records if r.get('date')]
    period_start = min(dates) if dates else timezone.now().date()
    period_end = max(dates) if dates else timezone.now().date()

    with transaction.atomic():
        batch = BiometricImportBatch.objects.create(
            file_name=file_name,
            period_start=period_start,
            period_end=period_end,
            records_imported=0,
            anomalies_detected=0,
            newly_created_accounts_count=0
        )

        records_imported = 0
        anomalies_detected = 0
        new_persons_created = 0
        ojt_diffs_by_person = {}

        default_shift = Shift.objects.filter(code='DAY', is_archived=False).first()

        for raw in raw_records:
            bio_id = raw.get('biometric_id')
            rec_date = raw.get('date')
            if not rec_date:
                continue

            person = None
            if bio_id:
                person = Person.objects.filter(biometric_id=bio_id, is_archived=False).first()

            if not person and raw.get('name'):
                person = Person.objects.filter(name__iexact=raw['name'], is_archived=False).first()
                if person and not person.biometric_id and bio_id:
                    person.biometric_id = bio_id
                    person.save(update_fields=['biometric_id'])

            if not person:
                person = Person.objects.create(
                    biometric_id=bio_id,
                    name=raw.get('name') or f"Biometric #{bio_id}",
                    person_type='EMPLOYEE',
                    employment_mode='FULL_TIME',
                    rate_type='DAILY',
                    base_rate=0.00,
                    status='ACTIVE',
                    is_newly_imported=True,
                    date_started=rec_date
                )
                new_persons_created += 1

            schedule = Schedule.objects.filter(person=person, date=rec_date, is_archived=False).first()
            shift = schedule.shift if schedule and schedule.shift else default_shift

            existing_record = AttendanceRecord.objects.filter(person=person, date=rec_date).first()
            old_hours = existing_record.actual_hours if existing_record else Decimal('0.00')

            computed = compute_daily_attendance(
                person=person,
                record_date=rec_date,
                am_in_t=raw.get('am_in'),
                am_out_t=raw.get('am_out'),
                pm_in_t=raw.get('pm_in'),
                pm_out_t=raw.get('pm_out'),
                ot_in_t=raw.get('overtime_in'),
                ot_out_t=raw.get('overtime_out'),
                shift=shift
            )

            att_record, _ = AttendanceRecord.objects.update_or_create(
                person=person,
                date=rec_date,
                defaults={
                    'am_in': computed['am_in'],
                    'am_out': computed['am_out'],
                    'pm_in': computed['pm_in'],
                    'pm_out': computed['pm_out'],
                    'overtime_in': computed['overtime_in'],
                    'overtime_out': computed['overtime_out'],
                    'actual_hours': computed['actual_hours'],
                    'required_hours': computed['required_hours'],
                    'tardiness_minutes': computed['tardiness_minutes'],
                    'tardiness_count': computed['tardiness_count'],
                    'early_leave_minutes': computed['early_leave_minutes'],
                    'early_leave_count': computed['early_leave_count'],
                    'overtime_regular_minutes': computed['overtime_regular_minutes'],
                    'status': computed['status'],
                    'is_absent': computed['is_absent'],
                    'is_abnormal': computed['is_abnormal'],
                    'batch': batch,
                    'is_archived': False
                }
            )
            records_imported += 1

            hour_diff = computed['actual_hours'] - old_hours
            if hour_diff != 0 and person.person_type == 'OJT':
                ojt_diffs_by_person[person.id] = ojt_diffs_by_person.get(person.id, Decimal('0.00')) + hour_diff

            if computed['am_in']:
                BiometricLog.objects.create(
                    person=person,
                    biometric_id=bio_id or str(person.id),
                    timestamp=computed['am_in'],
                    log_type='CHECK_IN',
                    batch=batch
                )
            if computed['pm_out']:
                BiometricLog.objects.create(
                    person=person,
                    biometric_id=bio_id or str(person.id),
                    timestamp=computed['pm_out'],
                    log_type='CHECK_OUT',
                    batch=batch
                )

            if computed['is_abnormal']:
                anomalies_detected += 1
                am_in_str = computed['am_in'].strftime('%H:%M') if computed['am_in'] else None
                am_out_str = computed['am_out'].strftime('%H:%M') if computed['am_out'] else None
                pm_in_str = computed['pm_in'].strftime('%H:%M') if computed['pm_in'] else None
                pm_out_str = computed['pm_out'].strftime('%H:%M') if computed['pm_out'] else None

                AbnormalClocking.objects.update_or_create(
                    attendance_record=att_record,
                    defaults={
                        'person': person,
                        'date': rec_date,
                        'am_in': am_in_str,
                        'am_out': am_out_str,
                        'pm_in': pm_in_str,
                        'pm_out': pm_out_str,
                        'tardiness_minutes': computed['tardiness_minutes'],
                        'early_leave_minutes': computed['early_leave_minutes'],
                        'total_abnormal_minutes': computed['tardiness_minutes'] + computed['early_leave_minutes'],
                        'reason': computed.get('anomaly_reason') or 'Biometric anomaly detected',
                        'status': 'PENDING'
                    }
                )
            else:
                # If existing exception was pending but record is now normal, resolve it
                AbnormalClocking.objects.filter(attendance_record=att_record, status='PENDING').update(
                    status='RESOLVED',
                    reason='Auto-resolved by biometric log update'
                )

        for p_id, diff in ojt_diffs_by_person.items():
            p = Person.objects.filter(id=p_id).first()
            if p:
                current_rendered = p.rendered_ojt_hours or Decimal('0.00')
                p.rendered_ojt_hours = max(Decimal('0.00'), current_rendered + diff)
                p.save(update_fields=['rendered_ojt_hours'])

        batch.records_imported = records_imported
        batch.anomalies_detected = anomalies_detected
        batch.newly_created_accounts_count = new_persons_created
        batch.save()

    return {
        'success': True,
        'batch_id': str(batch.id),
        'file_name': file_name,
        'records_imported': records_imported,
        'anomalies_detected': anomalies_detected,
        'newly_created_accounts_count': new_persons_created,
        'period_start': period_start.isoformat(),
        'period_end': period_end.isoformat(),
        'message': f"Successfully processed {file_name}: {records_imported} attendance records imported ({new_persons_created} new accounts, {anomalies_detected} anomalies)."
    }
