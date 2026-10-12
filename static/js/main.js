// MedTrack Frontend JavaScript Utilities

document.addEventListener('DOMContentLoaded', function () {
    // 0. Theme Switcher (Light / Dark Mode)
    function getCurrentTheme() {
        return document.documentElement.getAttribute('data-bs-theme') || 'light';
    }

    function updateThemeUI(theme) {
        document.querySelectorAll('.theme-toggle-btn').forEach(btn => {
            const icon = btn.querySelector('i');
            if (icon) {
                if (theme === 'dark') {
                    icon.className = 'bi bi-sun-fill text-warning';
                    btn.setAttribute('title', 'Switch to Light Mode');
                } else {
                    icon.className = 'bi bi-moon-stars-fill text-dark';
                    btn.setAttribute('title', 'Switch to Dark Mode');
                }
            }
        });
    }

    function toggleTheme() {
        const current = getCurrentTheme();
        const nextTheme = current === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-bs-theme', nextTheme);
        document.documentElement.setAttribute('data-theme', nextTheme);
        localStorage.setItem('medtrack-theme', nextTheme);
        updateThemeUI(nextTheme);
    }

    // Initialize toggle icons on load
    updateThemeUI(getCurrentTheme());

    // Bind click handlers to theme toggle buttons
    document.querySelectorAll('.theme-toggle-btn').forEach(btn => {
        btn.addEventListener('click', toggleTheme);
    });

    // 1. Role Toggle Handler on Registration Page
    const roleRadios = document.querySelectorAll('input[name="role"]');
    const patientFields = document.getElementById('patient-specific-fields');
    const doctorFields = document.getElementById('doctor-specific-fields');

    function toggleRoleFields() {
        if (!roleRadios.length) return;
        const selectedRole = document.querySelector('input[name="role"]:checked')?.value || 'patient';
        if (selectedRole === 'doctor') {
            if (patientFields) patientFields.style.display = 'none';
            if (doctorFields) doctorFields.style.display = 'block';
        } else {
            if (patientFields) patientFields.style.display = 'block';
            if (doctorFields) doctorFields.style.display = 'none';
        }
    }

    if (roleRadios.length) {
        roleRadios.forEach(radio => radio.addEventListener('change', toggleRoleFields));
        toggleRoleFields(); // initialize on load
    }

    // 2. Doctor Filter Selection in Book Appointment
    const doctorSelect = document.getElementById('doctor-select');
    const doctorCardInfo = document.getElementById('selected-doctor-info');
    if (doctorSelect && doctorCardInfo) {
        doctorSelect.addEventListener('change', function () {
            const selectedOpt = doctorSelect.options[doctorSelect.selectedIndex];
            if (selectedOpt && selectedOpt.value) {
                const spec = selectedOpt.getAttribute('data-spec') || '';
                const hospital = selectedOpt.getAttribute('data-hospital') || '';
                const exp = selectedOpt.getAttribute('data-exp') || '';
                doctorCardInfo.innerHTML = `
                    <div class="p-3 bg-light rounded border mt-2">
                        <h6 class="mb-1 text-primary fw-bold">${selectedOpt.text}</h6>
                        <div class="small text-muted mb-1"><i class="bi bi-award me-1"></i> Specialization: <strong>${spec}</strong> (${exp} yrs exp)</div>
                        <div class="small text-muted"><i class="bi bi-geo-alt me-1"></i> Hospital: ${hospital}</div>
                    </div>
                `;
                doctorCardInfo.style.display = 'block';
            } else {
                doctorCardInfo.style.display = 'none';
            }
        });
        // Trigger if pre-selected
        if (doctorSelect.value) {
            doctorSelect.dispatchEvent(new Event('change'));
        }
    }

    // 3. Time Slot Picker Buttons
    const slotButtons = document.querySelectorAll('.slot-option-btn');
    const slotInput = document.getElementById('time-slot-input');
    if (slotButtons.length && slotInput) {
        slotButtons.forEach(btn => {
            btn.addEventListener('click', function () {
                slotButtons.forEach(b => b.classList.remove('active', 'btn-primary'));
                slotButtons.forEach(b => b.classList.add('btn-outline-primary'));
                btn.classList.add('active', 'btn-primary');
                btn.classList.remove('btn-outline-primary');
                slotInput.value = btn.getAttribute('data-slot');
            });
        });
    }

    // 4. Auto-dismiss alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert-dismissible');
    alerts.forEach(alert => {
        setTimeout(() => {
            const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            if (bsAlert) {
                bsAlert.close();
            }
        }, 5000);
    });
});
