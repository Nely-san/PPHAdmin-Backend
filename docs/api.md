# PPHAdmin API Documentation

Comprehensive API endpoint specification for the PPHAdmin Django REST Framework backend.

All endpoints are mounted under `/api/` (except `/healthz` which is also mounted at the root) and configured via [`backend/config/urls.py`](file:///backend/config/urls.py).

---

## 1. Global Standards & Conventions

- **Default Authentication**: SimpleJWT Bearer token (`Authorization: Bearer <access_token>`).
- **Default Permissions**: `rest_framework.permissions.IsAuthenticated` unless overridden with `AllowAny` or custom RBAC permission classes.
- **Throttling**:
  - Anonymous: `60/minute` (configurable via `ANON_THROTTLE_RATE`)
  - Authenticated Users: `300/minute` (configurable via `USER_THROTTLE_RATE`)
  - Login attempts (`/api/auth/login/`): `5/minute`
  - Password reset requests (`/api/auth/password-reset/request/`): `5/hour`
- **Standard Success Format**: JSON response with HTTP `200 OK`, `201 Created`, or `204 No Content`.
- **Standard Error Format**:
  - DRF Validation / Client Error: `400 Bad Request` — `{"<field>": ["<error_message>"]}` or `{"error": "<message>"}` or `{"detail": "<message>"}`
  - Authentication Error: `401 Unauthorized` — `{"detail": "Authentication credentials were not provided."}`
  - Permission Error: `403 Forbidden` — `{"detail": "You do not have permission to perform this action."}`
  - Not Found: `404 Not Found` — `{"detail": "Not found."}`
- **Audit Middleware**: Mutating requests (`POST`, `PUT`, `PATCH`, `DELETE`) across audited apps (`users`, `settings`, `payroll`, `leaves_ob`) trigger automated diff logs in `audit_logs` table via `audit.signals`.

---

## 2. Authentication & Account Lifecycle

### `POST /api/auth/login/`
- **Purpose**: Authenticates user with username & password, returning JWT access & refresh tokens and user payload.
- **Auth / Authorization**: None (`AllowAny`). Throttled at `5/minute`.
- **Request**:
  - Body (`application/json`):
    - `username` (string, required)
    - `password` (string, required)
- **Response**:
  - `200 OK`:
    ```json
    {
      "access": "jwt_token_string",
      "refresh": "refresh_token_string",
      "user": {
        "id": "uuid-string",
        "username": "admin",
        "email": "admin@example.com",
        "role": "SUPER_ADMIN",
        "approval_status": "APPROVED",
        "allowed_pages": ["dashboard", "user-management", "..."],
        "permissions": ["dashboard:view", "dashboard:edit", "..."]
      }
    }
    ```
  - `401 Unauthorized`: `{"detail": "No active account found with the given credentials"}`
  - `403 Forbidden`: `{"detail": "Your account registration is currently pending Super Admin approval."}`
- **Handler Location**: [`backend/users/views.py`](file:///backend/users/views.py) — `CustomLoginView` / `CustomTokenObtainPairSerializer`
- **Middleware / Validators**: `AnonRateThrottle`, `CustomTokenObtainPairSerializer`
- **Notes**: Blocks unapproved (`PENDING`) and `REJECTED` users. Updates `last_login`.

### `POST /api/auth/register/`
- **Purpose**: Self-service user account registration into the `PENDING` approval queue.
- **Auth / Authorization**: None (`AllowAny`).
- **Request**:
  - Body (`application/json`):
    - `username` (string, required, unique)
    - `email` (string, optional, unique)
    - `password` (string, required, min 8 chars)
    - `person_type` (string, optional: `EMPLOYEE` or `OJT`, default: `EMPLOYEE`)
    - `school_name` (string, optional, for OJT)
- **Response**:
  - `201 Created`: `{"message": "Registration successful. Your account is pending Super Admin approval.", "user_id": "uuid"}`
  - `400 Bad Request`: `{"username": ["A user with that username already exists."]}`
- **Handler Location**: [`backend/users/views.py`](file:///backend/users/views.py) — `register_view`
- **Middleware / Validators**: Password validation via Django `AUTH_PASSWORD_VALIDATORS`.
- **Notes**: Creates user with `is_active=False` and `approval_status='PENDING'`.

### `POST /api/auth/google-login/`
- **Purpose**: Authenticates or auto-provisions a user account via Google OAuth 2.0 credential ID token.
- **Auth / Authorization**: None (`AllowAny`).
- **Request**:
  - Body (`application/json`):
    - `token` (string, required, Google ID token) or `credential` (string)
- **Response**:
  - `200 OK`: `{"access": "jwt_token", "refresh": "jwt_token", "user": { ... }}`
  - `400 Bad Request`: `{"detail": "Invalid Google token or email address."}`
  - `403 Forbidden`: `{"detail": "Your Google account has been registered but is pending administrator approval."}`
- **Handler Location**: [`backend/users/views.py`](file:///backend/users/views.py) — `GoogleLoginView`
- **Middleware / Validators**: Verifies token against Google OAuth API via `requests.get('https://oauth2.googleapis.com/tokeninfo?id_token=...')`
- **Notes**: Automatically assigns `EMPLOYEE` role to newly created Google accounts with `PENDING` approval status.

### `GET /api/auth/me/`
- **Purpose**: Returns currently authenticated user's profile, role, resolved page permissions, and linked `Person` / `PersonProfile` record.
- **Auth / Authorization**: Required (`IsAuthenticated`).
- **Request**: None (reads JWT Bearer token).
- **Response**:
  - `200 OK`:
    ```json
    {
      "id": "uuid",
      "username": "sol",
      "email": "sol@example.com",
      "role": "SUPER_ADMIN",
      "role_code": "SUPER_ADMIN",
      "role_name": "Super Admin",
      "is_superuser": true,
      "approval_status": "APPROVED",
      "allowed_pages": ["dashboard", "employees", "..."],
      "allowed_permissions": ["*"],
      "person": {
        "id": "uuid",
        "name": "Sol Admin",
        "person_type": "EMPLOYEE",
        "base_rate": 1200.00
      },
      "profile": {
        "house_number": "123",
        "street": "Main St",
        "city_municipality": "Cebu City",
        "character_references": [...]
      }
    }
    ```
  - `401 Unauthorized`: `{"detail": "Given token not valid for any token type"}`
- **Handler Location**: [`backend/users/views.py`](file:///backend/users/views.py) — `current_user_view`

### `POST /api/auth/token/refresh/`
- **Purpose**: Exchanges a valid JWT refresh token for a fresh JWT access token.
- **Auth / Authorization**: None (`AllowAny`).
- **Request**:
  - Body (`application/json`):
    - `refresh` (string, required)
- **Response**:
  - `200 OK`: `{"access": "new_jwt_access_token"}`
  - `401 Unauthorized`: `{"detail": "Token is invalid or expired", "code": "token_not_valid"}`
- **Handler Location**: `rest_framework_simplejwt.views.TokenRefreshView`

### `POST /api/auth/logout/`
- **Purpose**: Invalidates current user session and blacklists refresh token if token blacklisting is active.
- **Auth / Authorization**: Required (`IsAuthenticated`).
- **Request**:
  - Body (`application/json`, optional): `{"refresh": "refresh_token"}`
- **Response**:
  - `200 OK`: `{"detail": "Successfully logged out."}`
- **Handler Location**: [`backend/users/views.py`](file:///backend/users/views.py) — `logout_view`

### `POST /api/auth/change-password/`
- **Purpose**: Allows authenticated users to change their own login password.
- **Auth / Authorization**: Required (`IsAuthenticated`).
- **Request**:
  - Body (`application/json`):
    - `old_password` (string, required)
    - `new_password` (string, required)
- **Response**:
  - `200 OK`: `{"message": "Password changed successfully."}`
  - `400 Bad Request`: `{"old_password": ["Incorrect current password."]}` or validation error
- **Handler Location**: [`backend/users/views.py`](file:///backend/users/views.py) — `ChangePasswordView`

### `POST /api/auth/password-reset/request/`
- **Purpose**: Generates password reset token and dispatches reset instructions via email.
- **Auth / Authorization**: None (`AllowAny`). Throttled at `5/hour`.
- **Request**:
  - Body (`application/json`):
    - `email` (string, required)
- **Response**:
  - `200 OK`: `{"message": "If that email address exists in our system, a password reset email has been sent."}`
- **Handler Location**: [`backend/users/views.py`](file:///backend/users/views.py) — `PasswordResetRequestView`
- **Notes**: Generates cryptographic one-time token via `PasswordResetTokenGenerator`. Emits email via Django configured mail backend.

### `POST /api/auth/password-reset/confirm/`
- **Purpose**: Verifies password reset token and updates user password.
- **Auth / Authorization**: None (`AllowAny`).
- **Request**:
  - Body (`application/json`):
    - `uid` (string, base64-encoded user ID, required)
    - `token` (string, required)
    - `new_password` (string, required)
- **Response**:
  - `200 OK`: `{"message": "Password has been successfully reset. You may now log in with your new password."}`
  - `400 Bad Request`: `{"error": "Invalid or expired password reset link."}`
- **Handler Location**: [`backend/users/views.py`](file:///backend/users/views.py) — `PasswordResetConfirmView`

---

## 3. User Management & Super Admin Approvals

Mounted via `DefaultRouter` at `/api/users/`. Handled by [`backend/users/views.py`](file:///backend/users/views.py) — `UserViewSet`.

| Method | Path | Purpose | Permissions | Request Body / Query | Success Response |
|---|---|---|---|---|---|
| `GET` | `/api/users/` | List all user accounts | `HasUserManagementViewPermission` | `?approval_status=`, `?role=`, `?search=`, `?is_archived=` | `200 OK` Array of `UserProfileSerializer` objects |
| `POST` | `/api/users/` | Create a user account | `HasUserManagementEditPermission` | `{"username", "password", "email", "role_id"}` | `201 Created` user object |
| `GET` | `/api/users/{id}/` | Retrieve single user | `HasUserManagementViewPermission` | None | `200 OK` user object |
| `PUT` / `PATCH` | `/api/users/{id}/` | Update user details | `HasUserManagementEditPermission` | `{"email", "role_id", "is_active", "custom_permissions"}` | `200 OK` updated user object |
| `DELETE` | `/api/users/{id}/` | Hard delete user | `HasUserManagementDeletePermission` | None | `204 No Content` (Blocked for `SUPER_ADMIN`) |
| `POST` | `/api/users/{id}/archive/` | Soft-archive user | `HasUserManagementDeletePermission` | None | `200 OK` `{"message": "User archived successfully."}` |
| `POST` | `/api/users/{id}/unarchive/` | Restore archived user | `HasUserManagementEditPermission` | None | `200 OK` `{"message": "User unarchived successfully."}` |
| `GET` | `/api/users/pending-approvals/` | Fetch pending user registration queue | `HasUserManagementViewPermission` | None | `200 OK` Array of pending users |
| `POST` | `/api/users/{id}/approve/` | Approve user & assign role + permissions | `HasUserManagementEditPermission` | `{"role_id" or "role_code", "page_codes": [...]}` | `200 OK` `{"message": "User approved successfully.", "user": {...}}` |
| `POST` | `/api/users/{id}/reject/` | Reject user registration | `HasUserManagementEditPermission` | `{"reason": "string"}` | `200 OK` `{"message": "User registration rejected."}` |

**Triple-Lock Super Admin Safeguards applied in `UserViewSet`**:
- Cannot delete or soft-archive the active Super Admin.
- Cannot demote Super Admin role.
- Cannot create a second active Super Admin account.

---

## 4. Personnel Directory (Employees & OJT Interns)

Mounted via `DefaultRouter` at `/api/persons/`. Handled by [`backend/users/views.py`](file:///backend/users/views.py) — `PersonViewSet`.

| Method | Path | Purpose | Permissions | Request Body / Query | Success Response |
|---|---|---|---|---|---|
| `GET` | `/api/persons/` | List personnel profiles | `HasEmployeePermission` (View) | `?status=`, `?person_type=`, `?search=`, `?is_archived=`, `?is_newly_imported=` | `200 OK` Array of `PersonDetailSerializer` |
| `POST` | `/api/persons/` | Create personnel master record | `HasEmployeePermission` (Add) | Full person payload + optional `profile` | `201 Created` person object |
| `GET` | `/api/persons/{id}/` | Retrieve employee profile & character references | `HasEmployeePermission` (View) | None | `200 OK` person object |
| `PUT` / `PATCH` | `/api/persons/{id}/` | Update employee record & profile fields | `HasEmployeePermission` (Edit) | Person fields and nested `profile` fields | `200 OK` updated person |
| `DELETE` | `/api/persons/{id}/` | Hard delete person record | `HasEmployeePermission` (Delete) | None | `204 No Content` |
| `POST` | `/api/persons/{id}/archive/` | Soft-archive person record | `HasEmployeePermission` (Delete) | None | `200 OK` `{"message": "Person archived"}` |
| `POST` | `/api/persons/{id}/unarchive/` | Restore archived person | `HasEmployeePermission` (Edit) | None | `200 OK` `{"message": "Person restored"}` |
| `POST` | `/api/persons/{id}/link-biometric/` | Enroll external biometric device ID | `HasEmployeePermission` (Edit) | `{"biometric_id": "string", "device_name": "string"}` | `200 OK` `{"message": "Biometric linked", "biometric_id": "..."}` |
| `POST` | `/api/persons/{id}/unlink-biometric/` | Revoke active biometric enrollment | `HasEmployeePermission` (Edit) | None | `200 OK` `{"message": "Biometric unlinked"}` |
| `PATCH` / `PUT` | `/api/persons/{id}/ojt-hours/` | Update required & rendered OJT internship hours | `HasEmployeePermission` (Edit) | `{"required_ojt_hours": 300, "rendered_ojt_hours": 120}` | `200 OK` `{"message": "OJT hours updated", "person": {...}}` |

---

## 5. Notifications & In-App Alerts

Mounted in [`backend/users/urls.py`](file:///backend/users/urls.py) and handled in [`backend/users/views.py`](file:///backend/users/views.py).

| Method | Path | Purpose | Permissions | Request Body / Query | Success Response |
|---|---|---|---|---|---|
| `GET` | `/api/notifications/` | List user's notifications | `IsAuthenticated` | `?unread_only=true` | `200 OK` Array of notifications |
| `GET` | `/api/notifications/unread-count/` | Get count of unread notifications | `IsAuthenticated` | None | `200 OK` `{"unread_count": 3}` |
| `POST` | `/api/notifications/read-all/` | Mark all notifications as read | `IsAuthenticated` | None | `200 OK` `{"message": "All notifications marked as read."}` |
| `POST` | `/api/notifications/{id}/read/` | Mark single notification as read | `IsAuthenticated` | None | `200 OK` `{"message": "Notification marked as read."}` |
| `GET` | `/api/notifications/preferences/` | Get user notification preferences | `IsAuthenticated` | None | `200 OK` `NotificationPreference` object |
| `PUT` / `PATCH` | `/api/notifications/preferences/` | Update notification preferences | `IsAuthenticated` | `{"enable_in_app", "notify_attendance", "notify_payroll", "notify_leave"}` | `200 OK` updated preferences |

---

## 6. Dynamic Roles, Permissions & System Parameters

Mounted in [`backend/settings/urls.py`](file:///backend/settings/urls.py) and handled in [`backend/settings/views.py`](file:///backend/settings/views.py).

| Method | Path | Purpose | Permissions | Request Body / Query | Success Response |
|---|---|---|---|---|---|
| `GET` | `/api/roles/` | List all dynamic roles | `IsAuthenticated` | `?is_archived=` | `200 OK` Array of `RoleSerializer` |
| `POST` | `/api/roles/` | Create custom role | `IsAuthenticated` (Super Admin / Admin) | `{"name", "code", "description", "permissions": [...]}` | `201 Created` role object |
| `GET` | `/api/roles/{id}/` | Retrieve single role | `IsAuthenticated` | None | `200 OK` role object |
| `PUT` / `PATCH` | `/api/roles/{id}/` | Update role permissions & details | `IsAuthenticated` | `{"name", "permissions": [...]}` | `200 OK` updated role |
| `DELETE` | `/api/roles/{id}/` | Soft-archive role | `IsAuthenticated` | None | `204 No Content` (System roles protected) |
| `GET` | `/api/permissions/` | Read-only catalog of PagePermissions | `IsAuthenticated` | None | `200 OK` Array of `PagePermissionSerializer` |
| `GET` | `/api/module-access/` | List module navigation definitions | `IsAuthenticated` | None | `200 OK` Array of `ModuleAccessSerializer` |
| `GET` | `/api/system-parameters/` | List runtime system parameters | `IsAuthenticated` | `?category=` | `200 OK` Array of `SystemParameterSerializer` |
| `POST` | `/api/system-parameters/` | Create system parameter | `IsAuthenticated` | `{"key", "value", "category", "description"}` | `201 Created` parameter |
| `PUT` / `PATCH` | `/api/system-parameters/bulk/` | Bulk update system parameters | `IsAuthenticated` | Array or Object of key-value pairs | `200 OK` `{"message": "Parameters updated successfully."}` |

---

## 7. Scheduling, Shifts & Rosters

Mounted in [`backend/scheduling/urls.py`](file:///backend/scheduling/urls.py) and handled in [`backend/scheduling/views.py`](file:///backend/scheduling/views.py).

| Method | Path | Purpose | Permissions | Request Body / Query | Success Response |
|---|---|---|---|---|---|
| `GET` | `/api/shifts/` | List configured shifts | `IsAuthenticated` | None | `200 OK` Array of `ShiftSerializer` |
| `POST` | `/api/shifts/` | Create shift template | `IsAuthenticated` | `{"code", "name", "start_time", "end_time", "work_hours", "grace_period_mins"}` | `201 Created` shift |
| `PUT` / `PATCH` | `/api/shifts/{id}/` | Update shift template | `IsAuthenticated` | Shift fields | `200 OK` updated shift |
| `DELETE` | `/api/shifts/{id}/` | Soft-archive shift | `IsAuthenticated` | None | `204 No Content` |
| `POST` | `/api/shifts/seed-defaults/` | Seed default baseline shifts | `IsAuthenticated` | None | `200 OK` `{"message": "Default shifts seeded (X new shifts created)."}` |
| `GET` | `/api/schedules/` | List assigned schedules | `IsAuthenticated` | `?person=`, `?date=`, `?date_from=`, `?date_to=` | `200 OK` Array of `ScheduleSerializer` |
| `POST` | `/api/schedules/` | Assign schedule to person for date | `IsAuthenticated` | `{"person": "uuid", "shift": "uuid", "date": "YYYY-MM-DD", "schedule_type": "REGULAR"}` | `201 Created` schedule |
| `PUT` / `PATCH` | `/api/schedules/{id}/` | Update schedule assignment | `IsAuthenticated` | Schedule fields | `200 OK` updated schedule |
| `DELETE` | `/api/schedules/{id}/` | Delete schedule assignment | `IsAuthenticated` | None | `204 No Content` |
| `POST` | `/api/schedules/batch-assign/` | Batch assign shifts across personnel & date range | `IsAuthenticated` | `{"person_ids": [...], "shift_id": "...", "start_date": "...", "end_date": "...", "weekdays": [...]}` | `200 OK` `{"message": "Schedules assigned successfully", "count": 28}` |

---

## 8. Biometric Imports & Attendance Records

Mounted in [`backend/biometrics_attendance/urls.py`](file:///backend/biometrics_attendance/urls.py) and handled in [`backend/biometrics_attendance/views.py`](file:///backend/biometrics_attendance/views.py).

| Method | Path | Purpose | Permissions | Request Body / Query | Success Response |
|---|---|---|---|---|---|
| `GET` | `/api/biometrics/` | List biometric import batches | `IsAuthenticated` | None | `200 OK` Array of `BiometricImportBatchSerializer` |
| `POST` | `/api/biometrics/upload/` | Upload `.xls`/`.xlsx`/`.csv` machine punches | `HasBiometricUploadPermission` | `multipart/form-data`: `file` | `200 OK` Batch import summary (records count, anomalies, auto-created accounts) |
| `DELETE` / `POST` | `/api/biometrics/clear-latest/` | Roll back latest biometric batch | `HasBiometricUploadPermission` | None | `200 OK` `{"message": "Latest biometric batch rolled back."}` |
| `DELETE` | `/api/biometrics/{id}/` | Delete specific biometric batch | `HasBiometricUploadPermission` | None | `204 No Content` |
| `GET` | `/api/attendance/` | List attendance records | `IsAuthenticated` | `?person=`, `?date=`, `?date_from=`, `?date_to=`, `?status=` | `200 OK` Array of `AttendanceRecordSerializer` |
| `GET` | `/api/attendance/my-attendance/` | Current user's attendance records | `IsAuthenticated` | `?date_from=`, `?date_to=` | `200 OK` Array of attendance records for calling user |
| `POST` | `/api/attendance/` | Create manual attendance record | `IsAuthenticated` | `{"person", "date", "am_in", "am_out", "pm_in", "pm_out", "status"}` | `201 Created` attendance record |
| `PUT` / `PATCH` | `/api/attendance/{id}/` | Update attendance record | `IsAuthenticated` | Time fields, status, memo | `200 OK` (Fails with `400` if record is locked) |
| `DELETE` | `/api/attendance/{id}/` | Delete attendance record | `IsAuthenticated` | None | `204 No Content` (Fails if record is locked) |
| `POST` | `/api/attendance/field-log/` | Log manual / field punch | `IsAuthenticated` | `{"punch_type": "CHECK_IN", "timestamp": "...", "notes": "..."}` | `200 OK` `{"message": "Punch recorded"}` |
| `POST` | `/api/attendance/reset/` | Wipe all attendance records | `IsAuthenticated` (Super Admin) | None | `200 OK` `{"message": "Attendance records cleared."}` |
| `GET` | `/api/attendance/exceptions/` | List abnormal clocking exceptions | `HasAttendanceExceptionPermission` (View) | `?status=`, `?person=`, `?date=` | `200 OK` Array of `AbnormalClockingSerializer` |
| `POST` | `/api/attendance/exceptions/{id}/justify/` | Justify / excuse clocking exception | `HasAttendanceExceptionPermission` (Edit) | `{"status": "JUSTIFIED" / "EXCUSED", "reason": "string"}` | `200 OK` updated exception |
| `GET` | `/api/attendance/periods/` | List attendance cutoff periods | `IsAuthenticated` | None | `200 OK` Array of `AttendancePeriodSerializer` |
| `GET` | `/api/attendance/summaries/` | List attendance period summaries | `IsAuthenticated` | `?period=`, `?person=` | `200 OK` Array of `AttendanceSummarySerializer` |

---

## 9. Leaves, Official Business (OB) & Overtime

Mounted in [`backend/leaves_ob/urls.py`](file:///backend/leaves_ob/urls.py) and handled in [`backend/leaves_ob/views.py`](file:///backend/leaves_ob/views.py).

| Method | Path | Purpose | Permissions | Request Body / Query | Success Response |
|---|---|---|---|---|---|
| `GET` | `/api/leaves-ob/` | List all leave & OB applications | `IsAuthenticated` | `?status=`, `?person=`, `?request_type=` | `200 OK` Array of `LeaveOBApplicationSerializer` |
| `POST` | `/api/leaves-ob/` | File new leave or OB request | `IsAuthenticated` | `{"request_type", "start_date", "end_date", "total_days", "reason", "location"}` | `201 Created` application |
| `GET` | `/api/leaves/my-leaves/` | List current user's leave requests | `IsAuthenticated` | None | `200 OK` Array of applications for caller |
| `POST` | `/api/leaves-ob/{id}/action/` | Approve or reject leave request | `HasLeaveApprovalPermission` | `{"action": "APPROVE" or "REJECT", "remarks": "..."}` | `200 OK` updated application |
| `POST` | `/api/leaves-ob/{id}/withdraw/` | Withdraw pending leave request | `IsAuthenticated` (Applicant only) | None | `200 OK` `{"message": "Leave application withdrawn."}` |
| `GET` | `/api/overtime/` | List all overtime requests | `IsAuthenticated` | `?status=`, `?person=`, `?date=` | `200 OK` Array of `OvertimeApplicationSerializer` |
| `POST` | `/api/overtime/` | File overtime request | `IsAuthenticated` | `{"date", "hours", "reason"}` | `201 Created` overtime application |
| `GET` | `/api/overtime/my-overtime/` | List current user's overtime requests | `IsAuthenticated` | None | `200 OK` Array of overtime applications for caller |
| `POST` | `/api/overtime/{id}/action/` | Approve or reject overtime | `HasLeaveApprovalPermission` | `{"action": "APPROVE" or "REJECT", "remarks": "..."}` | `200 OK` updated overtime |
| `POST` | `/api/overtime/{id}/cancel/` | Cancel pending overtime | `IsAuthenticated` (Applicant only) | None | `200 OK` `{"message": "Overtime request cancelled."}` |

---

## 10. Payroll Processing & Salary Adjustments

Mounted in [`backend/payroll/urls.py`](file:///backend/payroll/urls.py) and handled in [`backend/payroll/views.py`](file:///backend/payroll/views.py).

| Method | Path | Purpose | Permissions | Request Body / Query | Success Response |
|---|---|---|---|---|---|
| `GET` | `/api/payroll/` | List payroll records | `IsAuthenticated` | `?status=`, `?cutoff_start=`, `?cutoff_end=`, `?person=` | `200 OK` Array of `PayrollRecordSerializer` with nested `items` |
| `POST` | `/api/payroll/calculate/` | Trigger automated payroll calculation for cutoff | `IsAuthenticated` | `{"cutoff_start": "YYYY-MM-DD", "cutoff_end": "YYYY-MM-DD", "person_ids": [...]}` | `200 OK` `{"message": "Payroll computed successfully", "records_count": 14}` |
| `POST` | `/api/payroll/lock/` | Lock & finalize payroll cutoff | `IsAuthenticated` | `{"cutoff_start": "YYYY-MM-DD", "cutoff_end": "YYYY-MM-DD"}` | `200 OK` `{"message": "Payroll records and related attendance records locked."}` |
| `GET` | `/api/payroll/my-payslips/` | Get latest payslip for current user | `IsAuthenticated` | None | `200 OK` Single `PayrollRecordSerializer` object |
| `GET` | `/api/payroll/my-payslips/history/` | Get historical payslips for current user | `IsAuthenticated` | None | `200 OK` Array of historical `PayrollRecordSerializer` objects |
| `GET` | `/api/payroll/rate-adjustments/` | List salary rate change audit history | `IsAuthenticated` | `?person=` | `200 OK` Array of `SalaryRateAdjustmentSerializer` |
| `POST` | `/api/payroll/rate-adjustments/adjust/` | Log single salary base rate adjustment | `IsAuthenticated` | `{"person_id", "new_rate", "new_rate_type", "effective_date", "reason", "adjustment_type"}` | `200 OK` `{"message": "Rate adjusted", "record": {...}}` |
| `POST` | `/api/payroll/rate-adjustments/bulk-adjust/` | Bulk adjust base rates by department/type | `IsAuthenticated` | `{"person_ids": [...], "adjustment_amount": 50, "effective_date": "...", "reason": "..."}` | `200 OK` `{"message": "Bulk rate adjustment applied", "count": 10}` |

---

## 11. Organization (Companies & Departments)

Mounted in [`backend/organization/urls.py`](file:///backend/organization/urls.py) and handled in [`backend/organization/views.py`](file:///backend/organization/views.py).

| Method | Path | Purpose | Permissions | Request Body / Query | Success Response |
|---|---|---|---|---|---|
| `GET` | `/api/companies/` | List corporate company entities | `IsAuthenticated` | None | `200 OK` Array of `CompanySerializer` |
| `POST` | `/api/companies/` | Create company entity | `IsAuthenticated` | `{"name": "...", "code": "..."}` | `201 Created` company |
| `PUT` / `PATCH` | `/api/companies/{id}/` | Update company entity | `IsAuthenticated` | Company fields | `200 OK` updated company |
| `DELETE` | `/api/companies/{id}/` | Soft-archive company | `IsAuthenticated` | None | `204 No Content` |
| `GET` | `/api/companies/org-tree/` | Hierarchical company and department tree | `IsAuthenticated` | None | `200 OK` Array of companies with nested `departments` |
| `GET` | `/api/departments/` | List departments across entities | `IsAuthenticated` | `?company=` | `200 OK` Array of `DepartmentSerializer` |
| `POST` | `/api/departments/` | Create department under company | `IsAuthenticated` | `{"company": "uuid", "name": "...", "code": "..."}` | `201 Created` department |

---

## 12. Audit Logs & System Health

| Method | Path | Purpose | Permissions | Request Body / Query | Success Response |
|---|---|---|---|---|---|
| `GET` | `/healthz` & `/api/health/` | Server heartbeat and database connectivity check | None (`AllowAny`) | None | `200 OK` `{"status": "ok", "database": "connected"}` |
| `GET` | `/api/audit-logs/` | Query mutation audit logs & before/after JSON diffs | `IsAuthenticated` | `?table_name=`, `?action=`, `?changed_by=`, `?search=` | `200 OK` Array of `AuditLogSerializer` |

---

## 13. Endpoint Status Matrix (Dead / Unused / Frontend-Missing)

| Endpoint | Backend Defined | Called from Frontend (`api.ts`) | Status / Notes |
|---|---|---|---|
| `/api/auth/login/` | Yes | Yes | Active |
| `/api/auth/register/` | Yes | Yes | Active |
| `/api/auth/google-login/` | Yes | Yes | Active |
| `/api/auth/me/` | Yes | Yes | Active |
| `/api/auth/logout/` | Yes | Yes | Active |
| `/api/auth/token/refresh/` | Yes | Yes | Active |
| `/api/users/` | Yes | Yes | Active |
| `/api/persons/` | Yes | Yes | Active |
| `/api/notifications/` | Yes | Yes | Active |
| `/api/shifts/` | Yes | Indirectly via schedule | Active |
| `/api/shifts/seed-defaults/` | Yes | No | **Defined but unused in UI** (available for manual CLI / bootstrap seeding) |
| `/api/companies/` | Yes | No | **Defined but unused in UI** (Companies currently hardcoded or mocked in frontend components; backend ready for multi-entity rollout) |
| `/api/attendance/periods/` | Yes | No | **Defined but unused in UI** (Periods managed internally during payroll batching) |
| `/api/attendance/summaries/` | Yes | No | **Defined but unused in UI** (Summaries aggregated on demand) |
| `/api/payroll/base-rates/adjust/` | Yes | Indirectly via Person updates | **Partially unused** (Direct person patch used instead of separate adjust endpoint) |
