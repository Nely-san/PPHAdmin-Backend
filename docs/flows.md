# PPHAdmin System Architecture & Workflow Diagrams

Visual flows and architectural interaction models for PPHAdmin.

---

## 1. High-Level System Architecture

```mermaid
flowchart TD
    subgraph Client["Frontend Client (React 19 + TypeScript + Vite)"]
        UI["React SPA Components (Vite :5173)"]
        AuthCtx["AuthContext / tokenStorage"]
        ApiFetch["apiFetch Interceptor (Silent JWT Refresh)"]
        UI --> AuthCtx
        UI --> ApiFetch
    end

    subgraph Gateway["Reverse Proxy / Server Boundary"]
        Proxy["Vite Dev Proxy / Nginx (/api/*)"]
        ApiFetch --> Proxy
    end

    subgraph Backend["Django 5.0 REST Framework Backend (:8000)"]
        URLRouter["Root URL Router (config/urls.py)"]
        Middleware["Django Middleware Stack\n(CorsMiddleware, AuditMiddleware)"]
        JWTAuth["SimpleJWT Authentication & Throttle Guards"]
        
        Proxy --> URLRouter
        URLRouter --> Middleware
        Middleware --> JWTAuth

        subgraph Modules["Domain Applications"]
            UsersApp["users (Auth, Accounts, Profiles)"]
            BioApp["biometrics_attendance (Ingestion & Engine)"]
            SchedApp["scheduling (Shifts & Rosters)"]
            LeavesApp["leaves_ob (Leave & Overtime)"]
            PayrollApp["payroll (Pay Engine & Arrears)"]
            SettingsApp["settings (Dynamic RBAC & Params)"]
            AuditApp["audit (Diff & Trail Logging)"]
        end

        JWTAuth --> UsersApp
        JWTAuth --> BioApp
        JWTAuth --> SchedApp
        JWTAuth --> LeavesApp
        JWTAuth --> PayrollApp
        JWTApp --> SettingsApp
    end

    subgraph DataStore["Data Layer"]
        MySQL[("MySQL 8.0 Database (pph-2026)\nInnoDB UTF8mb4")]
        UsersApp --> MySQL
        BioApp --> MySQL
        SchedApp --> MySQL
        LeavesApp --> MySQL
        PayrollApp --> MySQL
        SettingsApp --> MySQL
        AuditApp --> MySQL
    end

    subgraph External["External Integrations"]
        GoogleOAuth["Google Cloud OAuth 2.0 API"]
        EmailSMTP["SMTP / Console Mail Server"]
        BioDevice["Biometric Hardware Files (07Statistic.xls)"]
        
        UsersApp -->|Token verification| GoogleOAuth
        UsersApp -->|Password reset tokens| EmailSMTP
        BioApp -->|File upload parsing| BioDevice
    end
```

---

## 2. API Request Lifecycle

Representative sequence of an authenticated mutating API request (e.g. Updating an Employee record or Filing a Leave):

```mermaid
sequenceDiagram
    autonumber
    actor Dev as User / Browser
    participant Comp as React Component (EmployeesPage.tsx)
    participant Api as apiFetch / api.ts
    participant Mid as AuditMiddleware (audit/middleware.py)
    participant View as PersonViewSet (users/views.py)
    participant Perm as HasEmployeePermission
    participant Serial as PersonDetailSerializer
    participant Model as Person & PersonProfile (users/models.py)
    participant Signal as audit.signals (post_save)
    participant DB as MySQL Database

    Dev->>Comp: Click "Save Employee Profile"
    Comp->>Api: updatePerson(id, payload)
    Note over Api: Injects Authorization: Bearer <access_token>
    Api->>Mid: HTTP PATCH /api/persons/{id}/
    Note over Mid: Captures client IP & authenticated username in thread-local
    Mid->>View: Dispatch to partial_update()
    View->>Perm: Check user role & module permissions
    alt Permission Denied
        Perm-->>Dev: 403 Forbidden
    else Permission Granted
        View->>Serial: Validate payload constraints
        Serial->>Model: Save updated fields
        Model->>DB: UPDATE persons, person_profiles
        DB-->>Model: Success
        Model->>Signal: Trigger post_save hook
        Signal->>DB: INSERT INTO audit_logs (JSON diff, actor, record_id)
        View-->>Api: 200 OK + Updated Person JSON
        Api-->>Comp: Resolves Promise
        Comp-->>Dev: Update UI & Display Success Toast
    end
```

---

## 3. Authentication & JWT Token Lifecycle

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Login as LoginPage.tsx
    participant Api as api.ts (loginUser)
    participant Backend as CustomLoginView (users/views.py)
    participant DB as User Table
    participant Storage as localStorage (tokenStorage)
    participant SessionLock as SessionLockModal.tsx

    User->>Login: Submit credentials (username & password)
    Login->>Api: POST /api/auth/login/
    Api->>Backend: Process TokenObtainPair
    Backend->>DB: SELECT * FROM users WHERE username = ...
    alt Status != APPROVED
        Backend-->>Login: 403 Forbidden ("Registration pending approval")
    else Password Invalid
        Backend-->>Login: 401 Unauthorized
    else Valid & Approved
        Backend-->>Api: 200 OK (access_token, refresh_token, user_payload)
        Api->>Storage: Store access_token & refresh_token
        Api->>Login: Set AuthContext state
        Login->>User: Redirect to /dashboard
    end

    Note over User, SessionLock: After 15 minutes of user inactivity:
    SessionLock->>User: Display Session Lock Screen (Shield active session)
    User->>SessionLock: Re-enter password or Google login
    SessionLock->>Api: Re-verify credentials
    SessionLock->>User: Dismiss lock screen & resume work
```

---

## 4. Key Business Domain Flows

### 4.1. Biometric Import & Anomaly Processing

```mermaid
flowchart TD
    Start([Upload Biometric Spreadsheet: .xls / .xlsx / .csv]) --> UploadAPI["POST /api/biometrics/upload/<br/>(BiometricImportViewSet.upload_file)"]
    UploadAPI --> ParseEngine["Biometric Engine Parser<br/>(biometrics_attendance/engine.py)"]
    ParseEngine --> CreateBatch["INSERT BiometricImportBatch Record"]
    
    ParseEngine --> InspectRows{"Row Loop:<br/>Biometric ID & Timestamps"}
    InspectRows --> CheckEnroll{"Is Biometric ID<br/>Enrolled to Person?"}
    
    CheckEnroll -->|No| AutoReg["Auto-Create Person Profile<br/>(is_newly_imported = True)<br/>Stage in Newly Imported Queue"]
    CheckEnroll -->|Yes| LinkPerson["Match Existing Person Record"]
    
    AutoReg --> InsertPunches["INSERT Raw BiometricLog Records"]
    LinkPerson --> InsertPunches
    
    InsertPunches --> Aggregate["Calculate Daily Logs (AM/PM In/Out)<br/>Calculate Tardiness & Overtime"]
    Aggregate --> AnomalyCheck{"Punch Missing or<br/>Late Arrival?"}
    
    AnomalyCheck -->|Yes| GenAnomaly["Create AbnormalClocking<br/>(Status: PENDING)"]
    AnomalyCheck -->|No| GenAtt["Create / Update AttendanceRecord"]
    GenAnomaly --> GenAtt
    
    GenAtt --> DoneBatch["Update Batch Statistics<br/>(records_count, anomalies_detected)"]
    DoneBatch --> End([Return Batch Processing Summary])
```

---

### 4.2. Salary & Payroll Cutoff Generation

```mermaid
flowchart TD
    A([HR Admin triggers Payroll Run]) --> B["POST /api/payroll/calculate/<br/>Select Cutoff Window (e.g. 5th or 20th)"]
    B --> C["Fetch Active Persons & Rates<br/>(Daily / Monthly / Hourly)"]
    C --> D["Fetch Approved AttendanceRecords<br/>Within Cutoff Dates"]
    
    D --> E["Compute Basic Pay = (Days Worked * Base Rate)"]
    E --> F["Deduct Tardiness & Absent Days"]
    F --> G["Add Approved Overtime & Holiday Multipliers"]
    G --> H{"Government Deductions<br/>has_government_deductions?"}
    
    H -->|Yes| I["Calculate SSS, PhilHealth, Pag-IBIG<br/>Insert PayrollItem (DEDUCTION)"]
    H -->|No| J["Skip Statutory Deductions"]
    
    I --> K["Add Non-taxable Reimbursements / Advances"]
    J --> K
    K --> L["Calculate Net Pay = Gross - Total Deductions"]
    L --> M["INSERT Draft PayrollRecord & PayrollItems"]
    
    M --> N([Review in Payroll UI])
    N --> LockBtn{"Payroll Officer<br/>Clicks 'Lock Cutoff'"}
    LockBtn --> LockAPI["POST /api/payroll/lock/"]
    LockAPI --> FinalizeRecords["Set PayrollRecord.status = 'LOCKED'"]
    FinalizeRecords --> LockAttendance["UPDATE AttendanceRecord SET is_locked = True"]
    LockAttendance --> Complete([Cutoff Immutable & Archived])
```

---

### 4.3. Leave & Official Business (OB) Filing & Approval

```mermaid
sequenceDiagram
    autonumber
    actor Emp as Employee / Intern
    participant UI as Self-Service Portal (MyLeavesPage.tsx)
    participant LeavesAPI as POST /api/leaves-ob/
    participant DB as MySQL DB
    actor HR as HR Admin / Supervisor
    participant HRUI as Attendance & Approvals (AttendancePage.tsx)
    participant ActionAPI as POST /api/leaves-ob/{id}/action/

    Emp->>UI: Fill Leave/OB form (Dates, Type, Reason)
    UI->>LeavesAPI: Submit application
    LeavesAPI->>DB: INSERT INTO leave_ob_applications (status='PENDING')
    LeavesAPI-->>UI: 201 Created (Pending HR review)
    
    Note over HR, HRUI: HR opens Approvals tab
    HRUI->>DB: Query PENDING leave applications
    HR->>HRUI: Click "Approve Application"
    HRUI->>ActionAPI: {"action": "APPROVE", "remarks": "Approved"}
    ActionAPI->>DB: UPDATE leave_ob_applications SET status='APPROVED'
    ActionAPI->>DB: INSERT / UPDATE schedules (schedule_type='LEAVE' or 'BUSINESS_TRIP')
    ActionAPI->>DB: INSERT INTO notifications (Alert employee)
    ActionAPI-->>HRUI: 200 OK
    HRUI-->>HR: Display updated status badge
```

---

## 5. Core Data Entity Relationships

```mermaid
erDiagram
    users ||--o| persons : "links 1:1"
    roles ||--o{ users : "assigned to"
    roles }|--|{ page_permissions : "grants"
    
    companies ||--o{ departments : "contains"
    
    persons ||--o| person_profiles : "extends 1:1"
    person_profiles ||--o{ character_references : "has up to 5"
    
    persons ||--o{ schedules : "assigned"
    shifts ||--o{ schedules : "defines"
    
    persons ||--o{ biometric_enrollments : "registered"
    biometric_import_batches ||--o{ biometric_logs : "contains"
    persons ||--o{ biometric_logs : "scanned by"
    
    persons ||--o{ attendance_records : "generates daily"
    biometric_import_batches ||--o{ attendance_records : "imported from"
    attendance_records ||--o{ abnormal_clockings : "flags exceptions"
    
    persons ||--o{ leave_ob_applications : "files"
    persons ||--o{ overtime_applications : "submits"
    
    persons ||--o{ payroll_records : "receives cutoff"
    payroll_records ||--o{ payroll_items : "itemizes"
    payroll_records ||--o{ attendance_records : "locks & references"
    
    persons ||--o{ salary_rate_adjustments : "history"
    users ||--o{ notifications : "receives"
```
