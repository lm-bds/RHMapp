# System Metadata & Developer Manual

## 1. System Components

The **Remote Patient Monitoring (RHMapp)** system is divided into three primary components:

### A. The Clinical Command Center (Backend & Frontend)
- **Framework:** FastAPI (Python 3.9+)
- **Templating:** Jinja2 + HTMX (Server-Side Rendered, No JS framework)
- **Styling:** Tailwind CSS (via CDN) utilizing the "Modern Warm Earth" design system.
- **Database:** SQLAlchemy 2.0. (Currently using SQLite for prototyping; configured for PostgreSQL in production).
- **Core Functionality:** 
  - High-density, triage-sorted dashboard.
  - Comprehensive Electronic Health Record (EHR) compliant with Australian standards (NHDD).
  - Background asynchronous task processing for clinical alerting and reminders.

### B. The Patient Kiosk (Mobile)
- **Framework:** React Native / Expo (SDK 54)
- **Role:** A radically simple, locked-down interface designed for elderly patients (90+).
- **Core Functionality:** 
  - Passwordless authentication via QR code scanning.
  - Dynamic task execution (Vitals collection and Questionnaire responses).

### C. The Database (Schema)
- **Patients:** Core demographics and health identifiers.
- **Vitals:** Time-series physiological data (Weight, BP, SpO2, HR).
- **Events:** Longitudinal clinical timeline (Hospitalisations, Appointments).
- **PatientNotes:** Clinician-authored structured notes.
- **Documents:** Metadata store for external files (Referrals, Imaging).
- **DeviceTokens:** Secure JWT mappings tying physical devices to specific patient records.

---

## 2. Essential Commands

### Backend Operations
Ensure you are in the root directory (`/RMPapp`) and your virtual environment is activated before running backend commands.

**Activate Virtual Environment:**
```bash
source venv/bin/activate
```

**Run the Server (Development):**
```bash
uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload
```
*The server is accessible at `http://localhost:8000`. The clinician dashboard is at `/dashboard`.*

**Reset & Re-seed Database:**
If the schema changes or you need fresh demo data (generates 50 Australian patients):
```bash
rm -f rpm_db.db && python3 seed_data.py
```

### Mobile Operations
Ensure you are inside the `/mobile` directory.

**Start the Expo Development Server:**
```bash
cd mobile
npx expo start
```
*Use the Expo Go app on your physical device to scan the generated QR code.*

**Clear Cache & Reinstall Dependencies (Troubleshooting):**
```bash
cd mobile
rm -rf node_modules package-lock.json
npm install --legacy-peer-deps
npx expo start -c
```

---

## 3. Configuration & Environment Variables

The system relies on specific environment variables for security and configuration. A template is provided in `.env.example`.

| Variable | Description | Default / Dev Value |
| :--- | :--- | :--- |
| `DATABASE_URL` | Connection string for SQLAlchemy. | `sqlite:///./rpm_db.db` |
| `SECRET_KEY` | Key used to sign JWTs for devices and staff. | `super-secret-key-change-me` |
| `ALGORITHM` | JWT signing algorithm. | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token lifespan. | `43200` (30 days) |

*Note: The mobile application (`mobile/App.js`) requires `API_BASE_URL` to be hardcoded to your local machine's IP address during development (e.g., `http://192.168.1.110:8000/api/v1`).*

---

## 4. Workflows & Lifecycle

### Patient Onboarding
1. Clinician clicks "+ Add New Patient" on the dashboard.
2. Fills out the Australian clinical specification form.
3. Clicks "Link Mobile Device (QR)" in the new patient's EHR to generate a binding token.
4. Patient scans the QR code using the mobile app to securely bind their device.

### Daily Vitals Collection
1. Mobile app fetches `/api/v1/tasks/today` and presents tasks to the patient.
2. Patient submits data to `/api/v1/tasks/submit`.
3. Backend saves the data and fires an async `evaluate_patient_vitals` task.
4. If a threshold is breached (e.g., Weight Spike ≥ 2.0kg), an alert is logged and the patient is pushed to the top of the Triage Dashboard.

### Clinical Triage
1. Clinician reviews the "URGENT" patients at the top of the dashboard.
2. Clinician clicks "ACK", provides a clinical rationale (e.g., "Patient Contacted", "Med Adjusted").
3. The vital sign is marked as acknowledged, an Event is logged in the EHR, and the patient is filtered out of the active triage view.
