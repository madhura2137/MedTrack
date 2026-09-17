import os
from app import create_app

app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'True').lower() in ['true', '1', 't']
    print("=" * 60)
    print("  MEDTRACK HEALTHCARE MANAGEMENT SYSTEM")
    print(f"  Local Server Starting on http://127.0.0.1:{port}")
    print("  Demo Doctor:  doctor@medtrack.com  /  Doctor@123")
    print("  Demo Patient: patient@medtrack.com /  Patient@123")
    print("=" * 60)
    app.run(host='127.0.0.1', port=port, debug=debug)
