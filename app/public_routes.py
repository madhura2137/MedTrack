from flask import Blueprint, render_template, redirect, url_for, session
from app.data_store import DataStore

public_bp = Blueprint('public', __name__)

@public_bp.route('/')
def index():
    if 'user_id' in session:
        if session.get('role') == 'doctor':
            return redirect(url_for('doctor.dashboard'))
        return redirect(url_for('patient.dashboard'))

    db = DataStore()
    doctors = db.get_all_doctors()[:4]
    return render_template('public/index.html', doctors=doctors)

@public_bp.route('/about')
def about():
    return render_template('public/about.html')
