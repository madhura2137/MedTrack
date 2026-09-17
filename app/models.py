from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
import uuid
from datetime import datetime

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
        "09:00 AM", "10:00 AM", "11:00 AM", "02:00 PM", "03:00 PM", "04:00 PM"
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
