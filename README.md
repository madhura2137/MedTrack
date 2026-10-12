# MedTrack 🩺

> **AWS Cloud-Enabled Healthcare Management System**  
> *Phase 1: Web Application & Clinical Workflows (Local Production-Ready Milestone)*

MedTrack is a modern, centralized healthcare management web platform connecting **Patients** and **Doctors**. The platform streamlines appointment scheduling, digital medical record tracking, and electronic diagnosis and prescription delivery through an intuitive, accessible interface featuring both **Light and Dark mode**.

---

## 🚀 Key Features

### 👤 Patient Experience
- **Interactive Health Dashboard**: Quick-glance metrics for upcoming visits, clinical reports, and unread notification alerts.
- **Doctor Discovery & Appointment Booking**: Browse licensed physicians by specialization, hospital affiliation, and years of experience. Select dates and available consultation slots with conflict-prevention validation.
- **Digital Health Profile**: Maintain records of blood group, date of birth, biological sex, allergies, emergency contacts, and ongoing conditions.
- **Official Diagnosis & Prescription Hub**: Access structured physician diagnosis reports with itemized prescription regimens ($\text{℞}$), dosage guidelines, and lifestyle recommendations. Includes one-click **Print / Save as PDF** support.
- **In-App Notification Center**: Instant updates on booking status transitions (`Pending` $\rightarrow$ `Confirmed` $\rightarrow$ `Completed`) and newly issued reports.
- **Collision-Free Rescheduling**: Easily request new consultation dates/slots or cancel with notice tracking.

### 👨‍⚕️ Doctor Clinical Portal
- **Clinical Command Center**: Review today's consultation schedule, total patient roster count, and pending visit requests.
- **Appointment Queue Management**: Filter appointments by status (`Pending`, `Confirmed`, `Completed`, `Cancelled`) and accept or decline requests with required clinical reasoning.
- **Patient Directory & Health Files**: Inspect patient medical history, pre-existing conditions, and allergy warnings prior to consultations.
- **Diagnostic Report & $\text{℞}$ Submission**: Submit formal diagnosis summaries, prescriptions, and follow-up schedules. Automatically updates appointment status to `Completed` and notifies the patient.
- **Immutable Addenda**: Append signed clinical addenda to finalized reports without overwriting the original diagnosis record.
- **Strict Privacy Isolation**: Strict access controls ensure physicians can only access records for patients with confirmed consultation relationships, backed by automated audit logging.

### 🎨 Modern Healthcare UI & Theme Engine
- **Light & Dark Mode**: One-click theme switcher in the global header with system preference auto-detection, zero-FOUC script, and `localStorage` persistence.
- **Responsive Layout**: Optimized for mobile, tablet, and desktop viewports using Bootstrap 5.3 and custom healthcare CSS variables.

---

## 🔑 Demo Access Credentials

The application is pre-seeded with sample accounts and mock clinical records for immediate demonstration:

| Role | Email | Password | Details |
| :--- | :--- | :--- | :--- |
| **Doctor** | `doctor@medtrack.com` | `Doctor@123` | Dr. Sarah Jenkins (Cardiologist, 12 yrs exp) |
| **Patient** | `patient@medtrack.com` | `Patient@123` | Madhura Patil (Age 29, Blood Group O+) |

> 💡 *Tip: The login page includes 1-click quick-fill demo buttons for instantaneous testing.*

---

## 📂 Project Structure

MedTrack follows a clean, streamlined root layout:

```text
MedTrack/
├── static/
│   ├── css/
│   │   └── style.css          # Healthcare UI stylesheet with Light & Dark themes
│   └── js/
│       └── main.js            # Theme engine, dynamic registration toggle, slot picker
├── templates/
│   ├── base.html              # Master layout with navbar, theme toggle & footer
│   ├── book_appointment.html  # Appointment scheduling form with live doctor preview
│   ├── doctor_dashboard.html  # Physician agenda, queue stats & practitioner bio
│   ├── index.html             # Landing page with doctor search bar & About MedTrack
│   ├── login.html             # Sign-in form with 1-click demo access buttons
│   ├── patient_dashboard.html # Patient metrics, next visit card & medical profile
│   ├── register.html          # Dual-role account creation (Patient / Doctor)
│   ├── search_results.html    # Specialist directory with keyword & specialty filter
│   ├── view_appointment.html # Single appointment view with printable Rx prescription
│   ├── view_appointment_doctor.html  # Doctor appointment queue & status modals
│   └── view_appointment_patient.html # Patient consultation history & reschedule modal
├── .env                       # Local environment configuration
├── app.log                    # Automated application event & audit log file
├── app.py                     # Unified Flask backend: models, datastore, auth & routes
├── requirements.txt           # Python dependencies (Flask, Werkzeug, python-dotenv)
├── test_app.py                # End-to-end automated test suite
└── README.md                  # Project documentation
```

---

## 🛠️ Quickstart Installation & Execution

### 1. Prerequisites
Ensure you have Python 3.9+ installed on your system.

### 2. Clone the Repository
```bash
git clone https://github.com/madhura2137/MedTrack.git
cd MedTrack
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Run Automated Unit Tests
Verify all authentication, role isolation, slot conflict prevention, and clinical lifecycle tests pass:
```bash
python test_app.py
```
*Expected output: `Ran 5 tests in ~0.8s — OK`*

### 5. Launch the Application
```bash
python app.py
```
Open your web browser and navigate to:
```text
http://127.0.0.1:5000
```

---

## 📝 Application Logging

All server boot events, user logins, registrations, appointment bookings, status transitions, diagnosis submissions, and patient privacy audit checks are recorded in real time to `app.log`.

Example log entries:
```text
2026-10-12 22:20:19 [INFO] medtrack: MedTrack Application initialized.
2026-10-12 22:20:19 [INFO] medtrack: User signed in: doctor@medtrack.com (doctor)
2026-10-12 22:20:20 [INFO] medtrack: Appointment apt_2f49849f status changed from Pending to Confirmed
2026-10-12 22:20:20 [INFO] medtrack: Diagnosis submitted: diag_c3365e6d for Appointment apt_2f49849f
2026-10-12 22:20:20 [INFO] medtrack: AUDIT LOG: Doctor usr_doc_001 performed 'view_appointment_details' on Patient usr_pat_001
```

---

## ☁️ Architecture & AWS Cloud Roadmap

MedTrack was engineered in Phase 1 with a modular repository pattern (`DataStore` in `app.py`). This ensures that transitioning to AWS services requires zero changes to user interface templates:

```text
                    MEDTRACK ARCHITECTURE
                             │
               ┌─────────────┴─────────────┐
               │                           │
          PATIENT UI                   DOCTOR UI
               │                           │
        ┌──────┴──────┐             ┌──────┴──────┐
        │             │             │             │
    Book Visit   View Records    Consultation  Diagnosis
        │             │             │          Report (℞)
        └──────┬──────┘             └──────┬──────┘
               │                           │
               └─────────────┬─────────────┘
                             │
                      Flask (app.py)
                             │
               ┌─────────────┴─────────────┐
               ▼                           ▼
          Local Phase 1              AWS Phase 2+
        DataStore (JSON)              Amazon DynamoDB
          Local Logging              Amazon CloudWatch
          Local Alerts               Amazon SNS
```

1. **Phase 2 — Amazon DynamoDB**: Replace local persistence with DynamoDB tables (`MedTrack_Users`, `MedTrack_Appointments`, `MedTrack_Diagnoses`, `MedTrack_Notifications`).
2. **Phase 3 — AWS IAM & Least Privilege**: Attach IAM instance profile roles to compute resources so DynamoDB and SNS are invoked securely without hardcoded credentials.
3. **Phase 4 — AWS EC2 Deployment**: Host the application on Amazon Linux 2023 with Gunicorn and an Nginx reverse proxy.
4. **Phase 5 — Amazon SNS Notifications**: Dispatch instant SMS and email notifications upon booking confirmation and prescription filing.
5. **Phase 6 — CloudWatch & Route 53**: Stream application telemetry and request latencies into CloudWatch, fronted by Route 53 domain routing.
