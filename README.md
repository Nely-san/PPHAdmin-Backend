# PPHAdmin — Backend API Application

Backend REST API service for PPHAdmin (Employee Records, Biometrics Ingestion, Shift Rosters & Payroll System), built with Python 3.11+, Django 5.0.6, and Django REST Framework (DRF 3.15+).

---

## 📖 Navigation & Deeper Documentation Links

- [Frontend Documentation (frontend/README.md)](file:///frontend/README.md)
- [Complete API Specification (docs/api.md)](file:///docs/api.md)
- [Database Schema & Models Catalog (docs/database.md)](file:///docs/database.md)
- [System Architecture & Flow Diagrams (docs/flows.md)](file:///docs/flows.md)

---

## 1. Quickstart & Local Setup

### Prerequisites
- Python 3.11+
- MySQL 8.0 server running locally or remotely
- Virtual environment tool (`venv`)

### Installation Steps
```bash
# 1. Navigate to the backend directory
cd backend

# 2. Create and activate a Python virtual environment
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
copy .env.example .env
# Edit .env and supply your MySQL DB_PASSWORD and SECRET_KEY

# 5. Apply database migrations
python manage.py migrate

# 6. Create the initial Super Admin account (enforces single super admin policy)
python manage.py createsuperuser

# 7. Start the local development server (port 8000)
python manage.py runserver
```

### Running Test Suites
```bash
# Run all backend unit and integration tests
python manage.py test

# Run tests for specific domain apps
python manage.py test users
python manage.py test biometrics_attendance
python manage.py test payroll
python manage.py test leaves_ob
python manage.py test scheduling
python manage.py test settings
python manage.py test audit
python manage.py test organization
```

---

## 2. Directory Tree Map

```text
backend/
├── config/                     # Django project configuration, settings, health, urls, wsgi/asgi
├── core/                       # Dormant/legacy empty module directory
├── users/                      # Authentication, User accounts, Person master records, Profiles, Notifications
│   └── migrations/             # Schema migrations for User, Person, PersonProfile, CharacterReference, Notification
├── organization/               # Company entities and departmental hierarchy
│   └── migrations/             # Schema migrations for Company, Department
├── scheduling/                 # Shifts definitions, work hour policies, employee rosters
│   └── migrations/             # Schema migrations for Shift, Schedule
├── biometrics_attendance/      # Multi-sheet spreadsheet ingestion, raw punches, timecards, anomaly engine
│   └── migrations/             # Schema migrations for Biometric batches, AttendanceRecord, AbnormalClocking
├── leaves_ob/                  # Leave of absence (VL/SL/EL), official business (OB) & overtime approvals
│   └── migrations/             # Schema migrations for LeaveOBApplication, OvertimeApplication
├── payroll/                    # Semi-monthly payroll computation engine, items, locking, rate adjustments
│   └── migrations/             # Schema migrations for PayrollRecord, PayrollItem, SalaryRateAdjustment
├── audit/                      # Automated JSON diff audit trail capturing actor, IP, timestamp
│   └── migrations/             # Schema migrations for AuditLog
├── settings/                   # Base abstract models, system parameters, dynamic navigation registry
│   └── migrations/             # Migrations and automated RBAC data seeders
├── manage.py                   # Django CLI management entry point
└── requirements.txt            # Python dependencies manifest
```

---

## 3. Part 1 — Per-Folder Documentation

### `## backend/`
- **Purpose**: Root directory of the Django project hosting configuration, dependencies, environment templates, and operational run scripts.
- **Key files**:
  - `manage.py`: Django command-line utility for executing administrative tasks, migrations, and servers.
  - `requirements.txt`: Pinned Python dependencies (`Django`, `djangorestframework`, `rest_framework_simplejwt`, `mysqlclient`, etc.).
  - `.env.example`: Safe configuration template for local and production deployments.
  - `.env`: Active local environment variables file (git-ignored).
- **Responsibilities**: Dependency resolution, process bootstrapping, runtime configuration loading.
- **Dependencies & interactions**: Acts as the root execution context for all child domain apps.
- **Important details / gotchas**: `settings.py` automatically attempts to load `.env` from both `backend/` and project root if present. `DB_PASSWORD` is strictly required without fallback.
- **How to run/test**: `python manage.py runserver`, `python manage.py test`.

---

### `## backend/config/`
- **Purpose**: Central Django project settings and global URL routing configuration.
- **Key files**:
  - `settings.py`: Project settings, database connections, JWT configs, CORS whitelist, throttling, and email backends.
  - `urls.py`: Master URL dispatcher aggregating route tables from all 8 domain apps and health endpoints.
  - `health.py`: Heartbeat monitoring handler (`/healthz`, `/api/health/`) verifying database connectivity.
  - `asgi.py` & `wsgi.py`: ASGI/WSGI gateway entry points for production application servers.
- **Responsibilities**: App bootstrapping, security policy enforcement, middleware pipeline definition, root routing.
- **Dependencies & interactions**: Imports URL configurations from `users`, `settings`, `audit`, `scheduling`, `biometrics_attendance`, `leaves_ob`, `payroll`, `organization`.
- **Important details / gotchas**: Fails closed if `DB_PASSWORD` or production `DJANGO_SECRET_KEY` is omitted. JWT access token lifetime defaults to 24 hours.

---

### `## backend/core/`
- **Purpose**: Dormant/legacy package directory containing no active source files.
- **Key files**: None (contains only `__pycache__` artifacts).
- **Responsibilities**: None.
- **Dependencies & interactions**: Not registered in `INSTALLED_APPS` or referenced in `config/urls.py`.
- **Important details / gotchas**: Maintained for legacy compatibility; safe to leave as-is or remove.

---

### `## backend/users/`
- **Purpose**: User authentication, account lifecycle, Triple-Lock Super Admin policy, personnel directories (`Person`), extended profiles (`PersonProfile`), and in-app notifications.
- **Key files**:
  - `models.py`: Defines `User`, `Person`, `PersonProfile`, `CharacterReference`, `Notification`, `NotificationPreference`.
  - `views.py`: `CustomLoginView`, `register_view`, `GoogleLoginView`, `current_user_view`, `UserViewSet`, `PersonViewSet`.
  - `serializers.py`: Serializers for user registration, tokens, employee details, and nested profile updates.
  - `urls.py`: URL mappings for auth, user management, person directory, and notifications.
  - `tests.py`: Unit and permission tests covering single Super Admin safeguards and CRUD operations.
- **Responsibilities**: JWT token issuance, approval workflow (`PENDING` -> `APPROVED`), password reset tokens, employee master records.
- **Dependencies & interactions**: Depends on `settings.models.BaseModel` and `users.PagePermission`. Used across all apps to reference user and personnel identities.
- **Important details / gotchas**: Triple-Lock safeguards prevent deleting, demoting, or soft-archiving the Super Admin account or creating a duplicate Super Admin. Post-save signals automatically create a `Person` profile when a `User` is created.
- **How to run/test**: `python manage.py test users`.

---

### `## backend/users/migrations/`
- **Purpose**: Database schema version history for `users` models.
- **Key files**:
  - `0001_initial.py`: Initial schema creation for users, persons, and profiles.
  - Subsequent migrations: Incremental schema modifications for government deduction flags, profile extensions, and character reference limits.
- **Responsibilities**: Synchronizing `users` model state with MySQL schema.
- **Dependencies & interactions**: Executed by `python manage.py migrate`.

---

### `## backend/organization/`
- **Purpose**: Multi-entity corporate organization structure (Companies and Departments).
- **Key files**:
  - `models.py`: Defines `Company` and `Department` models.
  - `views.py`: `CompanyViewSet` (with `org_tree` and nested `departments_for_company` actions) and `DepartmentViewSet`.
  - `serializers.py`: Serializers for corporate entities and departments.
  - `urls.py`: Routes for `/api/companies/` and `/api/departments/`.
  - `tests.py`: Unit tests for company and department CRUD.
- **Responsibilities**: Corporate entity hierarchy modeling, branch groupings.
- **Dependencies & interactions**: Inherits `BaseModel` from `settings.models`.
- **Important details / gotchas**: Soft-deleting a Company automatically cascades to child records.
- **How to run/test**: `python manage.py test organization`.

---

### `## backend/organization/migrations/`
- **Purpose**: Database schema migrations for `organization` app models.
- **Key files**: `0001_initial.py`.
- **Responsibilities**: Creates `companies` and `departments` tables.

---

### `## backend/scheduling/`
- **Purpose**: Shift templates, work hour configurations, grace periods, and daily employee roster schedules.
- **Key files**:
  - `models.py`: Defines `Shift` and `Schedule`.
  - `views.py`: `ShiftViewSet` (with `seed-defaults` action) and `ScheduleViewSet` (with `batch-assign` action).
  - `serializers.py`: Serializers for shifts and calendar assignments.
  - `urls.py`: Routes for `/api/shifts/` and `/api/schedules/`.
  - `tests.py`: Roster generation and shift validation test suites.
- **Responsibilities**: Shift policy definitions, calendar scheduling, batch shift assignment.
- **Dependencies & interactions**: Foreign key to `users.Person`. Consumed by `biometrics_attendance` to compute expected work hours.
- **Important details / gotchas**: `schedules` enforces `unique_together = ('person', 'date')`. `seed-defaults` seeds Day, Morning, and Night baseline templates.
- **How to run/test**: `python manage.py test scheduling`.

---

### `## backend/scheduling/migrations/`
- **Purpose**: Database schema migrations for `scheduling` app models.
- **Key files**: `0001_initial.py`.
- **Responsibilities**: Creates `shifts` and `schedules` tables.

---

### `## backend/biometrics_attendance/`
- **Purpose**: Biometric scanner timecard ingestion (`.xls`/`.xlsx`/`.csv`), raw log parsing, daily attendance consolidation, and anomaly detection.
- **Key files**:
  - `engine.py`: Multi-sheet parser (handles device exports e.g. `07Statistic.xls`, `Logs`, `Abnormal`), daily punch grouping, and work hour calculation.
  - `models.py`: Defines `BiometricImportBatch`, `BiometricLog`, `BiometricEnrollment`, `AttendanceRecord`, `AbnormalClocking`, `AttendancePeriod`, `AttendanceSummary`.
  - `views.py`: `BiometricImportViewSet` (`upload`, `clear-latest`), `AttendanceRecordViewSet` (`my-attendance`, `field-log`), `AbnormalClockingViewSet` (`justify`).
  - `serializers.py`: Serializers for batches, daily timecards, and clocking exceptions.
  - `urls.py`: URL dispatching for attendance endpoints.
  - `tests.py`: Comprehensive test suite for biometric file uploads and attendance calculations.
- **Responsibilities**: Punch extraction, auto-registration of unknown biometric IDs, tardiness/overtime calculation, exception review.
- **Dependencies & interactions**: Depends on `users.Person` and `scheduling.Shift`. Provides locked attendance records to `payroll`.
- **Important details / gotchas**: `AttendanceRecord` cannot be edited or deleted once `is_locked=True`. Newly imported biometric IDs without existing profiles are auto-staged with `is_newly_imported=True`.
- **How to run/test**: `python manage.py test biometrics_attendance`.

---

### `## backend/biometrics_attendance/migrations/`
- **Purpose**: Database schema migrations for biometric and attendance entities.
- **Key files**: `0001_initial.py` through active migrations.
- **Responsibilities**: Creates tables and indexes (e.g. `bio_enroll_person_status_idx`).

---

### `## backend/leaves_ob/`
- **Purpose**: Employee leave of absence (VL, SL, EL), official business trip (OB), and overtime application workflows.
- **Key files**:
  - `models.py`: Defines `LeaveOBApplication` and `OvertimeApplication`.
  - `views.py`: `LeaveOBViewSet` (`my-leaves`, `action`, `withdraw`) and `OvertimeApplicationViewSet` (`my-overtime`, `action`, `cancel`).
  - `serializers.py`: Serializers for applications and review remarks.
  - `urls.py`: URL endpoints for leave and overtime requests.
  - `tests.py`: Workflow tests for leave filing, supervisor approvals, and withdrawals.
- **Responsibilities**: Request validation, status transitions (`PENDING`, `APPROVED`, `REJECTED`, `WITHDRAWN`), notification dispatching.
- **Dependencies & interactions**: Upon leave/OB approval, creates or updates matching `scheduling.Schedule` records.
- **Important details / gotchas**: Employees can only withdraw/cancel their own pending requests. Approvals require `HasLeaveApprovalPermission`.
- **How to run/test**: `python manage.py test leaves_ob`.

---

### `## backend/leaves_ob/migrations/`
- **Purpose**: Database schema migrations for leaves and overtime models.
- **Key files**: `0001_initial.py`.
- **Responsibilities**: Creates `leave_ob_applications` and `overtime_applications` tables.

---

### `## backend/payroll/`
- **Purpose**: Automated semi-monthly payroll engine, itemized earnings/deductions, cutoff finalization, and salary rate adjustments.
- **Key files**:
  - `models.py`: Defines `PayrollRecord`, `PayrollItem`, `SalaryRateAdjustment`.
  - `views.py`: `PayrollRecordViewSet` (`calculate`, `lock`, `my-payslips`, `my-payslips/history`) and `SalaryRateAdjustmentViewSet`.
  - `serializers.py`: Serializers for payroll records and salary rate adjustments.
  - `urls.py`: Routes for payroll calculations and payslip self-service.
  - `tests.py`: Payroll calculation formulas, statutory deduction toggles, and locking test suites.
- **Responsibilities**: Gross/net pay calculation, tardiness deductions, overtime multipliers, cutoff locking.
- **Dependencies & interactions**: Reads `AttendanceRecord` and `Person.base_rate`. Locks corresponding `AttendanceRecord` entries upon payroll finalization.
- **Important details / gotchas**: `lock` sets `PayrollRecord.status = 'LOCKED'` and sets `AttendanceRecord.is_locked = True`, preventing further tampering.
- **How to run/test**: `python manage.py test payroll`.

---

### `## backend/payroll/migrations/`
- **Purpose**: Database schema migrations for payroll records and rate adjustments.
- **Key files**: `0001_initial.py`.
- **Responsibilities**: Creates `payroll_records`, `payroll_items`, and `salary_rate_adjustments` tables.

---

### `## backend/audit/`
- **Purpose**: Automated security and change audit trail capturing user identity, client IP, action type, and before/after JSON diffs.
- **Key files**:
  - `models.py`: Defines `AuditLog`.
  - `middleware.py`: Captures client IP and authenticated username into thread-local context.
  - `signals.py`: `pre_save`, `post_save`, and `post_delete` signals generating JSON snapshots and recording diffs.
  - `views.py` & `serializers.py`: Read-only ViewSet and serializer for querying audit trail entries.
  - `urls.py`: Mounts `/api/audit-logs/`.
  - `tests.py`: Audit signal firing and diff serialization tests.
- **Responsibilities**: Compliance auditing, immutable mutation logging, sensitive data redaction (passwords, tokens).
- **Dependencies & interactions**: Automatically audits models in `users`, `settings`, `payroll`, `leaves_ob`.
- **Important details / gotchas**: Passwords, secrets, and auth tokens are strictly replaced with `***REDACTED***` prior to JSON serialization.
- **How to run/test**: `python manage.py test audit`.

---

### `## backend/audit/migrations/`
- **Purpose**: Database schema migrations for audit logging.
- **Key files**: `0001_initial.py`.
- **Responsibilities**: Creates `audit_logs` table with indexes on `table_name`, `record_id`, `action`, `changed_by`, `created_at`.

---

### `## backend/settings/`
- **Purpose**: Abstract base models (`BaseModel`), dynamic system parameters, dynamic role permissions, and sidebar navigation registries.
- **Key files**:
  - `models.py`: Defines `BaseModel` (UUID, timestamps, soft-delete archive), `SystemParameter`, `ModuleAccess`.
  - `views.py`: `RoleViewSet`, `ModuleAccessViewSet`, `PagePermissionViewSet`, `SystemParameterViewSet`.
  - `serializers.py`: Serializers for system parameters, dynamic roles, and permission assignments.
  - `urls.py`: Routes for system parameters, roles, module access, and permissions.
  - `tests.py`: System parameter and role CRUD tests.
- **Responsibilities**: Soft-delete lifecycle implementation, runtime configuration storage, dynamic RBAC catalog management.
- **Dependencies & interactions**: `BaseModel` is inherited by nearly every table in the system.
- **Important details / gotchas**: `RoleViewSet` blocks modification or deletion of `SUPER_ADMIN` system role.
- **How to run/test**: `python manage.py test settings`.

---

### `## backend/settings/migrations/`
- **Purpose**: Schema migrations and automated data seeders for the RBAC permissions catalog.
- **Key files**:
  - `0001_initial.py` through `0003_auditlog.py`: Table definitions for parameters and module access.
  - `0005_sync_active_rbac_catalog.py`: Data migration that populates the 22 master `PagePermission` records and initial system roles (`SUPER_ADMIN`, `HR_ADMIN`, `EMPLOYEE`, `OJT`).
  - `0006_consolidate_reports_module_access.py` & `0007_cleanup_obsolete_report_pagepermissions.py`: Migrations aligning navigation slugs with active frontend tabs.
- **Responsibilities**: Automatic RBAC seeding and schema upgrades.

---

## 4. Part 4 — Environment Variables Reference

| Variable Name | Required? | Purpose | Safe Example Value | Where Read | Default Value | Notes |
|---|---|---|---|---|---|---|
| `DJANGO_SECRET_KEY` | **Yes (Prod)** | Cryptographic signing key for sessions and tokens | `django-insecure-dev-only-fallback-key` | `backend/config/settings.py` (L36) | None | Sensitive secret. Server raises `ImproperlyConfigured` in production if missing. |
| `SECRET_KEY` | No | Legacy fallback for `DJANGO_SECRET_KEY` in debug | `django-insecure-dev-only-fallback-key` | `backend/config/settings.py` (L39) | `django-insecure-dev-only-fallback-key` | Sensitive secret. |
| `DEBUG` | No | Toggles Django debug mode | `True` | `backend/config/settings.py` (L33) | `True` | Boolean (`true`, `1`, `t`). Must be `False` in production. |
| `ALLOWED_HOSTS` | **Yes (Prod)** | Permitted hostnames / IPs | `localhost,127.0.0.1` | `backend/config/settings.py` (L43) | `['*']` when DEBUG=True | Comma-delimited list. |
| `DB_NAME` | No | MySQL database name | `pph-2026` | `backend/config/settings.py` (L152) | `pph-2026` | Database schema name. |
| `DB_USER` | No | MySQL database username | `root` | `backend/config/settings.py` (L153) | `root` | Database account. |
| `DB_PASSWORD` | **Yes** | MySQL database password | `<set-in-secrets-manager>` | `backend/config/settings.py` (L158) | None | Sensitive secret. Server raises `ImproperlyConfigured` if unset. |
| `DB_HOST` | No | MySQL database host | `localhost` | `backend/config/settings.py` (L154) | `localhost` | Hostname or IP. |
| `DB_PORT` | No | MySQL database port | `3306` | `backend/config/settings.py` (L155) | `3306` | Port integer string. |
| `ANON_THROTTLE_RATE` | No | Rate limit for anonymous requests | `60/minute` | `backend/config/settings.py` (L99) | `60/minute` | Format: `count/period`. |
| `USER_THROTTLE_RATE` | No | Rate limit for authenticated users | `300/minute` | `backend/config/settings.py` (L100) | `300/minute` | Format: `count/period`. |
| `EMAIL_BACKEND` | No | Django email handler class | `django.core.mail.backends.console.EmailBackend` | `backend/config/settings.py` (L107) | Console backend | Use SMTP backend in production. |
| `DEFAULT_FROM_EMAIL` | No | Sender email header for system mail | `PPHAdmin Security <noreply@pphadmin.local>` | `backend/config/settings.py` (L108) | `PPHAdmin Security <...>` | Sender address string. |
| `CORS_ALLOWED_ORIGINS` | No | Allowed frontend web origins | `http://localhost:5173,http://localhost:8080` | `backend/config/settings.py` (L127) | `[]` (Allows all if DEBUG) | Comma-separated URL list. |
| `GOOGLE_CLIENT_ID` | No | Google OAuth 2.0 Web Client ID | `YOUR_CLIENT_ID.apps.googleusercontent.com` | `backend/config/settings.py` (L240) | Placeholder string | Public identifier. Must match frontend. |
| `GOOGLE_CLIENT_SECRET`| No | Google OAuth 2.0 Client Secret | `<set-in-secrets-manager>` | `backend/config/settings.py` (L241) | Placeholder string | Sensitive secret. |

### Configuration Callouts
- **Read in code but missing from initial `.env.example`**: `DJANGO_SECRET_KEY`, `ANON_THROTTLE_RATE`, `USER_THROTTLE_RATE`, `EMAIL_BACKEND`, `DEFAULT_FROM_EMAIL`, `CORS_ALLOWED_ORIGINS`. (Now added to `backend/.env.example`).
- **Dead config**: `USE_SQLITE` was commented in older template files; backend code exclusively connects to MySQL.
- **Shared variables**: `GOOGLE_CLIENT_ID` (backend) and `VITE_GOOGLE_CLIENT_ID` (frontend) must be identical for Google OAuth token validation.

---

## 5. Part 6 — Onboarding Summary

### Where to Start as a New Backend Developer
1. [`backend/config/settings.py`](file:///backend/config/settings.py) & [`backend/config/urls.py`](file:///backend/config/urls.py) — Understand database setup, JWT settings, throttling, and routing layout.
2. [`backend/settings/models.py`](file:///backend/settings/models.py) — Learn the `BaseModel` soft-delete lifecycle and audit timestamps.
3. [`backend/users/models.py`](file:///backend/users/models.py) & [`backend/users/views.py`](file:///backend/users/views.py) — Review `User`, `Person`, and Triple-Lock Super Admin safeguards.
4. [`backend/biometrics_attendance/engine.py`](file:///backend/biometrics_attendance/engine.py) — Learn how machine spreadsheets (`07Statistic.xls`) are parsed into punches and daily timecards.
5. [`backend/payroll/views.py`](file:///backend/payroll/views.py) — Review how attendance records feed the cutoff calculation and locking pipeline.
6. [`backend/audit/signals.py`](file:///backend/audit/signals.py) — Understand automated mutation auditing and diff logging.

### Request → Response Cheat Sheet

| Business Action | Frontend Component | API Endpoint | View / Handler | Models Involved | Primary Database Tables |
|---|---|---|---|---|---|
| User Login | `LoginPage.tsx` | `POST /api/auth/login/` | `CustomLoginView` | `User` | `users` |
| View Profile | `ProfilePage.tsx` | `GET /api/auth/me/` | `current_user_view` | `User`, `Person`, `PersonProfile` | `users`, `persons`, `person_profiles` |
| Update Employee | `EmployeesPage.tsx` | `PATCH /api/persons/{id}/` | `PersonViewSet.update` | `Person`, `PersonProfile` | `persons`, `person_profiles`, `audit_logs` |
| Upload Biometrics | `AttendancePage.tsx` | `POST /api/biometrics/upload/` | `BiometricImportViewSet.upload_file` | `BiometricImportBatch`, `BiometricLog`, `AttendanceRecord` | `biometric_import_batches`, `biometric_logs`, `attendance_records` |
| File Leave / OB | `MyLeavesPage.tsx` | `POST /api/leaves-ob/` | `LeaveOBViewSet.create` | `LeaveOBApplication` | `leave_ob_applications` |
| Approve Leave | `AttendancePage.tsx` | `POST /api/leaves-ob/{id}/action/` | `LeaveOBViewSet.process_action` | `LeaveOBApplication`, `Schedule` | `leave_ob_applications`, `schedules` |
| Run Payroll | `PayrollPage.tsx` | `POST /api/payroll/calculate/` | `PayrollRecordViewSet.calculate_cutoff` | `PayrollRecord`, `PayrollItem`, `AttendanceRecord` | `payroll_records`, `payroll_items`, `attendance_records` |
| Lock Payroll | `PayrollPage.tsx` | `POST /api/payroll/lock/` | `PayrollRecordViewSet.lock_cutoff` | `PayrollRecord`, `AttendanceRecord` | `payroll_records`, `attendance_records` |
| Edit Roles & RBAC | `RolesPermissionsPage.tsx` | `PUT /api/roles/{id}/` | `RoleViewSet.update` | `Role`, `PagePermission` | `roles`, `roles_permissions` |
| View Audit Logs | `AuditLogsPage.tsx` | `GET /api/audit-logs/` | `AuditLogViewSet.list` | `AuditLog` | `audit_logs` |
