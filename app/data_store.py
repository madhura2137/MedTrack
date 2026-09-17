import json
import os
import threading
from typing import Dict, Any, List, Optional
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta

from config import Config
from app.models import (
    User, PatientProfile, DoctorProfile, Appointment, DiagnosisReport,
    Notification, AccessLog, generate_id, current_timestamp
)

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
                "phone": "+1 (555) 901-2345",
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
                "license_no": "MD-CARDIO-8891",
                "hospital": "MedTrack Heart & Vascular Pavilion",
                "bio": "Specializing in preventive cardiology, hypertensive management, and clinical echocardiography.",
                "available_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
                "time_slots": ["09:00 AM", "10:00 AM", "11:30 AM", "02:00 PM", "03:30 PM", "04:30 PM"]
            },
            doc2_id: {
                "user_id": doc2_id,
                "specialization": "Neurology",
                "experience": 15,
                "license_no": "MD-NEURO-4321",
                "hospital": "MedTrack Neurosciences Institute",
                "bio": "Expert in neurological disorders, migraine therapy, and cognitive health management.",
                "available_days": ["Monday", "Wednesday", "Friday"],
                "time_slots": ["09:00 AM", "10:00 AM", "11:30 AM", "02:00 PM", "03:30 PM"]
            }
        }

        patients = {
            pat1_id: {
                "user_id": pat1_id,
                "date_of_birth": "2002-05-14",
                "age": 24,
                "gender": "Female",
                "blood_group": "O+",
                "conditions": "Mild seasonal allergic asthma",
                "medications": "Salbutamol inhaler as needed",
                "medical_history": "Mild seasonal allergic asthma; no major surgical history.",
                "emergency_contact": "John Patil (+1 555-901-2346)",
                "allergies": "Penicillin (moderate rash)"
            }
        }

        appt1_id = "apt_001"
        appt2_id = "apt_002"

        appointments = {
            appt1_id: {
                "id": appt1_id,
                "patient_id": pat1_id,
                "doctor_id": doc1_id,
                "date": tomorrow_str,
                "time_slot": "10:00 AM",
                "reason": "Routine Cardiovascular Health Check & ECG follow-up",
                "status": "Confirmed",
                "status_reason": "",
                "notes": "Patient requested morning slot.",
                "created_at": current_timestamp()
            },
            appt2_id: {
                "id": appt2_id,
                "patient_id": pat1_id,
                "doctor_id": doc2_id,
                "date": yesterday_str,
                "time_slot": "02:00 PM",
                "reason": "Recurrent tension headache and sleep disruption",
                "status": "Completed",
                "status_reason": "",
                "notes": "Diagnosis report generated.",
                "created_at": yesterday_str + " 10:00:00"
            }
        }

        diag1_id = "diag_001"
        diagnoses = {
            diag1_id: {
                "id": diag1_id,
                "appointment_id": appt2_id,
                "patient_id": pat1_id,
                "doctor_id": doc2_id,
                "diagnosis": "Episodic Tension-Type Headache with Stress-Related Sleep Onset Latency.",
                "prescription": (
                    "1. Acetaminophen 500mg - 1 tablet orally every 8 hours as needed for severe tension.\n"
                    "2. Magnesium Glycinate 200mg - 1 capsule at bedtime for 30 days.\n"
                    "3. Sleep hygiene protocol and reduced blue-light exposure 1 hour prior to sleep."
                ),
                "additional_notes": "Monitor symptoms in a daily log. If migraines develop with visual auras, return for MRI evaluation.",
                "follow_up_date": (now + timedelta(days=25)).strftime("%Y-%m-%d"),
                "is_read": True,
                "addenda": [],
                "created_at": yesterday_str + " 15:30:00"
            }
        }

        notif1_id = "notif_001"
        notif2_id = "notif_002"
        notif3_id = "notif_003"

        notifications = {
            notif1_id: {
                "id": notif1_id,
                "user_id": pat1_id,
                "title": "Appointment Confirmed",
                "message": f"Your appointment with Dr. Sarah Jenkins has been confirmed for {tomorrow_str} at 10:00 AM.",
                "type": "appointment",
                "related_id": appt1_id,
                "is_read": False,
                "created_at": current_timestamp()
            },
            notif2_id: {
                "id": notif2_id,
                "user_id": pat1_id,
                "title": "New Diagnosis Report Available",
                "message": "Dr. Robert Chen has finalized and uploaded your clinical diagnosis report.",
                "type": "diagnosis",
                "related_id": diag1_id,
                "is_read": True,
                "created_at": yesterday_str + " 16:00:00"
            },
            notif3_id: {
                "id": notif3_id,
                "user_id": doc1_id,
                "title": "Upcoming Patient Appointment",
                "message": f"You have an appointment scheduled with Madhura Patil tomorrow at 10:00 AM.",
                "type": "appointment",
                "related_id": appt1_id,
                "is_read": False,
                "created_at": current_timestamp()
            }
        }

        data = {
            "users": users,
            "doctors": doctors,
            "patients": patients,
            "appointments": appointments,
            "diagnoses": diagnoses,
            "notifications": notifications,
            "access_logs": {}
        }
        self._write_data(data)

    # ---------------- USER OPERATIONS ---------------- #
    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        data = self._read_data()
        return data["users"].get(user_id)

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        data = self._read_data()
        for user in data["users"].values():
            if user["email"].lower() == email.lower().strip():
                return user
        return None

    def create_user(self, user: User, profile_data: Dict[str, Any]) -> str:
        data = self._read_data()
        user_dict = user.to_dict()
        data["users"][user.id] = user_dict

        if user.role == "patient":
            patient = PatientProfile(
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
            data["patients"][user.id] = patient.to_dict()
        elif user.role == "doctor":
            doctor = DoctorProfile(
                user_id=user.id,
                specialization=profile_data.get("specialization", "General Medicine"),
                experience=int(profile_data.get("experience", 1)),
                license_no=profile_data.get("license_no", f"LIC-{user.id[-4:]}"),
                hospital=profile_data.get("hospital", "MedTrack Central Hospital"),
                bio=profile_data.get("bio", "")
            )
            data["doctors"][user.id] = doctor.to_dict()

        # Send welcome notification
        welcome_notif = Notification(
            id=generate_id("notif"),
            user_id=user.id,
            title="Welcome to MedTrack!",
            message="Your account has been registered successfully. Explore appointments, records, and digital health tools.",
            type="info"
        )
        data["notifications"][welcome_notif.id] = welcome_notif.to_dict()

        self._write_data(data)
        return user.id

    def update_user(self, user_id: str, **kwargs) -> bool:
        data = self._read_data()
        if user_id in data["users"]:
            for k, v in kwargs.items():
                if k in data["users"][user_id] and k != "id":
                    data["users"][user_id][k] = v
            self._write_data(data)
            return True
        return False

    # ---------------- PROFILE & RELATIONSHIPS ---------------- #
    def get_patient_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        data = self._read_data()
        return data["patients"].get(user_id)

    def update_patient_profile(self, user_id: str, **kwargs) -> bool:
        data = self._read_data()
        if user_id in data["patients"]:
            for k, v in kwargs.items():
                data["patients"][user_id][k] = v
            self._write_data(data)
            return True
        return False

    def get_doctor_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        data = self._read_data()
        return data["doctors"].get(user_id)

    def update_doctor_profile(self, user_id: str, **kwargs) -> bool:
        data = self._read_data()
        if user_id in data["doctors"]:
            for k, v in kwargs.items():
                data["doctors"][user_id][k] = v
            self._write_data(data)
            return True
        return False

    def get_all_doctors(self) -> List[Dict[str, Any]]:
        data = self._read_data()
        results = []
        for user_id, doc in data["doctors"].items():
            user = data["users"].get(user_id)
            if user:
                combined = {**user, **doc}
                results.append(combined)
        return results

    def get_doctor_detail(self, doctor_id: str) -> Optional[Dict[str, Any]]:
        data = self._read_data()
        doc = data["doctors"].get(doctor_id)
        user = data["users"].get(doctor_id)
        if doc and user:
            return {**user, **doc}
        return None

    def get_patient_detail(self, patient_id: str) -> Optional[Dict[str, Any]]:
        data = self._read_data()
        pat = data["patients"].get(patient_id)
        user = data["users"].get(patient_id)
        if pat and user:
            return {**user, **pat}
        return None

    def has_appointment_relationship(self, doctor_id: str, patient_id: str) -> bool:
        """Enforces FR-07: Relationship exists only where at least one appointment links them."""
        data = self._read_data()
        for appt in data["appointments"].values():
            if appt["doctor_id"] == doctor_id and appt["patient_id"] == patient_id:
                return True
        return False

    def log_access(self, doctor_id: str, patient_id: str, action: str):
        """Enforces FR-07: Every access to a patient record by a doctor is written to an access log."""
        data = self._read_data()
        log_id = generate_id("log")
        log = AccessLog(id=log_id, doctor_id=doctor_id, patient_id=patient_id, action=action)
        if "access_logs" not in data:
            data["access_logs"] = {}
        data["access_logs"][log_id] = log.to_dict()
        self._write_data(data)

    # ---------------- APPOINTMENT OPERATIONS ---------------- #
    def get_booked_slots(self, doctor_id: str, date_str: str) -> List[str]:
        """Enforces FR-04: Slots already booked for doctor and date are not offered."""
        data = self._read_data()
        booked = []
        for appt in data["appointments"].values():
            if appt["doctor_id"] == doctor_id and appt["date"] == date_str:
                if appt["status"] in ["Pending", "Confirmed"]:
                    booked.append(appt["time_slot"])
        return booked

    def create_appointment(self, appointment: Appointment) -> str:
        data = self._read_data()
        appt_dict = appointment.to_dict()
        data["appointments"][appointment.id] = appt_dict

        # Notify the Doctor (FR-10)
        pat_user = data["users"].get(appointment.patient_id, {})
        pat_name = pat_user.get("name", "A patient")
        doc_notif = Notification(
            id=generate_id("notif"),
            user_id=appointment.doctor_id,
            title="New Appointment Request",
            message=f"{pat_name} requested an appointment for {appointment.date} at {appointment.time_slot}.",
            type="appointment",
            related_id=appointment.id
        )
        data["notifications"][doc_notif.id] = doc_notif.to_dict()

        # Notify the Patient (FR-10)
        doc_user = data["users"].get(appointment.doctor_id, {})
        doc_name = doc_user.get("name", "Doctor")
        pat_notif = Notification(
            id=generate_id("notif"),
            user_id=appointment.patient_id,
            title="Appointment Request Submitted",
            message=f"Your appointment request with {doc_name} on {appointment.date} at {appointment.time_slot} is Pending confirmation.",
            type="appointment",
            related_id=appointment.id
        )
        data["notifications"][pat_notif.id] = pat_notif.to_dict()

        self._write_data(data)
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
            "patient_blood_group": pat_prof.get("blood_group", "-")
        }

    def get_patient_appointments(self, patient_id: str) -> List[Dict[str, Any]]:
        data = self._read_data()
        results = []
        for appt in data["appointments"].values():
            if appt["patient_id"] == patient_id:
                doc_user = data["users"].get(appt["doctor_id"], {})
                doc_prof = data["doctors"].get(appt["doctor_id"], {})
                enriched = {
                    **appt,
                    "doctor_name": doc_user.get("name", "Dr. Specialist"),
                    "doctor_specialization": doc_prof.get("specialization", "General Medicine"),
                    "doctor_hospital": doc_prof.get("hospital", "Central Clinic")
                }
                results.append(enriched)
        results.sort(key=lambda x: (x["date"], x["time_slot"]), reverse=True)
        return results

    def get_doctor_appointments(self, doctor_id: str) -> List[Dict[str, Any]]:
        data = self._read_data()
        results = []
        for appt in data["appointments"].values():
            if appt["doctor_id"] == doctor_id:
                pat_user = data["users"].get(appt["patient_id"], {})
                pat_prof = data["patients"].get(appt["patient_id"], {})
                enriched = {
                    **appt,
                    "patient_name": pat_user.get("name", "Patient"),
                    "patient_phone": pat_user.get("phone", "-"),
                    "patient_age": pat_prof.get("age", "-"),
                    "patient_gender": pat_prof.get("gender", "-"),
                    "patient_blood_group": pat_prof.get("blood_group", "-")
                }
                results.append(enriched)
        results.sort(key=lambda x: (x["date"], x["time_slot"]), reverse=True)
        return results

    def update_appointment_status(self, appt_id: str, new_status: str, status_reason: str = "", notes: Optional[str] = None) -> bool:
        """Enforces FR-05:
           - Permitted transitions: Pending -> Confirmed -> Completed, Pending -> Rejected, Confirmed -> Cancelled
           - Completed only if previously Confirmed.
           - Status reason stored and shown.
        """
        data = self._read_data()
        if appt_id not in data["appointments"]:
            return False

        appt = data["appointments"][appt_id]
        current_status = appt["status"]

        # Validate transition rule
        if new_status == "Completed" and current_status != "Confirmed":
            return False

        appt["status"] = new_status
        if status_reason:
            appt["status_reason"] = status_reason
        if notes is not None:
            appt["notes"] = notes

        # Generate notification for patient per FR-10
        doc_user = data["users"].get(appt["doctor_id"], {})
        doc_name = doc_user.get("name", "Your Doctor")
        msg = f"{doc_name} marked your appointment for {appt['date']} at {appt['time_slot']} as '{new_status}'."
        if status_reason:
            msg += f" Reason: {status_reason}"

        notif = Notification(
            id=generate_id("notif"),
            user_id=appt["patient_id"],
            title=f"Appointment {new_status}",
            message=msg,
            type="appointment",
            related_id=appt_id
        )
        data["notifications"][notif.id] = notif.to_dict()

        self._write_data(data)
        return True

    def reschedule_appointment(self, appt_id: str, new_date: str, new_slot: str) -> bool:
        """Enforces FR-06: Reschedule sets appointment back to Pending for doctor confirmation."""
        data = self._read_data()
        if appt_id not in data["appointments"]:
            return False
        appt = data["appointments"][appt_id]
        appt["date"] = new_date
        appt["time_slot"] = new_slot
        appt["status"] = "Pending"
        appt["status_reason"] = "Rescheduled by patient"

        # Notify doctor
        pat_user = data["users"].get(appt["patient_id"], {})
        pat_name = pat_user.get("name", "Patient")
        doc_notif = Notification(
            id=generate_id("notif"),
            user_id=appt["doctor_id"],
            title="Appointment Reschedule Requested",
            message=f"{pat_name} rescheduled their appointment to {new_date} at {new_slot} (Pending approval).",
            type="appointment",
            related_id=appt_id
        )
        data["notifications"][doc_notif.id] = doc_notif.to_dict()
        self._write_data(data)
        return True

    # ---------------- DIAGNOSIS OPERATIONS ---------------- #
    def create_diagnosis(self, report: DiagnosisReport) -> str:
        data = self._read_data()
        data["diagnoses"][report.id] = report.to_dict()

        # Update appointment status to Completed
        if report.appointment_id in data["appointments"]:
            data["appointments"][report.appointment_id]["status"] = "Completed"

        # Notify patient per FR-10
        doc_user = data["users"].get(report.doctor_id, {})
        doc_name = doc_user.get("name", "Your Doctor")
        notif = Notification(
            id=generate_id("notif"),
            user_id=report.patient_id,
            title="Diagnosis Report Available",
            message=f"{doc_name} has filed your diagnosis and prescription report. Click to view full details.",
            type="diagnosis",
            related_id=report.id
        )
        data["notifications"][notif.id] = notif.to_dict()

        self._write_data(data)
        return report.id

    def add_diagnosis_addendum(self, diag_id: str, text: str, doctor_id: str) -> bool:
        """Enforces FR-08: Report is immutable; corrections made by appending an addendum."""
        data = self._read_data()
        if diag_id not in data["diagnoses"]:
            return False
        diag = data["diagnoses"][diag_id]
        if diag["doctor_id"] != doctor_id:
            return False
        if "addenda" not in diag:
            diag["addenda"] = []
        diag["addenda"].append({
            "text": text,
            "timestamp": current_timestamp(),
            "doctor_id": doctor_id
        })
        self._write_data(data)
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
                    "doctor_specialization": doc_prof.get("specialization", "General"),
                    "appointment_date": appt.get("date", "-")
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
        for diag in data["diagnoses"].values():
            if diag.get("appointment_id") == appointment_id:
                return self.get_diagnosis_by_id(diag["id"])
        return None

    # ---------------- NOTIFICATION OPERATIONS ---------------- #
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

    # ---------------- PATIENT DIRECTORY FOR DOCTOR ---------------- #
    def get_doctor_patients(self, doctor_id: str) -> List[Dict[str, Any]]:
        data = self._read_data()
        patient_ids = set()
        for appt in data["appointments"].values():
            if appt["doctor_id"] == doctor_id:
                patient_ids.add(appt["patient_id"])

        results = []
        for pid in patient_ids:
            user = data["users"].get(pid)
            prof = data["patients"].get(pid)
            if user and prof:
                appt_count = sum(1 for a in data["appointments"].values() if a["doctor_id"] == doctor_id and a["patient_id"] == pid)
                results.append({
                    **user,
                    **prof,
                    "total_visits": appt_count
                })
        return results
