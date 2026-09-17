from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from app.auth import patient_required
from app.data_store import DataStore
from app.models import Appointment, generate_id
from datetime import datetime, timedelta

patient_bp = Blueprint('patient', __name__, url_prefix='/patient')

@patient_bp.route('/dashboard')
@patient_required
def dashboard():
    user_id = session['user_id']
    db = DataStore()
    
    user = db.get_user_by_id(user_id)
    profile = db.get_patient_profile(user_id)
    appointments = db.get_patient_appointments(user_id)
    diagnoses = db.get_patient_diagnoses(user_id)
    unread_notifs = db.get_unread_count(user_id)
    unread_reports = db.get_unread_diagnosis_count(user_id)

    # Find the earliest upcoming appointment
    upcoming = [a for a in appointments if a['status'] in ['Confirmed', 'Pending']]
    next_appointment = upcoming[0] if upcoming else None

    # FR-03: Count of upcoming appointments, count of unread reports, count of unread notifications
    stats = {
        "total_appointments": len(appointments),
        "upcoming_count": len(upcoming),
        "reports_count": len(diagnoses),
        "unread_reports_count": unread_reports,
        "unread_notifications": unread_notifs
    }

    return render_template(
        'patient/dashboard.html',
        user=user,
        profile=profile,
        stats=stats,
        next_appointment=next_appointment,
        recent_diagnoses=diagnoses[:2]
    )

@patient_bp.route('/book-appointment', methods=['GET', 'POST'])
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
            return render_template('patient/book_appointment.html', doctors=doctors)

        # FR-04: Reason for visit is mandatory and limited to 500 characters
        if len(reason) > 500:
            flash("Reason for visit cannot exceed 500 characters.", "danger")
            return render_template('patient/book_appointment.html', doctors=doctors)

        # FR-04: Only future dates are selectable
        today_str = datetime.now().strftime("%Y-%m-%d")
        if date < today_str:
            flash("Consultation date must be today or in the future.", "danger")
            return render_template('patient/book_appointment.html', doctors=doctors)

        # FR-04: Time slots already booked for the selected doctor and date are not offered
        booked_slots = db.get_booked_slots(doctor_id, date)
        if time_slot in booked_slots:
            flash("This time slot has already been booked by another patient. Please select an alternate slot.", "danger")
            return render_template('patient/book_appointment.html', doctors=doctors, selected_doctor_id=doctor_id)

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
        return redirect(url_for('patient.appointments'))

    selected_doctor_id = request.args.get('doctor_id', '')
    return render_template('patient/book_appointment.html', doctors=doctors, selected_doctor_id=selected_doctor_id)

@patient_bp.route('/api/booked-slots')
@patient_required
def api_booked_slots():
    doctor_id = request.args.get('doctor_id')
    date_str = request.args.get('date')
    if not doctor_id or not date_str:
        return jsonify({"booked": []})
    db = DataStore()
    booked = db.get_booked_slots(doctor_id, date_str)
    return jsonify({"booked": booked})

@patient_bp.route('/appointments')
@patient_required
def appointments():
    user_id = session['user_id']
    db = DataStore()
    all_appts = db.get_patient_appointments(user_id)
    return render_template('patient/appointments.html', appointments=all_appts)

@patient_bp.route('/appointments/<appt_id>/cancel', methods=['POST'])
@patient_required
def cancel_appointment(appt_id):
    user_id = session['user_id']
    db = DataStore()
    appt = db.get_appointment_by_id(appt_id)

    if not appt or appt['patient_id'] != user_id:
        flash("Appointment not found or unauthorized.", "danger")
        return redirect(url_for('patient.appointments'))

    if appt['status'] == 'Completed':
        flash("Cannot cancel an already completed appointment.", "warning")
        return redirect(url_for('patient.appointments'))

    # FR-06: Cancellation is permitted no later than 24 hours before the scheduled time
    try:
        appt_datetime_str = f"{appt['date']} {appt['time_slot']}"
        appt_dt = datetime.strptime(appt_datetime_str, "%Y-%m-%d %I:%M %p")
        if appt_dt - datetime.now() < timedelta(hours=24):
            # Record status with notice note
            db.update_appointment_status(appt_id, "Cancelled", status_reason="Cancelled by patient (< 24h notice)")
            flash("Appointment cancelled. Notice: cancellation took place with less than 24 hours notice.", "warning")
            return redirect(url_for('patient.appointments'))
    except Exception:
        pass

    db.update_appointment_status(appt_id, "Cancelled", status_reason="Cancelled by patient.")
    flash("Appointment has been cancelled successfully.", "info")
    return redirect(url_for('patient.appointments'))

@patient_bp.route('/appointments/<appt_id>/reschedule', methods=['POST'])
@patient_required
def reschedule_appointment(appt_id):
    """Enforces FR-06: Reschedule request sets appointment back to Pending for doctor to confirm."""
    user_id = session['user_id']
    db = DataStore()
    appt = db.get_appointment_by_id(appt_id)

    if not appt or appt['patient_id'] != user_id:
        flash("Appointment not found or unauthorized.", "danger")
        return redirect(url_for('patient.appointments'))

    if appt['status'] == 'Completed':
        flash("Cannot reschedule an already completed appointment.", "warning")
        return redirect(url_for('patient.appointments'))

    new_date = request.form.get('new_date')
    new_slot = request.form.get('new_slot')

    if not new_date or not new_slot:
        flash("Please provide both a new date and time slot for rescheduling.", "danger")
        return redirect(url_for('patient.appointments'))

    # Check slot collision
    booked = db.get_booked_slots(appt['doctor_id'], new_date)
    if new_slot in booked:
        flash("Selected time slot is already booked for this doctor. Please pick another.", "danger")
        return redirect(url_for('patient.appointments'))

    db.reschedule_appointment(appt_id, new_date, new_slot)
    flash(f"Appointment rescheduled to {new_date} at {new_slot} and submitted for doctor re-confirmation.", "info")
    return redirect(url_for('patient.appointments'))

@patient_bp.route('/medical-history', methods=['GET', 'POST'])
@patient_required
def medical_history():
    user_id = session['user_id']
    db = DataStore()
    user = db.get_user_by_id(user_id)
    profile = db.get_patient_profile(user_id)
    diagnoses = db.get_patient_diagnoses(user_id)

    if request.method == 'POST':
        dob = request.form.get('date_of_birth', profile.get('date_of_birth', '2000-01-01'))
        blood_group = request.form.get('blood_group', 'Unknown')
        allergies = request.form.get('allergies', '').strip()
        conditions = request.form.get('conditions', '').strip()
        medications = request.form.get('medications', '').strip()
        emergency_contact = request.form.get('emergency_contact', '').strip()

        # Recalculate age if DOB supplied
        calculated_age = profile.get('age', 25)
        try:
            birth_year = int(dob.split('-')[0])
            calculated_age = max(1, datetime.now().year - birth_year)
        except Exception:
            pass

        db.update_patient_profile(
            user_id,
            date_of_birth=dob,
            age=calculated_age,
            blood_group=blood_group,
            allergies=allergies,
            conditions=conditions,
            medications=medications,
            medical_history=conditions,
            emergency_contact=emergency_contact
        )
        flash("Medical history updated successfully.", "success")
        return redirect(url_for('patient.medical_history'))

    return render_template('patient/medical_history.html', user=user, profile=profile, diagnoses=diagnoses)

@patient_bp.route('/diagnosis-reports')
@patient_required
def diagnosis_reports():
    user_id = session['user_id']
    db = DataStore()
    diagnoses = db.get_patient_diagnoses(user_id)
    return render_template('patient/diagnosis_reports.html', diagnoses=diagnoses)

@patient_bp.route('/diagnosis-reports/<diag_id>')
@patient_required
def view_diagnosis_report(diag_id):
    user_id = session['user_id']
    db = DataStore()
    report = db.get_diagnosis_by_id(diag_id)

    if not report or report['patient_id'] != user_id:
        flash("Report not found or unauthorized.", "danger")
        return redirect(url_for('patient.diagnosis_reports'))

    # FR-09: Opening a report clears its unread indicator on the dashboard
    db.mark_diagnosis_read(diag_id)

    return render_template('patient/diagnosis_detail.html', report=report)

@patient_bp.route('/notifications')
@patient_required
def notifications():
    user_id = session['user_id']
    db = DataStore()
    notifs = db.get_user_notifications(user_id)
    return render_template('patient/notifications.html', notifications=notifs)

@patient_bp.route('/notifications/<notif_id>/read', methods=['POST'])
@patient_required
def mark_read(notif_id):
    db = DataStore()
    db.mark_notification_as_read(notif_id)
    return redirect(url_for('patient.notifications'))

@patient_bp.route('/notifications/mark-all-read', methods=['POST'])
@patient_required
def mark_all_read():
    user_id = session['user_id']
    db = DataStore()
    db.mark_all_notifications_read(user_id)
    flash("All notifications marked as read.", "info")
    return redirect(url_for('patient.notifications'))

@patient_bp.route('/profile', methods=['GET', 'POST'])
@patient_required
def profile():
    user_id = session['user_id']
    db = DataStore()
    user = db.get_user_by_id(user_id)
    patient_prof = db.get_patient_profile(user_id)

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'update_info':
            name = request.form.get('name', '').strip()
            phone = request.form.get('phone', '').strip()
            if name:
                db.update_user(user_id, name=name, phone=phone)
                session['name'] = name
                flash("Profile details updated successfully.", "success")
            return redirect(url_for('patient.profile'))

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
            return redirect(url_for('patient.profile'))

    return render_template('patient/profile.html', user=user, profile=patient_prof)
