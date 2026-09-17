from flask import Flask, session
from config import Config
from app.data_store import DataStore

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Register Blueprints
    from app.public_routes import public_bp
    from app.auth import auth_bp
    from app.patient_routes import patient_bp
    from app.doctor_routes import doctor_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(patient_bp)
    app.register_blueprint(doctor_bp)

    # Context processor for global template variables
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

    return app
