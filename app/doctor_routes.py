from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from app.auth import doctor_required
from app.data_store import DataStore
from app.models import DiagnosisReport, generate_id
from datetime import datetime

doctor_bp = Blueprint('doctor', __name__, url_prefix='/doctor')

@doctor_bp.route('/dashboard')
@doctor_required
def dashboard():
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
    # FR-03: Count of appointments awaiting a diagnosis report (Confirmed appointments)
    awaiting_report = [a for a in appointments if a['status'] == 'Confirmed']

    stats = {
        "today_appointments_count": len(today_appointments),
        "total_patients_count": len(patients),
        "pending_requests_count": len(pending_appointments),
        "awaiting_report_count": len(awaiting_report),
        "unread_notifications": unread_notifs
    }

    return render_template(
        'doctor/dashboard.html',
        user=user,
        profile=profile,
        stats=stats,
        today_appointments=today_appointments,
        recent_appointments=appointments[:5]
    )

@doctor_bp.route('/appointments')
@doctor_required
def appointments():
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

    return render_template('doctor/appointments.html', appointments=filtered, current_filter=filter_status, filter_date=filter_date)

@doctor_bp.route('/appointments/<appt_id>/status', methods=['POST'])
@doctor_required
def update_status(appt_id):
    user_id = session['user_id']
    db = DataStore()
    appt = db.get_appointment_by_id(appt_id)

    if not appt or appt['doctor_id'] != user_id:
        flash("Appointment not found or unauthorized.", "danger")
        return redirect(url_for('doctor.appointments'))

    new_status = request.form.get('status')
    status_reason = request.form.get('status_reason', '').strip()

    # FR-05: Rejecting or cancelling requires a reason
    if new_status in ['Rejected', 'Cancelled'] and not status_reason:
        status_reason = "Clinical schedule conflict / doctor unavailability"

    # FR-05: An appointment cannot move to Completed unless it was previously Confirmed
    if new_status == 'Completed' and appt['status'] != 'Confirmed':
        flash("An appointment cannot move to Completed unless it was previously Confirmed.", "danger")
        return redirect(request.referrer or url_for('doctor.appointments'))

    if new_status in ['Confirmed', 'Rejected', 'Cancelled', 'Completed']:
        success = db.update_appointment_status(appt_id, new_status, status_reason=status_reason)
        if success:
            flash(f"Appointment status updated to '{new_status}'.", "success")
        else:
            flash("Invalid status transition.", "danger")
    else:
        flash("Invalid status choice.", "danger")

    return redirect(request.referrer or url_for('doctor.appointments'))

@doctor_bp.route('/patients')
@doctor_required
def patients():
    user_id = session['user_id']
    db = DataStore()
    patient_list = db.get_doctor_patients(user_id)
    return render_template('doctor/patients.html', patients=patient_list)

@doctor_bp.route('/patient/<patient_id>')
@doctor_required
def patient_detail(patient_id):
    doctor_id = session['user_id']
    db = DataStore()

    # FR-07: A doctor with no appointment relationship to a patient cannot retrieve that patient's history by any route
    if not db.has_appointment_relationship(doctor_id, patient_id):
        flash("Access Denied: You are only permitted to view records of patients who have an active or past appointment with you.", "danger")
        return redirect(url_for('doctor.patients'))

    patient_info = db.get_patient_detail(patient_id)
    if not patient_info:
        flash("Patient not found.", "danger")
        return redirect(url_for('doctor.patients'))

    # FR-07: Every access to a patient record by a doctor is written to an access log
    db.log_access(doctor_id, patient_id, 'view_patient_history')

    all_diagnoses = db.get_patient_diagnoses(patient_id)
    patient_appts = [a for a in db.get_patient_appointments(patient_id) if a['doctor_id'] == doctor_id]

    return render_template(
        'doctor/patient_detail.html',
        patient=patient_info,
        diagnoses=all_diagnoses,
        appointments=patient_appts
    )

@doctor_bp.route('/diagnose/<appt_id>', methods=['GET', 'POST'])
@doctor_required
def diagnose(appt_id):
    doctor_id = session['user_id']
    db = DataStore()
    appt = db.get_appointment_by_id(appt_id)

    # FR-08: A report cannot be submitted against an appointment belonging to another doctor
    if not appt or appt['doctor_id'] != doctor_id:
        flash("Appointment not found or unauthorized.", "danger")
        return redirect(url_for('doctor.appointments'))

    # FR-08: Exactly one report may exist per appointment
    existing = db.get_diagnosis_by_appointment(appt_id)
    if existing and request.method == 'GET':
        return render_template('doctor/diagnosis_view.html', appt=appt, diagnosis=existing)

    if request.method == 'POST':
        diagnosis_text = request.form.get('diagnosis', '').strip()
        prescription = request.form.get('prescription', '').strip()
        notes = request.form.get('notes', '').strip()
        follow_up_date = request.form.get('follow_up_date', '').strip()

        # FR-08: Diagnosis text is mandatory; prescription and notes are optional
        if not diagnosis_text:
            flash("Clinical diagnosis description is mandatory.", "danger")
            return render_template('doctor/diagnosis_form.html', appt=appt)

        report_id = generate_id("diag")
        report = DiagnosisReport(
            id=report_id,
            appointment_id=appt_id,
            patient_id=appt['patient_id'],
            doctor_id=doctor_id,
            diagnosis=diagnosis_text,
            prescription=prescription,
            additional_notes=notes,
            follow_up_date=follow_up_date
        )
        db.create_diagnosis(report)

        flash("Clinical diagnosis report saved and submitted to patient successfully!", "success")
        return redirect(url_for('doctor.patient_detail', patient_id=appt['patient_id']))

    return render_template('doctor/diagnosis_form.html', appt=appt)

@doctor_bp.route('/diagnose/<diag_id>/addendum', methods=['POST'])
@doctor_required
def add_addendum(diag_id):
    """Enforces FR-08: A submitted report is immutable; corrections are made by appending an addendum."""
    doctor_id = session['user_id']
    db = DataStore()
    addendum_text = request.form.get('addendum_text', '').strip()

    if not addendum_text:
        flash("Addendum text cannot be empty.", "warning")
        return redirect(request.referrer or url_for('doctor.appointments'))

    success = db.add_diagnosis_addendum(diag_id, addendum_text, doctor_id)
    if success:
        flash("Clinical addendum appended successfully to the permanent record.", "success")
    else:
        flash("Unauthorized or report not found.", "danger")

    return redirect(request.referrer or url_for('doctor.appointments'))

@doctor_bp.route('/notifications')
@doctor_required
def notifications():
    user_id = session['user_id']
    db = DataStore()
    notifs = db.get_user_notifications(user_id)
    return render_template('doctor/notifications.html', notifications=notifs)

@doctor_bp.route('/notifications/<notif_id>/read', methods=['POST'])
@doctor_required
def mark_read(notif_id):
    db = DataStore()
    db.mark_notification_as_read(notif_id)
    return redirect(url_for('doctor.notifications'))

@doctor_bp.route('/notifications/mark-all-read', methods=['POST'])
@doctor_required
def mark_all_read():
    user_id = session['user_id']
    db = DataStore()
    db.mark_all_notifications_read(user_id)
    flash("All notifications marked as read.", "info")
    return redirect(url_for('doctor.notifications'))

@doctor_bp.route('/profile', methods=['GET', 'POST'])
@doctor_required
def profile():
    user_id = session['user_id']
    db = DataStore()
    user = db.get_user_by_id(user_id)
    doctor_prof = db.get_doctor_profile(user_id)

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'update_info':
            name = request.form.get('name', '').strip()
            phone = request.form.get('phone', '').strip()
            specialization = request.form.get('specialization', '').strip()
            experience = request.form.get('experience', 1)
            hospital = request.form.get('hospital', '').strip()
            bio = request.form.get('bio', '').strip()

            if name:
                db.update_user(user_id, name=name, phone=phone)
                session['name'] = name

            db.update_doctor_profile(
                user_id,
                specialization=specialization,
                experience=int(experience) if experience else 1,
                hospital=hospital,
                bio=bio
            )
            flash("Doctor profile updated successfully.", "success")
            return redirect(url_for('doctor.profile'))

        elif action == 'change_password':
            current_pwd = request.form.get('current_password', '')
            new_pwd = request.form.get('new_password', '')
            confirm_pwd = request.form.get('confirm_password', '')

            if not check_password_hash(user['password_hash'], current_pwd):
                flash("Current password incorrect.", "danger")
            elif len(new_pwd) < 8:
                flash("New password must be at least 8 characters.", "danger")
            elif new_pwd != confirm_pwd:
                flash("New passwords do not match.", "danger")
            else:
                db.update_user(user_id, password_hash=generate_password_hash(new_pwd))
                flash("Password changed successfully.", "success")
            return redirect(url_for('doctor.profile'))

    return render_template('doctor/profile.html', user=user, profile=doctor_prof)
