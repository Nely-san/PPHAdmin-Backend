# PPHAdmin Database Documentation

Complete database architecture, schema catalog, relationships, constraints, and query access patterns.

---

## 1. Engine & Connection Configuration

- **Database Engine**: MySQL 8.0 (InnoDB engine, utf8mb4 encoding, strict SQL mode).
- **Driver**: `mysqlclient` 2.2.8 (`django.db.backends.mysql`) with optional fallback to `pymysql` (1.2.0).
- **Configuration File**: [`backend/config/settings.py`](file:///backend/config/settings.py) (lines 149–180).
- **Environment Variables**:
  - `DB_NAME`: Database name (Default: `pph-2026`).
  - `DB_USER`: Database username (Default: `root`).
  - `DB_PASSWORD`: Database user password (**Required**; fails closed without hardcoded fallback).
  - `DB_HOST`: Host address (Default: `localhost`).
  - `DB_PORT`: TCP port (Default: `3306`).
- **Connection Options**: `SET time_zone='+00:00';` enforces UTC timezone synchronization.

---

## 2. Global Design Patterns & Base Model Lifecycle

All non-raw entities inherit from `BaseModel` defined in [`backend/settings/models.py`](file:///backend/settings/models.py):

```python
class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_archived = models.BooleanField(default=False, db_index=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    archived_by = models.CharField(max_length=255, null=True, blank=True)
```

### Zero Hard-Delete Archiving Lifecycle
- Standard delete operations are routed through `instance.archive(user_identifier)` to soft-delete the entity.
- Soft-archived records have `is_archived=True`, setting `archived_at` and `archived_by`.
- Restore operations (`instance.restore()`) reset flags back to `False` and clear timestamps.
- Default querysets filter `is_archived=False` across ViewSets.

---

## 3. Schema Catalog & Models Specification

### 3.1. Core & System Models

#### Table: `system_parameters` (`settings.SystemParameter`)
- **Purpose**: Dynamic runtime application parameters and calculation coefficients.
- **Fields**:
  - `id` (UUID, PK)
  - `key` (VARCHAR(100), unique, db_index)
  - `value` (LONGTEXT, stores string, number, or JSON configs)
  - `description` (TEXT, nullable)
  - `category` (VARCHAR(50), default `'GENERAL'`): Choices: `GENERAL`, `ATTENDANCE`, `PAYROLL`, `SECURITY`, `BIOMETRICS`.
  - Timestamps & archive fields via `BaseModel`.

#### Table: `settings_module_access` (`settings.ModuleAccess`)
- **Purpose**: Master navigation item registry and UI badge configuration for the frontend sidebar.
- **Fields**:
  - `id` (UUID, PK)
  - `code` (VARCHAR(100), unique, db_index): e.g. `'dashboard'`, `'employees'`.
  - `name` (VARCHAR(150))
  - `module` (VARCHAR(100)): Category group (`SYSTEM`, `HR`, `ATTENDANCE`, `PAYROLL`, `SELF_SERVICE`).
  - `icon` (VARCHAR(100), default `'fi fi-rr-apps'`)
  - `path` (VARCHAR(150), nullable): Route path.
  - `tag` (VARCHAR(50), nullable): UI pill badge.
  - `is_primary` (BOOLEAN, default `False`)
  - `display_order` (INT, default `0`)
  - `allowed_actions` (JSON, default `[]`): e.g. `["view", "add", "edit", "delete"]`.
  - Timestamps & archive fields via `BaseModel`.

#### Table: `page_permissions` (`users.PagePermission`)
- **Purpose**: Granular permission catalog for page views and functional actions.
- **Fields**:
  - `id` (UUID, PK)
  - `code` (VARCHAR(100), unique, db_index): e.g. `'employees:view'`, `'payroll:edit'`.
  - `name` (VARCHAR(255))
  - `module` (VARCHAR(100))
  - `icon` (VARCHAR(100), default `'fi fi-rr-folder'`)
  - `description` (TEXT, nullable)

#### Table: `roles` (`users.Role`)
- **Purpose**: Dynamic RBAC roles configurable by the Super Admin.
- **Fields**:
  - `id` (BIGINT, PK, auto-increment)
  - `name` (VARCHAR(100), unique)
  - `code` (VARCHAR(100), unique, db_index): e.g. `'SUPER_ADMIN'`, `'HR_ADMIN'`, `'EMPLOYEE'`, `'OJT'`.
  - `description` (TEXT, nullable)
  - `is_system_role` (BOOLEAN, default `False`): Protects baseline roles (`SUPER_ADMIN`) from deletion.
- **Relationships**:
  - `permissions` (M2M to `page_permissions` via intermediate table `roles_permissions`).

#### Table: `users` (`users.User`)
- **Purpose**: User login account with approval workflow and Triple-Lock Super Admin safeguards.
- **Fields**:
  - `id` (UUID, PK)
  - `username` (VARCHAR(150), unique, db_index)
  - `email` (VARCHAR(254), unique, nullable, db_index)
  - `password` (VARCHAR(128))
  - `role_id` (FK to `roles.id`, ON DELETE PROTECT, nullable)
  - `approval_status` (VARCHAR(20), choices: `PENDING`, `APPROVED`, `REJECTED`, default `'PENDING'`, db_index)
  - `rejection_reason` (TEXT, nullable)
  - `approved_by_id` (FK to `users.id`, ON DELETE SET NULL, nullable)
  - `approved_at` (DATETIME, nullable)
  - `is_staff` (BOOLEAN, default `False`)
  - `is_active` (BOOLEAN, default `False`)
- **Relationships**:
  - `custom_permissions` (M2M to `page_permissions` via `users_custom_permissions`).
  - Reverse 1:1 to `Person` (`person`).
- **Safeguards**:
  - Cannot create more than one active user with `role.code == 'SUPER_ADMIN'`.
  - Cannot demote, deactivate, soft-archive, or delete the Super Admin.

#### Table: `notifications` (`users.Notification`)
- **Purpose**: User-specific in-app notification alerts.
- **Fields**:
  - `id` (UUID, PK)
  - `user_id` (FK to `users.id`, ON DELETE CASCADE)
  - `title` (VARCHAR(255))
  - `message` (TEXT)
  - `is_read` (BOOLEAN, default `False`, db_index)
  - `category` (VARCHAR(50), default `'SYSTEM'`)
  - `priority` (VARCHAR(20), choices: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`, default `'MEDIUM'`)
  - `action_url` (VARCHAR(255), nullable)

#### Table: `notification_preferences` (`users.NotificationPreference`)
- **Purpose**: Opt-in/out toggles for in-app alert categories.
- **Fields**:
  - `id` (UUID, PK)
  - `user_id` (1:1 FK to `users.id`, ON DELETE CASCADE, unique)
  - `enable_in_app` (BOOLEAN, default `True`)
  - `notify_attendance` (BOOLEAN, default `True`)
  - `notify_payroll` (BOOLEAN, default `True`)
  - `notify_leave` (BOOLEAN, default `True`)

---

### 3.2. Personnel & Profiles

#### Table: `persons` (`users.Person`)
- **Purpose**: Master employee and OJT intern record.
- **Fields**:
  - `id` (UUID, PK)
  - `biometric_id` (VARCHAR(50), unique, nullable, db_index)
  - `name` (VARCHAR(255))
  - `person_type` (VARCHAR(20), choices: `EMPLOYEE`, `OJT`, default `'EMPLOYEE'`)
  - `employment_mode` (VARCHAR(20), choices: `FULL_TIME`, `PART_TIME`, `CONTRACT`, `INTERN`, default `'FULL_TIME'`)
  - `rate_type` (VARCHAR(20), choices: `DAILY`, `MONTHLY`, `HOURLY`, default `'DAILY'`)
  - `base_rate` (DECIMAL(10,2), default `0.00`)
  - `has_government_deductions` (BOOLEAN, default `True`)
  - `date_started` (DATE, nullable)
  - `date_ended` (DATE, nullable)
  - `status` (VARCHAR(20), choices: `ACTIVE`, `ARCHIVED`, `ON_LEAVE`, `COMPLETED`, default `'ACTIVE'`)
  - `user_id` (1:1 FK to `users.id`, ON DELETE SET NULL, nullable, unique)
  - `school_name` (VARCHAR(255), nullable, for OJT)
  - `coordinator_contact` (VARCHAR(255), nullable, for OJT)
  - `required_ojt_hours` (DECIMAL(10,2), default `0.00`, nullable)
  - `rendered_ojt_hours` (DECIMAL(10,2), default `0.00`, nullable)
  - `is_newly_imported` (BOOLEAN, default `False`, db_index)
  - `work_setup` (VARCHAR(20), default `'ONSITE'`, nullable)
  - `notes` (TEXT, nullable)
  - `shift_code` (VARCHAR(50), default `'DAY'`, nullable)
  - `work_days` (VARCHAR(100), default `'Mon - Fri'`, nullable)

#### Table: `person_profiles` (`users.PersonProfile`)
- **Purpose**: Extended HR, address, education, and real estate accreditation data.
- **Fields**:
  - `id` (UUID, PK)
  - `person_id` (1:1 FK to `persons.id`, ON DELETE CASCADE, unique)
  - Personal: `partners_code`, `birth_date`, `birth_place`, `citizenship`, `gender`, `civil_status`, `tin_number`, `registration_date`.
  - Address: `house_number`, `street`, `barangay`, `city_municipality`, `province_region`, `zip_code`, `landline`, `mobile_number`.
  - Education: `highest_education_attainment`, `course`, `education_school`, `year_graduated` (>= 0).
  - Accreditation: `property_status`, `accreditation_date`, `current_position`, `previous_position`, `position_time_period`, `prc_license_number`, `prc_license_time_period`, `hlurb_license_number`, `hlurb_license_time_period`, `partners_recruiter`, `executive_partner`, `team_director`, `division_broker`.

#### Table: `character_references` (`users.CharacterReference`)
- **Purpose**: Emergency/character references (maximum 5 per person).
- **Fields**:
  - `id` (UUID, PK)
  - `person_profile_id` (FK to `person_profiles.id`, ON DELETE CASCADE)
  - `name` (VARCHAR(255))
  - `relationship` (VARCHAR(100), nullable)
  - `contact_number` (VARCHAR(50))
  - `email_address` (VARCHAR(254), nullable)
  - `position_or_company` (VARCHAR(255), nullable)
  - `display_order` (SMALLINT UNSIGNED, default `0`)

---

### 3.3. Organization

#### Table: `companies` (`organization.Company`)
- **Fields**: `id` (UUID), `name` (VARCHAR(255)), `code` (VARCHAR(50), unique, nullable).

#### Table: `departments` (`organization.Department`)
- **Fields**: `id` (UUID), `company_id` (FK to `companies.id`, ON DELETE CASCADE), `name` (VARCHAR(255)), `code` (VARCHAR(50), nullable).

---

### 3.4. Scheduling & Shifts

#### Table: `shifts` (`scheduling.Shift`)
- **Fields**:
  - `id` (UUID, PK)
  - `code` (VARCHAR(50), unique, db_index)
  - `name` (VARCHAR(255))
  - `start_time` (VARCHAR(10))
  - `end_time` (VARCHAR(10))
  - `break_start_time` (VARCHAR(10), nullable)
  - `break_end_time` (VARCHAR(10), nullable)
  - `work_hours` (DECIMAL(4,2), default `8.00`)
  - `grace_period_mins` (INT, default `10`)
  - `is_flexible` (BOOLEAN, default `False`)
  - `is_field_ob` (BOOLEAN, default `False`)

#### Table: `schedules` (`scheduling.Schedule`)
- **Fields**:
  - `id` (UUID, PK)
  - `person_id` (FK to `persons.id`, ON DELETE CASCADE)
  - `shift_id` (FK to `shifts.id`, ON DELETE SET NULL, nullable)
  - `date` (DATE, db_index)
  - `schedule_type` (VARCHAR(50), choices: `REGULAR`, `REST_DAY`, `HOLIDAY`, `LEAVE`, `BUSINESS_TRIP`, default `'REGULAR'`)
  - `weekdays` (JSON, default `[]`)
  - `note` (TEXT, nullable)
- **Constraints**: `unique_together = ('person', 'date')`.

---

### 3.5. Biometrics & Attendance

#### Table: `biometric_import_batches` (`biometrics_attendance.BiometricImportBatch`)
- **Fields**:
  - `id` (UUID, PK)
  - `file_name` (VARCHAR(255))
  - `period_start` (DATE, nullable)
  - `period_end` (DATE, nullable)
  - `imported_at` (DATETIME, auto_now_add)
  - `records_imported` (INT, default `0`)
  - `anomalies_detected` (INT, default `0`)
  - `newly_created_accounts_count` (INT, default `0`)

#### Table: `biometric_logs` (`biometrics_attendance.BiometricLog`)
- **Purpose**: Raw punch times read directly from files or hardware scanners.
- **Fields**:
  - `id` (UUID, PK)
  - `person_id` (FK to `persons.id`, ON DELETE SET NULL, nullable)
  - `biometric_id` (VARCHAR(50), db_index)
  - `timestamp` (DATETIME, db_index)
  - `log_type` (VARCHAR(30), choices: `CHECK_IN`, `CHECK_OUT`, `BREAK_IN`, `BREAK_OUT`, `OVERTIME_IN`, `OVERTIME_OUT`, `UNKNOWN`)
  - `device_id` (VARCHAR(50), nullable)
  - `batch_id` (FK to `biometric_import_batches.id`, ON DELETE SET NULL, nullable)
  - `created_at` (DATETIME, auto_now_add)
- **Indexes**: `INDEX(biometric_id, timestamp)`.

#### Table: `biometric_enrollments` (`biometrics_attendance.BiometricEnrollment`)
- **Purpose**: Links physical scanner machine ID to a `Person` profile.
- **Fields**:
  - `id` (UUID, PK)
  - `person_id` (FK to `persons.id`, ON DELETE CASCADE)
  - `device_name` (VARCHAR(255), default `''`)
  - `device_id` (VARCHAR(50), default `''`, db_index)
  - `external_biometric_id` (VARCHAR(50), db_index)
  - `enrolled_at` (DATETIME, auto_now_add)
  - `enrolled_by_id` (FK to `users.id`, ON DELETE SET NULL, nullable)
  - `status` (VARCHAR(20), choices: `ENROLLED`, `REVOKED`, default `'ENROLLED'`)
  - `is_active` (BOOLEAN, default `True`, db_index)
- **Indexes**:
  - `bio_enroll_person_status_idx`: `(person_id, status, is_active)`
  - `bio_enroll_external_status_idx`: `(external_biometric_id, status)`

#### Table: `attendance_records` (`biometrics_attendance.AttendanceRecord`)
- **Purpose**: Consolidated daily timecard for calculation and payroll feeding.
- **Fields**:
  - `id` (UUID, PK)
  - `person_id` (FK to `persons.id`, ON DELETE CASCADE)
  - `date` (DATE, db_index)
  - `am_in`, `am_out`, `pm_in`, `pm_out`, `overtime_in`, `overtime_out` (DATETIME, nullable)
  - `actual_hours` (DECIMAL(6,2), default `0.00`)
  - `required_hours` (DECIMAL(6,2), default `8.00`)
  - `tardiness_minutes` (INT, default `0`)
  - `tardiness_count` (INT, default `0`)
  - `early_leave_minutes` (INT, default `0`)
  - `early_leave_count` (INT, default `0`)
  - `overtime_regular_minutes` (INT, default `0`)
  - `overtime_special_minutes` (INT, default `0`)
  - `status` (VARCHAR(30), choices: `PRESENT`, `ABSENT`, `LATE`, `HALF_DAY`, `ON_LEAVE`, `BUSINESS_TRIP`, `HOLIDAY`, `REST_DAY`, default `'PRESENT'`)
  - Flags: `is_absent`, `is_leave`, `is_business_trip`, `is_abnormal`, `is_locked`, `is_field_ob` (BOOLEAN)
  - `batch_id` (FK to `biometric_import_batches.id`, ON DELETE SET NULL, nullable)
  - `payroll_record_id` (FK to `payroll.PayrollRecord`, ON DELETE SET NULL, nullable)
  - `memo` (TEXT, nullable)
- **Constraints**:
  - `unique_together = ('person', 'date')`
  - Modification or deletion is blocked by model validation when `is_locked=True`.

#### Table: `abnormal_clockings` (`biometrics_attendance.AbnormalClocking`)
- **Purpose**: Exceptions (late punches, early outs, missing punch) flagged for HR review.
- **Fields**:
  - `id` (UUID, PK)
  - `attendance_record_id` (FK to `attendance_records.id`, ON DELETE SET NULL, nullable)
  - `person_id` (FK to `persons.id`, ON DELETE CASCADE)
  - `date` (DATE, db_index)
  - `am_in`, `am_out`, `pm_in`, `pm_out` (VARCHAR(20), nullable)
  - `tardiness_minutes`, `early_leave_minutes`, `total_abnormal_minutes` (INT)
  - `reason` (TEXT, nullable)
  - `status` (VARCHAR(30), choices: `PENDING`, `JUSTIFIED`, `RESOLVED`, `EXCUSED`, `UNEXCUSED`, default `'PENDING'`)
  - `justified_by_id` (FK to `users.id`, ON DELETE SET NULL, nullable)
  - `justified_at` (DATETIME, nullable)

#### Tables: `attendance_periods` & `attendance_summaries`
- Cutoff date boundary tracking and cumulative person summary totals.

---

### 3.6. Leaves, OB & Overtime

#### Table: `leave_ob_applications` (`leaves_ob.LeaveOBApplication`)
- **Fields**:
  - `id` (UUID, PK)
  - `person_id` (FK to `persons.id`, ON DELETE CASCADE)
  - `request_type` (VARCHAR(30), choices: `VACATION_LEAVE`, `SICK_LEAVE`, `EMERGENCY_LEAVE`, `OFFICIAL_BUSINESS`)
  - `start_date` (DATE, db_index)
  - `end_date` (DATE, db_index)
  - `total_days` (DECIMAL(4,1), default `1.0`)
  - `reason` (TEXT)
  - `location` (VARCHAR(255), nullable)
  - `status` (VARCHAR(20), choices: `PENDING`, `APPROVED`, `REJECTED`, `WITHDRAWN`, default `'PENDING'`, db_index)
  - `reviewed_by_id` (FK to `users.id`, ON DELETE SET NULL, nullable)
  - `review_remarks` (TEXT, nullable)
  - `reviewed_at` (DATETIME, nullable)

#### Table: `overtime_applications` (`leaves_ob.OvertimeApplication`)
- **Fields**:
  - `id` (UUID, PK)
  - `person_id` (FK to `persons.id`, ON DELETE CASCADE)
  - `date` (DATE, db_index)
  - `hours` (DECIMAL(4,1), default `1.0`)
  - `reason` (TEXT)
  - `status` (VARCHAR(20), choices: `PENDING`, `APPROVED`, `REJECTED`, `CANCELLED`, default `'PENDING'`, db_index)
  - `reviewed_by_id` (FK to `users.id`, ON DELETE SET NULL, nullable)
  - `review_remarks` (TEXT, nullable)
  - `reviewed_at` (DATETIME, nullable)

---

### 3.7. Payroll Processing

#### Table: `payroll_records` (`payroll.PayrollRecord`)
- **Purpose**: Consolidated cutoff payslip record.
- **Fields**:
  - `id` (UUID, PK)
  - `person_id` (FK to `persons.id`, ON DELETE CASCADE)
  - `cutoff_start` (DATE, db_index)
  - `cutoff_end` (DATE, db_index)
  - `gross_pay` (DECIMAL(12,2), default `0.00`)
  - `total_deductions` (DECIMAL(12,2), default `0.00`)
  - `net_pay` (DECIMAL(12,2), default `0.00`)
  - `arrear_balance` (DECIMAL(12,2), default `0.00`)
  - `status` (VARCHAR(20), choices: `DRAFT`, `APPROVED`, `PAID`, `LOCKED`, default `'DRAFT'`, db_index)
- **Constraints**: `unique_together = ('person', 'cutoff_start', 'cutoff_end')`.

#### Table: `payroll_items` (`payroll.PayrollItem`)
- **Purpose**: Itemized earnings and deductions.
- **Fields**:
  - `id` (UUID, PK)
  - `payroll_record_id` (FK to `payroll_records.id`, ON DELETE CASCADE)
  - `item_type` (VARCHAR(30), choices: `EARNING`, `DEDUCTION`, `ADVANCE`, `REIMBURSEMENT`, `ALLOWANCE`)
  - `description` (VARCHAR(255))
  - `amount` (DECIMAL(12,2), default `0.00`)

#### Table: `salary_rate_adjustments` (`payroll.SalaryRateAdjustment`)
- **Purpose**: Rate change history for audit trails and retroactive recalculations.
- **Fields**:
  - `id` (UUID, PK)
  - `person_id` (FK to `persons.id`, ON DELETE CASCADE)
  - `old_rate`, `new_rate` (DECIMAL(10,2))
  - `old_rate_type`, `new_rate_type` (VARCHAR(20))
  - `adjustment_type` (VARCHAR(30), choices: `PROMOTION`, `REGULARIZATION`, `ANNUAL_INCREASE`, `MERIT`, `BULK_INCREMENT`)
  - `reason` (TEXT)
  - `adjusted_by_id` (FK to `users.id`, ON DELETE SET NULL, nullable)
  - `effective_date` (DATE, db_index)

---

### 3.8. Audit & Compliance

#### Table: `audit_logs` (`audit.AuditLog`)
- **Purpose**: Automated audit trail logging JSON diffs on database record changes.
- **Fields**:
  - `id` (UUID, PK)
  - `table_name` (VARCHAR(100), db_index)
  - `record_id` (VARCHAR(255), nullable, db_index)
  - `action` (VARCHAR(50), db_index: `CREATE`, `UPDATE`, `ARCHIVE`, `RESTORE`, `IMPORT`, `RESET`, `GENERATE`, `APPROVE`, `REJECT`, `LOCK`, `PURGE`, `LINK_BIOMETRIC`, `UNLINK_BIOMETRIC`, `PROFILE_UPDATE`)
  - `old_data` (LONGTEXT, JSON encoded snapshot of fields prior to mutation)
  - `new_data` (LONGTEXT, JSON encoded snapshot of fields post mutation)
  - `changed_by` (VARCHAR(150), default `'SYSTEM'`, db_index)
  - `created_at` (DATETIME, auto_now_add, db_index)

---

## 4. Migrations & Seeding

### Migration Files Location
- `backend/users/migrations/`
- `backend/organization/migrations/`
- `backend/scheduling/migrations/`
- `backend/biometrics_attendance/migrations/`
- `backend/leaves_ob/migrations/`
- `backend/payroll/migrations/`
- `backend/audit/migrations/`
- `backend/settings/migrations/`

### Migration Commands
```bash
# Apply pending schema migrations
python manage.py migrate

# Create new migrations if models are modified
python manage.py makemigrations
```

### Seeding Logic
- **Default RBAC Catalog & Roles**: Seeded automatically during migration execution via [`backend/settings/migrations/0005_sync_active_rbac_catalog.py`](file:///backend/settings/migrations/0005_sync_active_rbac_catalog.py). Seeds `SUPER_ADMIN`, `HR_ADMIN`, `EMPLOYEE`, `OJT` and the 22 master `PagePermission` records.
- **Initial Super Admin Account**: Created via Django CLI:
  ```bash
  python manage.py createsuperuser
  ```
  *(Automatically links `SUPER_ADMIN` system role and sets `approval_status='APPROVED'`, `is_active=True`)*.
- **Default Shifts**: Can be initialized on-demand via `POST /api/shifts/seed-defaults/` (populates standard Day, Morning, and Night shift templates).

---

## 5. Table Access Patterns Mapping

| Module / Folder | Primary Tables Read | Primary Tables Written |
|---|---|---|
| `users` | `users`, `roles`, `page_permissions`, `persons`, `person_profiles`, `character_references`, `notifications` | `users`, `persons`, `person_profiles`, `character_references`, `notifications`, `notification_preferences` |
| `settings` | `system_parameters`, `settings_module_access`, `roles`, `page_permissions` | `system_parameters`, `settings_module_access`, `roles` |
| `scheduling` | `shifts`, `schedules`, `persons` | `shifts`, `schedules` |
| `biometrics_attendance` | `biometric_import_batches`, `biometric_logs`, `biometric_enrollments`, `attendance_records`, `abnormal_clockings`, `shifts`, `schedules`, `persons` | `biometric_import_batches`, `biometric_logs`, `biometric_enrollments`, `attendance_records`, `abnormal_clockings` |
| `leaves_ob` | `leave_ob_applications`, `overtime_applications`, `persons` | `leave_ob_applications`, `overtime_applications`, `schedules` (upon OB/Leave approval) |
| `payroll` | `payroll_records`, `payroll_items`, `salary_rate_adjustments`, `attendance_records`, `persons` | `payroll_records`, `payroll_items`, `salary_rate_adjustments`, `attendance_records` (sets `is_locked=True`) |
| `organization` | `companies`, `departments` | `companies`, `departments` |
| `audit` | `audit_logs` | `audit_logs` (written automatically via pre_save/post_save signals) |

---

## 6. Gotchas & Defensive Constraints

1. **Strict Single Super Admin Rule**:
   Enforced at `clean()` in `users.models.User`. Attempting to register, update, or approve a second user with `role.code == 'SUPER_ADMIN'` raises a validation error.
2. **Attendance Lock Guard**:
   Once `AttendanceRecord.is_locked` is set to `True` (triggered during `POST /api/payroll/lock/`), any subsequent call to update or delete the attendance record is rejected with `ValidationError("Attendance record is locked and cannot be modified.")`.
3. **Cascading Delete Protection**:
   `User.role` is marked `on_delete=models.PROTECT`. Active system roles cannot be deleted while assigned to any existing user account.
4. **Biometric Enrollment Uniqueness**:
   Enforced by active status checks in `clean()` and database indexes. A biometric ID cannot be enrolled to two active people simultaneously, and an employee cannot have multiple active enrollments.
5. **Character Reference Ceiling**:
   A single person profile is restricted to a maximum of 5 active character references (`clean()` on `CharacterReference`).
