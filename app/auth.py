from datetime import datetime
from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from app.data_store import DataStore
from app.models import User, generate_id

auth_bp = Blueprint('auth', __name__)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please sign in to access this page.", "warning")
            return redirect(url_for('auth.login', next=request.path))
        return f(*args, **kwargs)
    return decorated_function

def patient_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in as a patient to access this page.", "warning")
            return redirect(url_for('auth.login', next=request.path))
        if session.get('role') != 'patient':
            flash("Access restricted to registered patients.", "danger")
            return redirect(url_for('doctor.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def doctor_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in as a doctor to access this portal.", "warning")
            return redirect(url_for('auth.login', next=request.path))
        if session.get('role') != 'doctor':
            flash("Access restricted to licensed healthcare professionals.", "danger")
            return redirect(url_for('patient.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        if session.get('role') == 'doctor':
            return redirect(url_for('doctor.dashboard'))
        return redirect(url_for('patient.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember') == 'on'

        if not email or not password:
            flash("Please provide both email and password.", "danger")
            return render_template('auth/login.html', email=email)

        db = DataStore()
        user = db.get_user_by_email(email)

        if not user or not check_password_hash(user['password_hash'], password):
            flash("Invalid email or password. Please verify your credentials.", "danger")
            return render_template('auth/login.html', email=email)

        # Establish session
        session.clear()
        session['user_id'] = user['id']
        session['name'] = user['name']
        session['email'] = user['email']
        session['role'] = user['role']
        if remember:
            session.permanent = True

        flash(f"Welcome back, {user['name']}!", "success")

        next_page = request.args.get('next')
        if next_page and next_page.startswith('/'):
            return redirect(next_page)

        if user['role'] == 'doctor':
            return redirect(url_for('doctor.dashboard'))
        else:
            return redirect(url_for('patient.dashboard'))

    return render_template('auth/login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        if session.get('role') == 'doctor':
            return redirect(url_for('doctor.dashboard'))
        return redirect(url_for('patient.dashboard'))

    default_role = request.args.get('role', 'patient')

    if request.method == 'POST':
        role = request.form.get('role', 'patient').lower()
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        # Basic validations
        if not name or not email or not password or not phone:
            flash("All standard fields are required.", "danger")
            return render_template('auth/register.html', role=role, form=request.form)

        if len(password) < 8:
            flash("Password must be at least 8 characters long.", "danger")
            return render_template('auth/register.html', role=role, form=request.form)

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template('auth/register.html', role=role, form=request.form)

        db = DataStore()
        if db.get_user_by_email(email):
            flash("An account with this email address already exists. Please sign in.", "warning")
            return render_template('auth/register.html', role=role, form=request.form)

        profile_data = {}
        if role == 'patient':
            dob = request.form.get('date_of_birth', '').strip()
            if not dob:
                flash("Date of birth is required for patient registration.", "danger")
                return render_template('auth/register.html', role=role, form=request.form)

            # Calculate approximate age from DOB
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
                return render_template('auth/register.html', role=role, form=request.form)

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
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html', role=default_role)

@auth_bp.route('/logout')
def logout():
    name = session.get('name', 'User')
    session.clear()
    flash(f"You have been successfully signed out. Have a healthy day, {name}!", "info")
    return redirect(url_for('public.index'))
