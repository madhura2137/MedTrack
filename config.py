import os
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    """Base application configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'medtrack-super-secret-key-2026-prod-ready')
    DATA_DIR = os.path.join(BASE_DIR, 'data')
    DATA_FILE = os.path.join(DATA_DIR, 'medtrack_db.json')
    # FR-02: Sessions expire after 30 minutes of inactivity
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    APP_NAME = "MedTrack"
    APP_TAGLINE = "Cloud-enabled healthcare management made simple."
