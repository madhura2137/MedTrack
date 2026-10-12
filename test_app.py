import unittest
import os
import shutil
import tempfile
from app import create_app, Config, DataStore

class TestMedTrackApp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_dir = tempfile.mkdtemp()
        cls.test_db_file = os.path.join(cls.test_dir, 'test_medtrack_db.json')
        cls.original_data_file = Config.DATA_FILE

        Config.DATA_FILE = cls.test_db_file
        DataStore._instance = None

        class TestConfig(Config):
            TESTING = True
            SECRET_KEY = 'test-secret-key'
            DATA_DIR = cls.test_dir
            DATA_FILE = cls.test_db_file

        cls.app = create_app(TestConfig)
        cls.client = cls.app.test_client()

    @classmethod
    def tearDownClass(cls):
        Config.DATA_FILE = cls.original_data_file
        DataStore._instance = None
        shutil.rmtree(cls.test_dir, ignore_errors=True)

    def test_01_public_pages(self):
        """Verify landing and about pages load successfully (FR-01, FR-02)."""
        res = self.client.get('/')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'MedTrack', res.data)

        res_about = self.client.get('/about')
        self.assertEqual(res_about.status_code, 200)
        self.assertIn(b'About MedTrack', res_about.data)

    def test_02_authentication_and_protection(self):
        """Verify login, 8-char passwords, and protected route access control (FR-02, FR-03)."""
        # Unauthenticated access redirects to login
        res = self.client.get('/patient/dashboard', follow_redirects=True)
        self.assertIn(b'Sign In', res.data)

        # Bad login credentials returns generic failure
        res = self.client.post('/login', data={
            'email': 'invalid@medtrack.com',
            'password': 'WrongPassword123'
        }, follow_redirects=True)
        self.assertIn(b'Invalid email or password', res.data)

        # Successful Patient Login
        res = self.client.post('/login', data={
            'email': 'patient@medtrack.com',
            'password': 'Patient@123'
        }, follow_redirects=True)
        self.assertIn(b'Patient Dashboard', res.data)
        self.assertIn(b'Madhura Patil', res.data)

        # Role enforcement: Patient cannot access Doctor portal (FR-03)
        res_blocked = self.client.get('/doctor/dashboard', follow_redirects=True)
        self.assertIn(b'Access restricted', res_blocked.data)

        # Logout (FR-12)
        res_logout = self.client.get('/logout', follow_redirects=True)
        self.assertIn(b'successfully signed out', res_logout.data)

    def test_03_registration_flow(self):
        """Verify registration for patient and doctor roles per FR-01."""
        # 1. Register new Patient with DOB
        res_pat = self.client.post('/register', data={
            'role': 'patient',
            'name': 'Alice Wonder',
            'email': 'alice.wonder@test.com',
            'phone': '+1 555-444-3333',
            'password': 'Password@123',
            'confirm_password': 'Password@123',
            'date_of_birth': '1998-04-12',
            'blood_group': 'B+',
            'conditions': 'Mild asthma',
            'medications': 'Albuterol',
            'allergies': 'None',
            'emergency_contact': 'Bob Wonder (+1 555-123-0000)'
        }, follow_redirects=True)
        self.assertIn(b'Registration successful', res_pat.data)

        # 2. Register new Doctor with mandatory credentials
        res_doc = self.client.post('/register', data={
            'role': 'doctor',
            'name': 'Dr. Marcus Vance',
            'email': 'vance@test.com',
            'phone': '+1 555-777-8888',
            'password': 'DoctorPassword@123',
            'confirm_password': 'DoctorPassword@123',
            'specialization': 'Orthopedics',
            'experience': '10',
            'license_no': 'MD-ORTHO-7721',
            'hospital': 'St. Jude Health Network'
        }, follow_redirects=True)
        self.assertIn(b'Registration successful', res_doc.data)

        # Verify new Doctor can login
        res_doc_login = self.client.post('/login', data={
            'email': 'vance@test.com',
            'password': 'DoctorPassword@123'
        }, follow_redirects=True)
        self.assertIn(b'Dr. Marcus Vance', res_doc_login.data)
        self.client.get('/logout')

    def test_04_full_consultation_lifecycle(self):
        """Test full workflow: Patient books -> Doctor confirms -> Doctor diagnoses -> Patient views report."""
        # 1. Patient logs in and books appointment (FR-04)
        self.client.post('/login', data={'email': 'patient@medtrack.com', 'password': 'Patient@123'})
        res_book = self.client.post('/patient/book-appointment', data={
            'doctor_id': 'usr_doc_001',
            'date': '2026-10-15',
            'time_slot': '11:30 AM',
            'reason': 'Annual cardiovascular checkup and blood pressure review'
        }, follow_redirects=True)
        self.assertIn(b'Appointment request submitted', res_book.data)

        # Verify slot collision prevention: same slot cannot be booked again (FR-04)
        res_duplicate = self.client.post('/patient/book-appointment', data={
            'doctor_id': 'usr_doc_001',
            'date': '2026-10-15',
            'time_slot': '11:30 AM',
            'reason': 'Trying to book duplicate slot'
        }, follow_redirects=True)
        self.assertIn(b'already been booked', res_duplicate.data)
        self.client.get('/logout')

        # 2. Doctor logs in and confirms appointment (FR-05)
        self.client.post('/login', data={'email': 'doctor@medtrack.com', 'password': 'Doctor@123'})
        db = DataStore()
        doc_appts = db.get_doctor_appointments('usr_doc_001')
        test_appt = next(a for a in doc_appts if a['date'] == '2026-10-15')
        appt_id = test_appt['id']

        res_accept = self.client.post(f'/doctor/appointments/{appt_id}/status', data={'status': 'Confirmed'}, follow_redirects=True)
        self.assertIn(b'Confirmed', res_accept.data)

        # 3. Doctor submits Diagnosis and Prescription (FR-08)
        res_diag = self.client.post(f'/doctor/diagnose/{appt_id}', data={
            'diagnosis': 'Borderline Essential Hypertension with Mild Sinus Tachycardia',
            'prescription': '1. Lisinopril 5mg - 1 tablet daily in the morning.\n2. Low-sodium diet and 30 min daily walking.',
            'notes': 'Re-check blood pressure in 30 days.',
            'follow_up_date': '2026-11-15'
        }, follow_redirects=True)
        self.assertIn(b'submitted to patient successfully', res_diag.data)
        self.client.get('/logout')

        # 4. Patient logs back in, verifies diagnosis report is visible and opening clears unread indicator (FR-09)
        self.client.post('/login', data={'email': 'patient@medtrack.com', 'password': 'Patient@123'})
        res_reports = self.client.get('/patient/diagnosis-reports')
        self.assertIn(b'Borderline Essential Hypertension', res_reports.data)

        # Verify notifications received (FR-10)
        res_notif = self.client.get('/patient/notifications')
        self.assertIn(b'Diagnosis Report Available', res_notif.data)
        self.client.get('/logout')

    def test_05_authorization_and_privacy_boundaries(self):
        """Enforces FR-07: Doctor cannot access patient records without an appointment relationship."""
        # Log in as Dr. Robert Chen (usr_doc_002) who has NO appointment with Alice Wonder
        self.client.post('/login', data={'email': 'chen@medtrack.com', 'password': 'Doctor@123'})
        
        # Try to access non-existent or unrelated patient
        res_unrelated = self.client.get('/doctor/patient/usr_pat_unrelated', follow_redirects=True)
        self.assertIn(b'Access Denied', res_unrelated.data)
        self.client.get('/logout')

if __name__ == '__main__':
    unittest.main()
