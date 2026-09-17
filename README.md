# MedTrack 🩺

> **AWS Cloud-Enabled Healthcare Management System**  
> *Phase 1: Web Application & Clinical Workflows (Local Production-Ready Milestone)*

MedTrack is a centralized healthcare management web platform connecting **Patients** and **Doctors**. The platform streamlines appointment scheduling, digital medical record tracking, and electronic diagnosis/prescription delivery through a modern, responsive interface.

---

## 🚀 Key Features

### 👤 Patient Experience
- **Interactive Health Dashboard**: Summary of upcoming appointments, diagnosis reports, and real-time notification alerts.
- **Doctor Discovery & Appointment Booking**: Browse licensed physicians by medical specialization, hospital affiliation, and clinical experience. Select appointment dates and time slots with instant confirmation tracking.
- **Digital Medical History**: Record and update blood group, age, gender, known drug/food allergies, emergency contacts, and chronic health conditions.
- **Clinical Diagnosis & Prescription Hub**: Access official physician diagnosis sheets with itemized prescription regimens ($\text{℞}$), dosage guidelines, and lifestyle instructions with one-click print/PDF export.
- **In-App Notifications**: Real-time alerts for booking status updates (Pending $\rightarrow$ Confirmed $\rightarrow$ Completed) and new diagnostic reports.
- **Account & Security Management**: Update personal profile details and securely rotate passwords.

### 👨‍⚕️ Doctor Portal
- **Clinical Command Dashboard**: View today's consultation schedule, total patient roster count, and pending booking requests.
- **Appointment Queue Management**: Filter appointments by status (Pending, Confirmed, Completed) and accept or decline incoming visit requests.
- **Patient Directory & Health Files**: Review patient profiles, pre-existing conditions, allergy warnings, and past visit logs prior to consultations.
- **Diagnostic Report & $\text{℞}$ Submission**: Formulate comprehensive diagnoses, itemized prescription regimens, and physician guidance notes with automated status progression to `Completed` and automatic notification dispatch to the patient.
- **Notifications & Profile Settings**: Monitor new patient bookings, manage medical license credentials, and update hospital affiliations.

---

## 🔑 Demo Access Credentials

The application is pre-seeded with sample accounts and mock clinical records for immediate demonstration:

| Role | Email | Password | Details |
|---|---|---|---|
| **Doctor** | `doctor@medtrack.com` | `Doctor@123` | Dr. Sarah Jenkins (Cardiologist, 12 yrs exp) |
| **Patient** | `patient@medtrack.com` | `Patient@123` | Madhura Patil (Age 24, Blood Group O+) |

> 💡 *Note: The login screen also contains 1-click quick fill buttons for both demo roles.*

---

## 📂 Project Structure

```text
MedTrack/
├── app/
│   ├── __init__.py            # Flask app factory and global template context
│   ├── auth.py                # Authentication, registration & role decorators
│   ├── data_store.py          # Thread-safe JSON repository layer (DynamoDB precursor)
│   ├── doctor_routes.py       # Doctor portal endpoints (dashboard, diagnose, patients)
│   ├── models.py              # Application schemas (User, Patient, Doctor, Appointment, ...)
│   ├── patient_routes.py      # Patient portal endpoints (dashboard, book, history, reports)
│   ├── public_routes.py       # Public pages (Landing, About MedTrack)
│   ├── static/
│   │   ├── css/
│   │   │   └── style.css      # Healthcare UI theme, custom variables & styling
│   │   └── js/
│   │       └── main.js        # Dynamic role switcher, slot picker, auto-dismiss alerts
│   └── templates/
│       ├── base.html          # Public layout
│       ├── portal_base.html   # Portal layout with responsive sidebar & topbar
│       ├── auth/              # Login and registration templates
│       ├── doctor/            # Doctor clinical management templates
│       ├── patient/           # Patient consultation & records templates
│       └── public/            # Landing and About templates
├── data/
│   └── medtrack_db.json       # Auto-seeded local database
├── config.py                  # Environment and session configuration
├── requirements.txt           # Python dependencies (Flask, Werkzeug, python-dotenv)
├── run.py                     # Local server entry point
├── test_app.py                # End-to-end automated unit test suite
└── README.md                  # Project documentation
```

---

## 🛠️ Quickstart Installation & Execution

### 1. Prerequisites
Ensure you have Python 3.9+ installed on your system.

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run Automated Tests
Verify that all authentication, role isolation, and appointment lifecycle flows pass:
```bash
python test_app.py
```

### 4. Start the Application
```bash
python run.py
```
Open your browser and navigate to:
```text
http://127.0.0.1:5000
```

---

## ☁️ Architecture & AWS Cloud Migration Roadmap

MedTrack was intentionally architected in Phase 1 with a clean **Repository Layer** (`app/data_store.py`). This guarantees that moving to AWS requires **zero changes to UI templates or route handlers**:

1. **Phase 2 — Amazon DynamoDB**:
   - Replace JSON reads/writes in `data_store.py` with `boto3.resource('dynamodb')` interacting with tables `MedTrack_Users`, `MedTrack_Appointments`, `MedTrack_Diagnoses`, and `MedTrack_Notifications`.
2. **Phase 3 — AWS IAM & Security**:
   - Attach IAM EC2 instance profile roles with least-privilege policies to communicate with DynamoDB and SNS without hardcoding any API keys.
3. **Phase 4 — Production EC2 Deployment**:
   - Deploy on Amazon Linux 2023 with Gunicorn WSGI workers fronted by an Nginx reverse proxy.
4. **Phase 5 — Amazon SNS Notifications**:
   - Connect diagnosis submissions and appointment confirmations to Amazon Simple Notification Service (SNS) to deliver SMS or email alerts to patients.
5. **Phase 6 — CloudWatch & Route 53**:
   - Set up CloudWatch Logs and application latency metrics, alongside Route 53 DNS routing.
