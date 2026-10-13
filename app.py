import os
import sys
import json
import uuid
import logging
import threading
from datetime import datetime, timedelta
from functools import wraps
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional

from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, jsonify, abort
)
from werkzeug.security import generate_password_hash, check_password_hash
import boto3

# -----------------------------------------------------------------------------
# 1. Environment & Logging Setup
# -----------------------------------------------------------------------------
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Simple .env loader if file exists
env_path = os.path.join(BASE_DIR, '.env')
if os.path.exists(env_path):
    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, val = line.split('=', 1)
                    os.environ.setdefault(key.strip(), val.strip())
    except Exception:
        pass

LOG_FILE = os.path.join(BASE_DIR, 'app.log')
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] medtrack: %(message)s'
)
logger = logging.getLogger("medtrack")
logger.info("MedTrack Application initialized.")

# -----------------------------------------------------------------------------
# 2. Configuration
# -----------------------------------------------------------------------------
class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'medtrack-super-secret-key-2026-prod-ready')
    DATA_DIR = os.path.join(BASE_DIR, 'data')
    DATA_FILE = os.environ.get('DATA_FILE', os.path.join(DATA_DIR, 'medtrack_db.json'))
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    APP_NAME = "MedTrack"
    APP_TAGLINE = "Cloud-enabled healthcare management made simple."

# ------------ AWS CONNECTION ------------
# It is better to rely on EC2 IAM Roles than hardcoded regions if possible
REGION = os.environ.get("AWS_REGION", "ap-south-1")

try:
    dynamodb = boto3.resource('dynamodb', region_name=REGION)
    sns = boto3.client('sns', region_name=REGION)

    users_table = dynamodb.Table(os.environ.get('DYNAMODB_USERS_TABLE', 'MedTrack-Users'))
    appointments_table = dynamodb.Table(os.environ.get('DYNAMODB_APPOINTMENTS_TABLE', 'MedTrack-Appointments'))
    diagnoses_table = dynamodb.Table(os.environ.get('DYNAMODB_DIAGNOSES_TABLE', 'MedTrack-Diagnoses'))
    notifications_table = dynamodb.Table(os.environ.get('DYNAMODB_NOTIFICATIONS_TABLE', 'MedTrack-Notifications'))
except Exception as _aws_init_err:
    dynamodb = None
    sns = None
    users_table = None
    appointments_table = None
    diagnoses_table = None
    notifications_table = None

SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN", "arn:aws:sns:us-east-1:970547343422:MedTrackNotifications:a8483fa2-3222-42dd-bd21-cf1bb758b932")
USE_AWS = os.environ.get("USE_AWS", "false").lower() in ["true", "1", "yes"]

def publish_sns_alert(subject: str, message: str):
    """Dispatches real-time notification alert via AWS SNS if configured."""
    if sns and SNS_TOPIC_ARN:
        try:
            response = sns.publish(
                TopicArn=SNS_TOPIC_ARN,
                Subject=subject[:100],
                Message=message
            )
            logger.info(f"AWS SNS Alert dispatched: {subject}")
            return response
        except Exception as err:
            logger.warning(f"AWS SNS alert dispatch skipped / pending credentials: {err}")
    return None

# -----------------------------------------------------------------------------
# 3. Domain Models & Helpers
# -----------------------------------------------------------------------------
def generate_id(prefix: str = "") -> str:
    short_uuid = uuid.uuid4().hex[:8]
    return f"{prefix}_{short_uuid}" if prefix else short_uuid

def current_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

@dataclass
class User:
    id: str
    name: str
    email: str
    phone: str
    role: str  # 'patient' or 'doctor'
    password_hash: str
    created_at: str = field(default_factory=current_timestamp)

    def to_dict(self):
        return asdict(self)

@dataclass
class PatientProfile:
    user_id: str
    date_of_birth: str = "2000-01-01"
    age: int = 25
    gender: str = "Not Specified"
    blood_group: str = "Unknown"
    conditions: str = ""
    medications: str = ""
    medical_history: str = ""
    emergency_contact: str = ""
    allergies: str = "None reported"

    def to_dict(self):
        return asdict(self)

@dataclass
class DoctorProfile:
    user_id: str
    specialization: str
    experience: int  # in years
    license_no: str
    hospital: str = "MedTrack Central Hospital"
    bio: str = ""
    available_days: List[str] = field(default_factory=lambda: ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])
    time_slots: List[str] = field(default_factory=lambda: [
        "09:00 AM", "10:00 AM", "11:30 AM", "02:00 PM", "03:30 PM", "04:30 PM"
    ])

    def to_dict(self):
        return asdict(self)

@dataclass
class Appointment:
    id: str
    patient_id: str
    doctor_id: str
    date: str  # YYYY-MM-DD
    time_slot: str
    reason: str  # Mandatory, max 500 chars
    status: str = "Pending"  # 'Pending', 'Confirmed', 'Rejected', 'Completed', 'Cancelled'
    status_reason: str = ""  # Mandatory when rejecting or cancelling per FR-05
    notes: str = ""
    created_at: str = field(default_factory=current_timestamp)

    def to_dict(self):
        return asdict(self)

@dataclass
class DiagnosisReport:
    id: str
    appointment_id: str
    patient_id: str
    doctor_id: str
    diagnosis: str  # Mandatory
    prescription: str = ""  # Optional per FR-08
    additional_notes: str = ""  # Optional per FR-08
    follow_up_date: str = ""  # Optional per FR-08
    is_read: bool = False  # Track unread indicator per FR-09
    addenda: List[Dict[str, str]] = field(default_factory=list)  # Immutable corrections per FR-08
    created_at: str = field(default_factory=current_timestamp)

    def to_dict(self):
        return asdict(self)

@dataclass
class Notification:
    id: str
    user_id: str
    title: str
    message: str
    type: str = "info"  # 'appointment', 'diagnosis', 'alert', 'info'
    related_id: str = ""  # Related record reference per FR-10
    is_read: bool = False
    created_at: str = field(default_factory=current_timestamp)

    def to_dict(self):
        return asdict(self)

@dataclass
class AccessLog:
    id: str
    doctor_id: str
    patient_id: str
    action: str  # 'view_patient_history', 'view_diagnosis'
    timestamp: str = field(default_factory=current_timestamp)

    def to_dict(self):
        return asdict(self)

# -----------------------------------------------------------------------------
# 4. Thread-Safe DataStore
# -----------------------------------------------------------------------------
class DataStore:
    """Thread-safe JSON repository mimicking future DynamoDB tables."""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(DataStore, cls).__new__(cls)
                cls._instance._init_storage()
            return cls._instance

    def _init_storage(self):
        self.file_path = Config.DATA_FILE
        self.data_lock = threading.Lock()
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        if not os.path.exists(self.file_path) or os.path.getsize(self.file_path) == 0:
            self._seed_initial_data()
        else:
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if "access_logs" not in data:
                        data["access_logs"] = {}
                        self._write_data(data)
            except Exception:
                self._seed_initial_data()

    def _read_data(self) -> Dict[str, Any]:
        with self.data_lock:
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return {
                    "users": {},
                    "patients": {},
                    "doctors": {},
                    "appointments": {},
                    "diagnoses": {},
                    "notifications": {},
                    "access_logs": {}
                }

    def _write_data(self, data: Dict[str, Any]):
        with self.data_lock:
            temp_path = self.file_path + ".tmp"
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            if os.path.exists(self.file_path):
                os.replace(temp_path, self.file_path)
            else:
                os.rename(temp_path, self.file_path)

    def _seed_initial_data(self):
        """Pre-populates database with demo doctor, patient, appointments, and records."""
        now = datetime.now()
        tomorrow_str = (now + timedelta(days=1)).strftime("%Y-%m-%d")
        yesterday_str = (now - timedelta(days=5)).strftime("%Y-%m-%d")

        doc1_id = "usr_doc_001"
        doc2_id = "usr_doc_002"
        pat1_id = "usr_pat_001"

        users = {
            doc1_id: {
                "id": doc1_id,
                "name": "Dr. Sarah Jenkins",
                "email": "doctor@medtrack.com",
                "phone": "+1 (555) 234-5678",
                "role": "doctor",
                "password_hash": generate_password_hash("Doctor@123"),
                "created_at": current_timestamp()
            },
            doc2_id: {
                "id": doc2_id,
                "name": "Dr. Robert Chen",
                "email": "chen@medtrack.com",
                "phone": "+1 (555) 876-5432",
                "role": "doctor",
                "password_hash": generate_password_hash("Doctor@123"),
                "created_at": current_timestamp()
            },
            pat1_id: {
                "id": pat1_id,
                "name": "Madhura Patil",
                "email": "patient@medtrack.com",
                "phone": "+1 (555) 987-6543",
                "role": "patient",
                "password_hash": generate_password_hash("Patient@123"),
                "created_at": current_timestamp()
            }
        }

        doctors = {
            doc1_id: {
                "user_id": doc1_id,
                "specialization": "Cardiology",
                "experience": 12,
                "license_no": "MD-CARD-89213",
                "hospital": "MedTrack Central Hospital",
                "bio": "Senior Consultant Cardiologist specializing in preventive heart health and advanced diagnostics.",
                "available_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
                "time_slots": ["09:00 AM", "10:00 AM", "11:30 AM", "02:00 PM", "03:30 PM", "04:30 PM"]
            },
            doc2_id: {
                "user_id": doc2_id,
                "specialization": "Neurology",
                "experience": 9,
                "license_no": "MD-NEUR-45129",
                "hospital": "City Neuroscience Clinic",
                "bio": "Consultant Neurologist focusing on cognitive health, migraines, and neuro-restorative care.",
                "available_days": ["Monday", "Tuesday", "Thursday"],
                "time_slots": ["10:00 AM", "11:30 AM", "02:00 PM", "03:30 PM"]
            }
        }

        patients = {
            pat1_id: {
                "user_id": pat1_id,
                "date_of_birth": "1997-08-14",
                "age": 29,
                "gender": "Female",
                "blood_group": "O+",
                "conditions": "Mild Hypertension, Seasonal Allergies",
                "medications": "Amlodipine 5mg (daily)",
                "medical_history": "Mild Hypertension diagnosed in 2024. Regular cardio workouts.",
                "emergency_contact": "Rohan Patil (+1 555-900-1122)",
                "allergies": "Penicillin (moderate rash)"
            }
        }

        appt1_id = "apt_001_seed"
        appt2_id = "apt_002_seed"
        diag1_id = "diag_001_seed"

        appointments = {
            appt1_id: {
                "id": appt1_id,
                "patient_id": pat1_id,
                "doctor_id": doc1_id,
                "date": tomorrow_str,
                "time_slot": "10:00 AM",
                "reason": "Routine cardiovascular wellness screening and blood pressure review.",
                "status": "Confirmed",
                "status_reason": "",
                "notes": "Patient requested morning slot.",
                "created_at": current_timestamp()
            },
            appt2_id: {
                "id": appt2_id,
                "patient_id": pat1_id,
                "doctor_id": doc1_id,
                "date": yesterday_str,
                "time_slot": "02:00 PM",
                "reason": "Comprehensive blood work and hypertension progress check.",
                "status": "Completed",
                "status_reason": "",
                "notes": "Patient arrived on schedule.",
                "created_at": current_timestamp()
            }
        }

        diagnoses = {
            diag1_id: {
                "id": diag1_id,
                "appointment_id": appt2_id,
                "patient_id": pat1_id,
                "doctor_id": doc1_id,
                "diagnosis": "Mild Essential Hypertension - Well Controlled",
                "prescription": "1. Amlodipine 5mg - 1 tablet daily in the morning.\n2. CoQ10 100mg - 1 tablet daily with food.\n3. Low sodium Mediterranean diet.",
                "additional_notes": "Blood pressure reading: 122/78 mmHg. Resting ECG normal. Continue daily morning walk of 30 mins.",
                "follow_up_date": (now + timedelta(days=90)).strftime("%Y-%m-%d"),
                "is_read": False,
                "addenda": [
                    {
                        "timestamp": current_timestamp(),
                        "doctor_id": doc1_id,
                        "text": "Addendum: Lab panel received. Serum electrolytes, lipid profile, and renal metrics are completely within normal range."
                    }
                ],
                "created_at": current_timestamp()
            }
        }

        notifs = {
            "notif_001": {
                "id": "notif_001",
                "user_id": pat1_id,
                "title": "Appointment Confirmed",
                "message": f"Dr. Sarah Jenkins has confirmed your visit for {tomorrow_str} at 10:00 AM.",
                "type": "appointment",
                "related_id": appt1_id,
                "is_read": False,
                "created_at": current_timestamp()
            },
            "notif_002": {
                "id": "notif_002",
                "user_id": pat1_id,
                "title": "Diagnosis Report Available",
                "message": "Dr. Sarah Jenkins has issued your diagnosis report and digital prescription.",
                "type": "diagnosis",
                "related_id": diag1_id,
                "is_read": False,
                "created_at": current_timestamp()
            },
            "notif_003": {
                "id": "notif_003",
                "user_id": doc1_id,
                "title": "Upcoming Consultation Scheduled",
                "message": f"Appointment scheduled with Madhura Patil on {tomorrow_str} at 10:00 AM.",
                "type": "appointment",
                "related_id": appt1_id,
                "is_read": True,
                "created_at": current_timestamp()
            }
        }

        data = {
            "users": users,
            "patients": patients,
            "doctors": doctors,
            "appointments": appointments,
            "diagnoses": diagnoses,
            "notifications": notifs,
            "access_logs": {}
        }
        self._write_data(data)
        logger.info("Demo database seeded successfully with mock patient and doctor records.")

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        data = self._read_data()
        return data["users"].get(user_id)

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        data = self._read_data()
        for u in data["users"].values():
            if u["email"].lower() == email.lower():
                return u
        return None

    def create_user(self, user: User, profile_data: Dict[str, Any]) -> str:
        data = self._read_data()
        data["users"][user.id] = user.to_dict()

        if user.role == "patient":
            p = PatientProfile(
                user_id=user.id,
                date_of_birth=profile_data.get("date_of_birth", "2000-01-01"),
                age=int(profile_data.get("age", 25)),
                gender=profile_data.get("gender", "Not Specified"),
                blood_group=profile_data.get("blood_group", "Unknown"),
                conditions=profile_data.get("conditions", ""),
                medications=profile_data.get("medications", ""),
                medical_history=profile_data.get("medical_history", ""),
                emergency_contact=profile_data.get("emergency_contact", ""),
                allergies=profile_data.get("allergies", "None reported")
            )
            data["patients"][user.id] = p.to_dict()
        elif user.role == "doctor":
            d = DoctorProfile(
                user_id=user.id,
                specialization=profile_data.get("specialization", "General Practice"),
                experience=int(profile_data.get("experience", 1)),
                license_no=profile_data.get("license_no", "MED-0000"),
                hospital=profile_data.get("hospital", "MedTrack Central Hospital"),
                bio=profile_data.get("bio", "")
            )
            data["doctors"][user.id] = d.to_dict()

        if USE_AWS and users_table:
            try:
                users_table.put_item(Item={
                    "id": user.id,
                    "name": user.name,
                    "email": user.email,
                    "phone": user.phone,
                    "role": user.role,
                    "created_at": user.created_at,
                    **profile_data
                })
            except Exception as e:
                logger.warning(f"AWS DynamoDB user write skipped: {e}")

        self._write_data(data)
        logger.info(f"User created: {user.email} (Role: {user.role}, ID: {user.id})")
        return user.id

    def update_user(self, user_id: str, **kwargs) -> bool:
        data = self._read_data()
        if user_id in data["users"]:
            data["users"][user_id].update(kwargs)
            self._write_data(data)
            return True
        return False

    def get_patient_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        data = self._read_data()
        return data["patients"].get(user_id)

    def update_patient_profile(self, user_id: str, **kwargs) -> bool:
        data = self._read_data()
        if user_id in data["patients"]:
            data["patients"][user_id].update(kwargs)
            self._write_data(data)
            return True
        return False

    def get_doctor_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        data = self._read_data()
        return data["doctors"].get(user_id)

    def update_doctor_profile(self, user_id: str, **kwargs) -> bool:
        data = self._read_data()
        if user_id in data["doctors"]:
            data["doctors"][user_id].update(kwargs)
            self._write_data(data)
            return True
        return False

    def get_all_doctors(self) -> List[Dict[str, Any]]:
        data = self._read_data()
        doctors = []
        for user_id, doc_profile in data["doctors"].items():
            user = data["users"].get(user_id)
            if user:
                doctors.append({
                    **user,
                    **doc_profile
                })
        return doctors

    def get_doctor_detail(self, doctor_id: str) -> Optional[Dict[str, Any]]:
        data = self._read_data()
        user = data["users"].get(doctor_id)
        profile = data["doctors"].get(doctor_id)
        if user and profile:
            return {**user, **profile}
        return None

    def get_patient_detail(self, patient_id: str) -> Optional[Dict[str, Any]]:
        data = self._read_data()
        user = data["users"].get(patient_id)
        profile = data["patients"].get(patient_id)
        if user and profile:
            return {**user, **profile}
        return None

    def has_appointment_relationship(self, doctor_id: str, patient_id: str) -> bool:
        data = self._read_data()
        for appt in data["appointments"].values():
            if appt["doctor_id"] == doctor_id and appt["patient_id"] == patient_id:
                return True
        return False

    def log_access(self, doctor_id: str, patient_id: str, action: str):
        data = self._read_data()
        log_id = generate_id("log")
        data["access_logs"][log_id] = {
            "id": log_id,
            "doctor_id": doctor_id,
            "patient_id": patient_id,
            "action": action,
            "timestamp": current_timestamp()
        }
        self._write_data(data)
        logger.info(f"AUDIT LOG: Doctor {doctor_id} performed '{action}' on Patient {patient_id}")

    def get_booked_slots(self, doctor_id: str, date_str: str) -> List[str]:
        data = self._read_data()
        booked = []
        for appt in data["appointments"].values():
            if appt["doctor_id"] == doctor_id and appt["date"] == date_str:
                if appt["status"] in ["Pending", "Confirmed", "Completed"]:
                    booked.append(appt["time_slot"])
        return booked

    def create_appointment(self, appointment: Appointment) -> str:
        data = self._read_data()
        data["appointments"][appointment.id] = appointment.to_dict()

        # Create notification for doctor
        patient = data["users"].get(appointment.patient_id, {})
        notif_id = generate_id("notif")
        data["notifications"][notif_id] = {
            "id": notif_id,
            "user_id": appointment.doctor_id,
            "title": "New Appointment Request",
            "message": f"{patient.get('name', 'A patient')} requested an appointment on {appointment.date} at {appointment.time_slot}.",
            "type": "appointment",
            "related_id": appointment.id,
            "is_read": False,
            "created_at": current_timestamp()
        }

        # Create notification for patient
        doctor = data["users"].get(appointment.doctor_id, {})
        p_notif_id = generate_id("notif")
        data["notifications"][p_notif_id] = {
            "id": p_notif_id,
            "user_id": appointment.patient_id,
            "title": "Appointment Requested",
            "message": f"Your consultation request with Dr. {doctor.get('name', 'Doctor')} on {appointment.date} at {appointment.time_slot} is Pending confirmation.",
            "type": "appointment",
            "related_id": appointment.id,
            "is_read": False,
            "created_at": current_timestamp()
        }

        self._write_data(data)

        if USE_AWS and appointments_table:
            try:
                appointments_table.put_item(Item=appointment.to_dict())
            except Exception as e:
                logger.warning(f"AWS DynamoDB appointment write skipped: {e}")

        # Trigger AWS SNS Notification
        publish_sns_alert(
            "MedTrack: New Appointment Request",
            f"New consultation booked for Dr. {doctor.get('name', 'Doctor')} on {appointment.date} at {appointment.time_slot}. Reason: {appointment.reason}"
        )

        logger.info(f"Appointment booked: {appointment.id} (Doctor: {appointment.doctor_id}, Patient: {appointment.patient_id})")
        return appointment.id

    def get_appointment_by_id(self, appt_id: str) -> Optional[Dict[str, Any]]:
        data = self._read_data()
        appt = data["appointments"].get(appt_id)
        if not appt:
            return None
        doc_user = data["users"].get(appt["doctor_id"], {})
        doc_prof = data["doctors"].get(appt["doctor_id"], {})
        pat_user = data["users"].get(appt["patient_id"], {})
        pat_prof = data["patients"].get(appt["patient_id"], {})
        return {
            **appt,
            "doctor_name": doc_user.get("name", "Doctor"),
            "doctor_specialization": doc_prof.get("specialization", "Specialist"),
            "doctor_hospital": doc_prof.get("hospital", "Central Hospital"),
            "patient_name": pat_user.get("name", "Patient"),
            "patient_phone": pat_user.get("phone", ""),
            "patient_email": pat_user.get("email", ""),
            "patient_age": pat_prof.get("age", "-"),
            "patient_gender": pat_prof.get("gender", "-"),
            "patient_blood_group": pat_prof.get("blood_group", "-"),
            "patient_conditions": pat_prof.get("conditions", "-"),
            "patient_allergies": pat_prof.get("allergies", "None reported"),
            "patient_medications": pat_prof.get("medications", "None")
        }

    def get_patient_appointments(self, patient_id: str) -> List[Dict[str, Any]]:
        data = self._read_data()
        results = []
        for appt in data["appointments"].values():
            if appt["patient_id"] == patient_id:
                doc_user = data["users"].get(appt["doctor_id"], {})
                doc_prof = data["doctors"].get(appt["doctor_id"], {})
                results.append({
                    **appt,
                    "doctor_name": doc_user.get("name", "Doctor"),
                    "doctor_specialization": doc_prof.get("specialization", "Specialist"),
                    "doctor_hospital": doc_prof.get("hospital", "Central Hospital")
                })
        results.sort(key=lambda x: (x["date"], x["time_slot"]), reverse=True)
        return results

    def get_doctor_appointments(self, doctor_id: str) -> List[Dict[str, Any]]:
        data = self._read_data()
        results = []
        for appt in data["appointments"].values():
            if appt["doctor_id"] == doctor_id:
                pat_user = data["users"].get(appt["patient_id"], {})
                pat_prof = data["patients"].get(appt["patient_id"], {})
                results.append({
                    **appt,
                    "patient_name": pat_user.get("name", "Patient"),
                    "patient_phone": pat_user.get("phone", ""),
                    "patient_age": pat_prof.get("age", "-"),
                    "patient_blood_group": pat_prof.get("blood_group", "-")
                })
        results.sort(key=lambda x: (x["date"], x["time_slot"]))
        return results

    def update_appointment_status(self, appt_id: str, new_status: str, status_reason: str = "", notes: Optional[str] = None) -> bool:
        data = self._read_data()
        if appt_id not in data["appointments"]:
            return False

        appt = data["appointments"][appt_id]
        if new_status == "Completed" and appt["status"] != "Confirmed":
            return False

        old_status = appt["status"]
        appt["status"] = new_status
        if status_reason:
            appt["status_reason"] = status_reason
        if notes is not None:
            appt["notes"] = notes

        # Notify patient
        doc_user = data["users"].get(appt["doctor_id"], {})
        notif_id = generate_id("notif")
        title = f"Appointment {new_status}"
        msg = f"Your appointment with Dr. {doc_user.get('name', 'Doctor')} on {appt['date']} has been updated to '{new_status}'."
        if status_reason:
            msg += f" Note: {status_reason}"

        data["notifications"][notif_id] = {
            "id": notif_id,
            "user_id": appt["patient_id"],
            "title": title,
            "message": msg,
            "type": "appointment",
            "related_id": appt_id,
            "is_read": False,
            "created_at": current_timestamp()
        }

        self._write_data(data)

        if USE_AWS and appointments_table:
            try:
                appointments_table.update_item(
                    Key={"id": appt_id},
                    UpdateExpression="SET #s = :st, status_reason = :sr",
                    ExpressionAttributeNames={"#s": "status"},
                    ExpressionAttributeValues={":st": new_status, ":sr": status_reason}
                )
            except Exception as e:
                logger.warning(f"AWS DynamoDB status update skipped: {e}")

        # Trigger AWS SNS Notification
        publish_sns_alert(
            f"MedTrack: Appointment {new_status}",
            f"Your appointment with Dr. {doc_user.get('name', 'Doctor')} on {appt['date']} has been updated to '{new_status}'."
        )

        logger.info(f"Appointment {appt_id} status changed from {old_status} to {new_status}")
        return True

    def reschedule_appointment(self, appt_id: str, new_date: str, new_slot: str) -> bool:
        data = self._read_data()
        if appt_id not in data["appointments"]:
            return False

        appt = data["appointments"][appt_id]
        old_date = appt["date"]
        old_slot = appt["time_slot"]

        appt["date"] = new_date
        appt["time_slot"] = new_slot
        appt["status"] = "Pending"
        appt["status_reason"] = f"Rescheduled from {old_date} {old_slot}"

        doc_user = data["users"].get(appt["doctor_id"], {})
        pat_user = data["users"].get(appt["patient_id"], {})

        notif_id = generate_id("notif")
        data["notifications"][notif_id] = {
            "id": notif_id,
            "user_id": appt["doctor_id"],
            "title": "Appointment Rescheduled",
            "message": f"Patient {pat_user.get('name', 'Patient')} rescheduled their appointment to {new_date} at {new_slot}.",
            "type": "appointment",
            "related_id": appt_id,
            "is_read": False,
            "created_at": current_timestamp()
        }

        self._write_data(data)
        logger.info(f"Appointment {appt_id} rescheduled to {new_date} {new_slot}")
        return True

    def create_diagnosis(self, report: DiagnosisReport) -> str:
        data = self._read_data()
        data["diagnoses"][report.id] = report.to_dict()

        if report.appointment_id in data["appointments"]:
            data["appointments"][report.appointment_id]["status"] = "Completed"

        doc_user = data["users"].get(report.doctor_id, {})
        notif_id = generate_id("notif")
        data["notifications"][notif_id] = {
            "id": notif_id,
            "user_id": report.patient_id,
            "title": "Diagnosis Report Available",
            "message": f"Dr. {doc_user.get('name', 'Doctor')} has filed your clinical diagnosis and prescription report.",
            "type": "diagnosis",
            "related_id": report.id,
            "is_read": False,
            "created_at": current_timestamp()
        }

        self._write_data(data)

        if USE_AWS and diagnoses_table:
            try:
                diagnoses_table.put_item(Item=report.to_dict())
            except Exception as e:
                logger.warning(f"AWS DynamoDB diagnosis write skipped: {e}")

        # Trigger AWS SNS Notification
        publish_sns_alert(
            "MedTrack: Diagnosis Report Ready",
            f"Dr. {doc_user.get('name', 'Doctor')} has filed your clinical diagnosis and prescription report #{report.id}."
        )

        logger.info(f"Diagnosis submitted: {report.id} for Appointment {report.appointment_id}")
        return report.id

    def add_diagnosis_addendum(self, diag_id: str, text: str, doctor_id: str) -> bool:
        data = self._read_data()
        if diag_id not in data["diagnoses"]:
            return False

        diag = data["diagnoses"][diag_id]
        if diag["doctor_id"] != doctor_id:
            return False

        addendum_entry = {
            "timestamp": current_timestamp(),
            "doctor_id": doctor_id,
            "text": text
        }
        if "addenda" not in diag:
            diag["addenda"] = []
        diag["addenda"].append(addendum_entry)

        # Notify patient of addendum
        notif_id = generate_id("notif")
        data["notifications"][notif_id] = {
            "id": notif_id,
            "user_id": diag["patient_id"],
            "title": "Diagnosis Addendum Added",
            "message": f"An official clinical addendum was appended to your diagnosis report #{diag_id}.",
            "type": "diagnosis",
            "related_id": diag_id,
            "is_read": False,
            "created_at": current_timestamp()
        }

        self._write_data(data)
        logger.info(f"Addendum appended to Diagnosis {diag_id} by Doctor {doctor_id}")
        return True

    def get_diagnosis_by_id(self, diag_id: str) -> Optional[Dict[str, Any]]:
        data = self._read_data()
        diag = data["diagnoses"].get(diag_id)
        if not diag:
            return None
        doc_user = data["users"].get(diag["doctor_id"], {})
        doc_prof = data["doctors"].get(diag["doctor_id"], {})
        pat_user = data["users"].get(diag["patient_id"], {})
        pat_prof = data["patients"].get(diag["patient_id"], {})
        appt = data["appointments"].get(diag.get("appointment_id"), {})
        return {
            **diag,
            "doctor_name": doc_user.get("name", "Doctor"),
            "doctor_specialization": doc_prof.get("specialization", "Specialist"),
            "doctor_hospital": doc_prof.get("hospital", "Central Hospital"),
            "doctor_license": doc_prof.get("license_no", ""),
            "patient_name": pat_user.get("name", "Patient"),
            "patient_age": pat_prof.get("age", "-"),
            "patient_date_of_birth": pat_prof.get("date_of_birth", "-"),
            "patient_gender": pat_prof.get("gender", "-"),
            "patient_blood_group": pat_prof.get("blood_group", "-"),
            "appointment_date": appt.get("date", "-"),
            "appointment_reason": appt.get("reason", "-")
        }

    def get_patient_diagnoses(self, patient_id: str) -> List[Dict[str, Any]]:
        data = self._read_data()
        results = []
        for diag in data["diagnoses"].values():
            if diag["patient_id"] == patient_id:
                doc_user = data["users"].get(diag["doctor_id"], {})
                doc_prof = data["doctors"].get(diag["doctor_id"], {})
                appt = data["appointments"].get(diag.get("appointment_id"), {})
                results.append({
                    **diag,
                    "doctor_name": doc_user.get("name", "Doctor"),
                    "doctor_specialization": doc_prof.get("specialization", "Specialist"),
                    "doctor_hospital": doc_prof.get("hospital", "Central Hospital"),
                    "appointment_date": appt.get("date", "-") if appt else "-"
                })
        results.sort(key=lambda x: x["created_at"], reverse=True)
        return results

    def get_unread_diagnosis_count(self, patient_id: str) -> int:
        data = self._read_data()
        return sum(1 for d in data["diagnoses"].values() if d["patient_id"] == patient_id and not d.get("is_read", False))

    def mark_diagnosis_read(self, diag_id: str):
        data = self._read_data()
        if diag_id in data["diagnoses"]:
            data["diagnoses"][diag_id]["is_read"] = True
            self._write_data(data)

    def get_diagnosis_by_appointment(self, appointment_id: str) -> Optional[Dict[str, Any]]:
        data = self._read_data()
        for diag_id, diag in data["diagnoses"].items():
            if diag.get("appointment_id") == appointment_id:
                return self.get_diagnosis_by_id(diag_id)
        return None

    def create_notification(self, notif: Notification) -> str:
        data = self._read_data()
        data["notifications"][notif.id] = notif.to_dict()
        self._write_data(data)
        return notif.id

    def get_user_notifications(self, user_id: str) -> List[Dict[str, Any]]:
        data = self._read_data()
        results = [n for n in data["notifications"].values() if n["user_id"] == user_id]
        results.sort(key=lambda x: x["created_at"], reverse=True)
        return results

    def mark_notification_as_read(self, notif_id: str) -> bool:
        data = self._read_data()
        if notif_id in data["notifications"]:
            data["notifications"][notif_id]["is_read"] = True
            self._write_data(data)
            return True
        return False

    def mark_all_notifications_read(self, user_id: str) -> bool:
        data = self._read_data()
        changed = False
        for n in data["notifications"].values():
            if n["user_id"] == user_id and not n["is_read"]:
                n["is_read"] = True
                changed = True
        if changed:
            self._write_data(data)
        return True

    def get_unread_count(self, user_id: str) -> int:
        data = self._read_data()
        return sum(1 for n in data["notifications"].values() if n["user_id"] == user_id and not n["is_read"])

    def get_doctor_patients(self, doctor_id: str) -> List[Dict[str, Any]]:
        data = self._read_data()
        patient_ids = set()
        for appt in data["appointments"].values():
            if appt["doctor_id"] == doctor_id:
                patient_ids.add(appt["patient_id"])

        patients = []
        for pid in patient_ids:
            user = data["users"].get(pid)
            prof = data["patients"].get(pid)
            if user and prof:
                patients.append({**user, **prof})
        return patients

# -----------------------------------------------------------------------------
# 5. Access Control Decorators
# -----------------------------------------------------------------------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please sign in to access this page.", "warning")
            return redirect(url_for('login', next=request.path))
        return f(*args, **kwargs)
    return decorated_function

def patient_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in as a patient to access this page.", "warning")
            return redirect(url_for('login', next=request.path))
        if session.get('role') != 'patient':
            flash("Access restricted to registered patients.", "danger")
            return redirect(url_for('doctor_dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def doctor_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in as a doctor to access this portal.", "warning")
            return redirect(url_for('login', next=request.path))
        if session.get('role') != 'doctor':
            flash("Access restricted to licensed healthcare professionals.", "danger")
            return redirect(url_for('patient_dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# -----------------------------------------------------------------------------
# 6. Application Factory & Route Registration
# -----------------------------------------------------------------------------
def create_app(config_class=Config):
    app = Flask(
        __name__,
        template_folder=os.path.join(BASE_DIR, 'templates'),
        static_folder=os.path.join(BASE_DIR, 'static')
    )
    app.config.from_object(config_class)

    # Global Template Context Processor
    @app.context_processor
    def inject_global_vars():
        unread_count = 0
        current_user = None
        if 'user_id' in session:
            db = DataStore()
            unread_count = db.get_unread_count(session['user_id'])
            current_user = db.get_user_by_id(session['user_id'])
        return {
            'app_name': Config.APP_NAME,
            'app_tagline': Config.APP_TAGLINE,
            'unread_notifications_count': unread_count,
            'current_session_user': current_user
        }

    # -------------------------------------------------------------------------
    # Public Routes
    # -------------------------------------------------------------------------
    @app.route('/')
    def index():
        if 'user_id' in session:
            if session.get('role') == 'doctor':
                return redirect(url_for('doctor_dashboard'))
            return redirect(url_for('patient_dashboard'))

        db = DataStore()
        doctors = db.get_all_doctors()[:4]
        return render_template('index.html', doctors=doctors)

    @app.route('/about')
    def about():
        db = DataStore()
        doctors = db.get_all_doctors()[:4]
        return render_template('index.html', doctors=doctors)

    @app.route('/search')
    def search():
        db = DataStore()
        all_docs = db.get_all_doctors()
        query = request.args.get('q', '').strip().lower()
        spec = request.args.get('specialization', '').strip()

        results = all_docs
        if query:
            results = [
                d for d in results
                if query in d.get('name', '').lower()
                or query in d.get('specialization', '').lower()
                or query in d.get('hospital', '').lower()
            ]
        if spec:
            results = [d for d in results if d.get('specialization', '').lower() == spec.lower()]

        return render_template('search_results.html', results=results, query=query, selected_spec=spec)

    # -------------------------------------------------------------------------
    # Authentication Routes
    # -------------------------------------------------------------------------
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if 'user_id' in session:
            if session.get('role') == 'doctor':
                return redirect(url_for('doctor_dashboard'))
            return redirect(url_for('patient_dashboard'))

        if request.method == 'POST':
            email = request.form.get('email', '').strip()
            password = request.form.get('password', '')
            remember = request.form.get('remember') == 'on'

            if not email or not password:
                flash("Please provide both email and password.", "danger")
                return render_template('login.html', email=email)

            db = DataStore()
            user = db.get_user_by_email(email)

            if not user or not check_password_hash(user['password_hash'], password):
                flash("Invalid email or password. Please verify your credentials.", "danger")
                return render_template('login.html', email=email)

            session.clear()
            session['user_id'] = user['id']
            session['name'] = user['name']
            session['email'] = user['email']
            session['role'] = user['role']
            if remember:
                session.permanent = True

            flash(f"Welcome back, {user['name']}!", "success")
            logger.info(f"User signed in: {user['email']} ({user['role']})")

            next_page = request.args.get('next')
            if next_page and next_page.startswith('/'):
                return redirect(next_page)

            if user['role'] == 'doctor':
                return redirect(url_for('doctor_dashboard'))
            return redirect(url_for('patient_dashboard'))

        return render_template('login.html')

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if 'user_id' in session:
            if session.get('role') == 'doctor':
                return redirect(url_for('doctor_dashboard'))
            return redirect(url_for('patient_dashboard'))

        default_role = request.args.get('role', 'patient')

        if request.method == 'POST':
            role = request.form.get('role', 'patient').lower()
            name = request.form.get('name', '').strip()
            email = request.form.get('email', '').strip().lower()
            phone = request.form.get('phone', '').strip()
            password = request.form.get('password', '')
            confirm_password = request.form.get('confirm_password', '')

            if not name or not email or not password or not phone:
                flash("All standard fields are required.", "danger")
                return render_template('register.html', role=role, form=request.form)

            if len(password) < 8:
                flash("Password must be at least 8 characters long.", "danger")
                return render_template('register.html', role=role, form=request.form)

            if password != confirm_password:
                flash("Passwords do not match.", "danger")
                return render_template('register.html', role=role, form=request.form)

            db = DataStore()
            if db.get_user_by_email(email):
                flash("An account with this email address already exists. Please sign in.", "warning")
                return render_template('register.html', role=role, form=request.form)

            profile_data = {}
            if role == 'patient':
                dob = request.form.get('date_of_birth', '').strip()
                if not dob:
                    flash("Date of birth is required for patient registration.", "danger")
                    return render_template('register.html', role=role, form=request.form)

                try:
                    birth_year = int(dob.split('-')[0])
                    calculated_age = max(1, datetime.now().year - birth_year)
                except Exception:
                    calculated_age = 25

                profile_data = {
                    "date_of_birth": dob,
                    "age": calculated_age,
                    "gender": request.form.get('gender', 'Not Specified'),
                    "blood_group": request.form.get('blood_group', 'Unknown'),
                    "conditions": request.form.get('conditions', '').strip(),
                    "medications": request.form.get('medications', '').strip(),
                    "medical_history": request.form.get('conditions', '').strip(),
                    "emergency_contact": request.form.get('emergency_contact', '').strip(),
                    "allergies": request.form.get('allergies', 'None reported').strip()
                }
            elif role == 'doctor':
                spec = request.form.get('specialization', '').strip()
                exp = request.form.get('experience', '').strip()
                lic = request.form.get('license_no', '').strip()
                if not spec or not exp or not lic:
                    flash("Specialisation, years of experience, and medical registration number are all mandatory for doctors.", "danger")
                    return render_template('register.html', role=role, form=request.form)

                profile_data = {
                    "specialization": spec,
                    "experience": int(exp) if exp.isdigit() else 1,
                    "license_no": lic,
                    "hospital": request.form.get('hospital', 'MedTrack Health Network').strip(),
                    "bio": request.form.get('bio', '').strip()
                }

            prefix = "usr_doc" if role == "doctor" else "usr_pat"
            user_id = generate_id(prefix)

            user = User(
                id=user_id,
                name=name,
                email=email,
                phone=phone,
                role=role,
                password_hash=generate_password_hash(password)
            )
            db.create_user(user, profile_data)

            flash("Registration successful! You can now log in with your credentials.", "success")
            return redirect(url_for('login'))

        return render_template('register.html', role=default_role)

    @app.route('/logout')
    def logout():
        name = session.get('name', 'User')
        session.clear()
        flash(f"You have been successfully signed out. Have a healthy day, {name}!", "info")
        return redirect(url_for('index'))

    # -------------------------------------------------------------------------
    # Patient Routes
    # -------------------------------------------------------------------------
    @app.route('/patient/dashboard', endpoint='patient_dashboard')
    @app.route('/patient_dashboard')
    @patient_required
    def patient_dashboard():
        user_id = session['user_id']
        db = DataStore()

        user = db.get_user_by_id(user_id)
        profile = db.get_patient_profile(user_id)
        appointments = db.get_patient_appointments(user_id)
        diagnoses = db.get_patient_diagnoses(user_id)
        unread_notifs = db.get_unread_count(user_id)
        unread_reports = db.get_unread_diagnosis_count(user_id)
        all_notifs = db.get_user_notifications(user_id)

        upcoming = [a for a in appointments if a['status'] in ['Confirmed', 'Pending']]
        next_appointment = upcoming[0] if upcoming else None

        stats = {
            "total_appointments": len(appointments),
            "upcoming_count": len(upcoming),
            "reports_count": len(diagnoses),
            "unread_reports_count": unread_reports,
            "unread_notifications": unread_notifs
        }

        return render_template(
            'patient_dashboard.html',
            user=user,
            profile=profile,
            stats=stats,
            next_appointment=next_appointment,
            recent_diagnoses=diagnoses[:3],
            notifications=all_notifs
        )

    @app.route('/book-appointment', methods=['GET', 'POST'], endpoint='book_appointment')
    @app.route('/patient/book-appointment', methods=['GET', 'POST'])
    @patient_required
    def book_appointment():
        user_id = session['user_id']
        db = DataStore()
        doctors = db.get_all_doctors()

        if request.method == 'POST':
            doctor_id = request.form.get('doctor_id')
            date = request.form.get('date')
            time_slot = request.form.get('time_slot')
            reason = request.form.get('reason', '').strip()

            if not doctor_id or not date or not time_slot or not reason:
                flash("Please complete all booking fields.", "danger")
                return render_template('book_appointment.html', doctors=doctors)

            if len(reason) > 500:
                flash("Reason for visit cannot exceed 500 characters.", "danger")
                return render_template('book_appointment.html', doctors=doctors)

            today_str = datetime.now().strftime("%Y-%m-%d")
            if date < today_str:
                flash("Consultation date must be today or in the future.", "danger")
                return render_template('book_appointment.html', doctors=doctors)

            booked_slots = db.get_booked_slots(doctor_id, date)
            if time_slot in booked_slots:
                flash("This time slot has already been booked by another patient. Please select an alternate slot.", "danger")
                return render_template('book_appointment.html', doctors=doctors, selected_doctor_id=doctor_id)

            appt_id = generate_id("apt")
            appointment = Appointment(
                id=appt_id,
                patient_id=user_id,
                doctor_id=doctor_id,
                date=date,
                time_slot=time_slot,
                reason=reason,
                status="Pending"
            )
            db.create_appointment(appointment)

            flash("Appointment request submitted successfully! Your doctor will review the schedule shortly.", "success")
            return redirect(url_for('view_appointment_patient'))

        selected_doctor_id = request.args.get('doctor_id', '')
        return render_template('book_appointment.html', doctors=doctors, selected_doctor_id=selected_doctor_id)

    @app.route('/patient/appointments', endpoint='view_appointment_patient')
    @app.route('/view_appointment_patient')
    @patient_required
    def view_appointment_patient():
        user_id = session['user_id']
        db = DataStore()
        all_appts = db.get_patient_appointments(user_id)
        diagnoses = db.get_patient_diagnoses(user_id)
        return render_template('view_appointment_patient.html', appointments=all_appts, diagnoses=diagnoses)

    @app.route('/patient/diagnosis-reports')
    @patient_required
    def patient_diagnosis_reports():
        user_id = session['user_id']
        db = DataStore()
        all_appts = db.get_patient_appointments(user_id)
        diagnoses = db.get_patient_diagnoses(user_id)
        return render_template('view_appointment_patient.html', appointments=all_appts, diagnoses=diagnoses)

    @app.route('/patient/notifications')
    @patient_required
    def patient_notifications():
        return patient_dashboard()

    @app.route('/appointment/<appt_id>/cancel', methods=['POST'], endpoint='cancel_appointment')
    @app.route('/patient/appointments/<appt_id>/cancel', methods=['POST'])
    @patient_required
    def cancel_appointment(appt_id):
        user_id = session['user_id']
        db = DataStore()
        appt = db.get_appointment_by_id(appt_id)

        if not appt or appt['patient_id'] != user_id:
            flash("Appointment not found or unauthorized.", "danger")
            return redirect(url_for('view_appointment_patient'))

        if appt['status'] == 'Completed':
            flash("Cannot cancel an already completed appointment.", "warning")
            return redirect(url_for('view_appointment_patient'))

        try:
            appt_datetime_str = f"{appt['date']} {appt['time_slot']}"
            appt_dt = datetime.strptime(appt_datetime_str, "%Y-%m-%d %I:%M %p")
            if appt_dt - datetime.now() < timedelta(hours=24):
                db.update_appointment_status(appt_id, "Cancelled", status_reason="Cancelled by patient (< 24h notice)")
                flash("Appointment cancelled. Notice: cancellation took place with less than 24 hours notice.", "warning")
                return redirect(url_for('view_appointment_patient'))
        except Exception:
            pass

        db.update_appointment_status(appt_id, "Cancelled", status_reason="Cancelled by patient.")
        flash("Appointment has been cancelled successfully.", "info")
        return redirect(url_for('view_appointment_patient'))

    @app.route('/appointment/<appt_id>/reschedule', methods=['POST'], endpoint='reschedule_appointment')
    @app.route('/patient/appointments/<appt_id>/reschedule', methods=['POST'])
    @patient_required
    def reschedule_appointment(appt_id):
        user_id = session['user_id']
        db = DataStore()
        appt = db.get_appointment_by_id(appt_id)

        if not appt or appt['patient_id'] != user_id:
            flash("Appointment not found or unauthorized.", "danger")
            return redirect(url_for('view_appointment_patient'))

        if appt['status'] == 'Completed':
            flash("Cannot reschedule an already completed appointment.", "warning")
            return redirect(url_for('view_appointment_patient'))

        new_date = request.form.get('new_date')
        new_slot = request.form.get('new_slot')

        if not new_date or not new_slot:
            flash("Please provide both a new date and time slot for rescheduling.", "danger")
            return redirect(url_for('view_appointment_patient'))

        booked = db.get_booked_slots(appt['doctor_id'], new_date)
        if new_slot in booked:
            flash("Selected time slot is already booked for this doctor. Please pick another.", "danger")
            return redirect(url_for('view_appointment_patient'))

        db.reschedule_appointment(appt_id, new_date, new_slot)
        flash(f"Appointment rescheduled to {new_date} at {new_slot} and submitted for doctor re-confirmation.", "info")
        return redirect(url_for('view_appointment_patient'))

    @app.route('/api/booked-slots', endpoint='api_booked_slots')
    @app.route('/patient/api/booked-slots')
    def api_booked_slots():
        doctor_id = request.args.get('doctor_id')
        date_str = request.args.get('date')
        if not doctor_id or not date_str:
            return jsonify({"booked": []})
        db = DataStore()
        booked = db.get_booked_slots(doctor_id, date_str)
        return jsonify({"booked": booked})

    # -------------------------------------------------------------------------
    # Doctor Routes
    # -------------------------------------------------------------------------
    @app.route('/doctor/dashboard', endpoint='doctor_dashboard')
    @app.route('/doctor_dashboard')
    @doctor_required
    def doctor_dashboard():
        user_id = session['user_id']
        db = DataStore()

        user = db.get_user_by_id(user_id)
        profile = db.get_doctor_profile(user_id)
        appointments = db.get_doctor_appointments(user_id)
        patients = db.get_doctor_patients(user_id)
        unread_notifs = db.get_unread_count(user_id)

        today_str = datetime.now().strftime("%Y-%m-%d")
        today_appointments = [a for a in appointments if a['date'] == today_str]
        pending_appointments = [a for a in appointments if a['status'] == 'Pending']
        awaiting_report = [a for a in appointments if a['status'] == 'Confirmed']

        stats = {
            "today_appointments_count": len(today_appointments),
            "total_patients_count": len(patients),
            "pending_requests_count": len(pending_appointments),
            "awaiting_report_count": len(awaiting_report),
            "unread_notifications": unread_notifs
        }

        return render_template(
            'doctor_dashboard.html',
            user=user,
            profile=profile,
            stats=stats,
            today_appointments=today_appointments,
            recent_appointments=appointments[:5]
        )

    @app.route('/doctor/appointments', endpoint='view_appointment_doctor')
    @app.route('/view_appointment_doctor')
    @doctor_required
    def view_appointment_doctor():
        user_id = session['user_id']
        db = DataStore()
        all_appts = db.get_doctor_appointments(user_id)
        filter_status = request.args.get('status', 'all')
        filter_date = request.args.get('date', '')

        filtered = all_appts
        if filter_status != 'all':
            filtered = [a for a in filtered if a['status'].lower() == filter_status.lower()]
        if filter_date:
            filtered = [a for a in filtered if a['date'] == filter_date]

        return render_template(
            'view_appointment_doctor.html',
            appointments=filtered,
            current_filter=filter_status,
            filter_date=filter_date
        )

    @app.route('/doctor/appointments/<appt_id>/status', methods=['POST'], endpoint='update_appointment_status')
    @app.route('/appointment/<appt_id>/status', methods=['POST'])
    @doctor_required
    def update_appointment_status(appt_id):
        user_id = session['user_id']
        db = DataStore()
        appt = db.get_appointment_by_id(appt_id)

        if not appt or appt['doctor_id'] != user_id:
            flash("Appointment not found or unauthorized.", "danger")
            return redirect(url_for('view_appointment_doctor'))

        new_status = request.form.get('status')
        status_reason = request.form.get('status_reason', '').strip()

        if new_status in ['Rejected', 'Cancelled'] and not status_reason:
            status_reason = "Clinical schedule conflict / doctor unavailability"

        if new_status == 'Completed' and appt['status'] != 'Confirmed':
            flash("An appointment cannot move to Completed unless it was previously Confirmed.", "danger")
            return redirect(request.referrer or url_for('view_appointment_doctor'))

        if new_status in ['Confirmed', 'Rejected', 'Cancelled', 'Completed']:
            success = db.update_appointment_status(appt_id, new_status, status_reason=status_reason)
            if success:
                flash(f"Appointment status updated to '{new_status}'.", "success")
            else:
                flash("Invalid status transition.", "danger")
        else:
            flash("Invalid status choice.", "danger")

        return redirect(request.referrer or url_for('view_appointment_doctor'))

    @app.route('/doctor/diagnose/<appointment_id>', methods=['GET', 'POST'], endpoint='submit_diagnosis')
    @app.route('/appointment/<appointment_id>/diagnosis', methods=['GET', 'POST'])
    @doctor_required
    def submit_diagnosis(appointment_id):
        doctor_id = session['user_id']
        db = DataStore()
        appt = db.get_appointment_by_id(appointment_id)

        if not appt or appt['doctor_id'] != doctor_id:
            flash("Appointment not found or unauthorized.", "danger")
            return redirect(url_for('view_appointment_doctor'))

        existing = db.get_diagnosis_by_appointment(appointment_id)

        if request.method == 'POST':
            if existing:
                flash("A diagnosis report has already been filed for this appointment. You may append an addendum below.", "warning")
                return redirect(url_for('view_appointment', appointment_id=appointment_id))

            diagnosis_text = request.form.get('diagnosis', '').strip()
            prescription = request.form.get('prescription', '').strip()
            notes = request.form.get('notes', '').strip()
            follow_up_date = request.form.get('follow_up_date', '').strip()

            if not diagnosis_text:
                flash("Clinical diagnosis description is mandatory.", "danger")
                return redirect(url_for('view_appointment', appointment_id=appointment_id))

            report_id = generate_id("diag")
            report = DiagnosisReport(
                id=report_id,
                appointment_id=appointment_id,
                patient_id=appt['patient_id'],
                doctor_id=doctor_id,
                diagnosis=diagnosis_text,
                prescription=prescription,
                additional_notes=notes,
                follow_up_date=follow_up_date
            )
            db.create_diagnosis(report)

            flash("Clinical diagnosis report saved and submitted to patient successfully!", "success")
            return redirect(url_for('view_appointment', appointment_id=appointment_id))

        return redirect(url_for('view_appointment', appointment_id=appointment_id))

    @app.route('/doctor/diagnose/<diag_id>/addendum', methods=['POST'], endpoint='add_diagnosis_addendum')
    @app.route('/appointment/<diag_id>/addendum', methods=['POST'])
    @doctor_required
    def add_diagnosis_addendum(diag_id):
        doctor_id = session['user_id']
        db = DataStore()
        addendum_text = request.form.get('addendum_text', '').strip()

        if not addendum_text:
            flash("Addendum text cannot be empty.", "warning")
            return redirect(request.referrer or url_for('view_appointment_doctor'))

        success = db.add_diagnosis_addendum(diag_id, addendum_text, doctor_id)
        if success:
            flash("Clinical addendum appended successfully to the permanent record.", "success")
        else:
            flash("Unauthorized or report not found.", "danger")

        return redirect(request.referrer or url_for('view_appointment_doctor'))

    @app.route('/doctor/patient/<patient_id>')
    @doctor_required
    def doctor_patient_detail(patient_id):
        doctor_id = session['user_id']
        db = DataStore()

        if not db.has_appointment_relationship(doctor_id, patient_id):
            flash("Access Denied: You are only permitted to view records of patients who have an active or past appointment with you.", "danger")
            return redirect(url_for('doctor_dashboard'))

        patient_info = db.get_patient_detail(patient_id)
        if not patient_info:
            flash("Patient not found.", "danger")
            return redirect(url_for('doctor_dashboard'))

        db.log_access(doctor_id, patient_id, 'view_patient_history')
        all_appts = [a for a in db.get_patient_appointments(patient_id) if a['doctor_id'] == doctor_id]
        return render_template('view_appointment_doctor.html', appointments=all_appts)

    # -------------------------------------------------------------------------
    # Shared Consultation Detail View
    # -------------------------------------------------------------------------
    @app.route('/appointment/<appointment_id>', endpoint='view_appointment')
    @app.route('/view_appointment/<appointment_id>')
    @login_required
    def view_appointment(appointment_id):
        user_id = session['user_id']
        role = session.get('role')
        db = DataStore()

        appt = db.get_appointment_by_id(appointment_id)
        if not appt:
            flash("Appointment record not found.", "danger")
            return redirect(url_for('patient_dashboard' if role == 'patient' else 'doctor_dashboard'))

        # Security check: User must be doctor or patient on this appointment
        if appt['patient_id'] != user_id and appt['doctor_id'] != user_id:
            flash("Unauthorized: You do not have permission to view this medical consultation.", "danger")
            return redirect(url_for('patient_dashboard' if role == 'patient' else 'doctor_dashboard'))

        if role == 'doctor':
            db.log_access(user_id, appt['patient_id'], 'view_appointment_details')

        diagnosis = db.get_diagnosis_by_appointment(appointment_id)
        if diagnosis and role == 'patient':
            db.mark_diagnosis_read(diagnosis['id'])

        return render_template('view_appointment.html', appointment=appt, diagnosis=diagnosis)

    # -------------------------------------------------------------------------
    # Notifications Management
    # -------------------------------------------------------------------------
    @app.route('/notifications/read-all', methods=['POST'], endpoint='mark_all_notifications_read')
    @app.route('/patient/notifications/mark-all-read', methods=['POST'])
    @app.route('/doctor/notifications/mark-all-read', methods=['POST'])
    @login_required
    def mark_all_notifications_read():
        user_id = session['user_id']
        db = DataStore()
        db.mark_all_notifications_read(user_id)
        flash("All notifications marked as read.", "info")
        return redirect(request.referrer or url_for('patient_dashboard' if session.get('role') == 'patient' else 'doctor_dashboard'))

    @app.route('/notifications/<notif_id>/read', methods=['POST'])
    @login_required
    def mark_single_notification_read(notif_id):
        db = DataStore()
        db.mark_notification_as_read(notif_id)
        return redirect(request.referrer or url_for('patient_dashboard' if session.get('role') == 'patient' else 'doctor_dashboard'))

    return app

# -----------------------------------------------------------------------------
# 7. Global Exposes & Backwards-Compatibility Aliases
# -----------------------------------------------------------------------------
app = create_app()

# Expose modules so test_app.py or legacy scripts importing from app can seamlessly resolve
sys.modules['app'] = sys.modules[__name__]
sys.modules['app.data_store'] = sys.modules[__name__]
sys.modules['app.models'] = sys.modules[__name__]

# -----------------------------------------------------------------------------
# 8. Main Entrypoint
# -----------------------------------------------------------------------------
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'True').lower() in ['true', '1', 't']
    print("=" * 65)
    print("  MEDTRACK HEALTHCARE MANAGEMENT SYSTEM")
    print(f"  Local Access:      http://127.0.0.1:{port}")
    print(f"  Network / Cloud:   http://0.0.0.0:{port} (Port {port})")
    print("  Demo Doctor:       doctor@medtrack.com  /  Doctor@123")
    print("  Demo Patient:      patient@medtrack.com /  Patient@123")
    print("=" * 65)
    app.run(host='0.0.0.0', port=port, debug=debug)
