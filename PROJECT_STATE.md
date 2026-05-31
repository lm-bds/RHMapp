# Project Master State: RHMapp (Australian RPM)

## Core Knowledge Persistence
This system is an Australian-compliant Remote Patient Monitoring (RPM) portal. It is designed for cardiovascular super-agers and high-throughput clinician workflows.

### **Current Development Status:**
- [x] **Backend:** API and Clinical Logic complete.
- [x] **Database:** Australian-compliant schema (Postgres-ready).
- [x] **UI Overhaul:** "Modern Warm Earth" design system applied.
- [x] **Triage Dashboard:** Searchable, acuity-sorted, unacknowledged-only by default.
- [x] **EHR:** Tabbed workspace with pinned trend graphs and right-side timeline.
- [x] **Manual Entry:** Functional clinician input for all vital signs.

### **Key Directories:**
- `/server/templates`: HTMX and Jinja2 UI.
- `/server/services`: Alerting and Reminders logic.
- `/mobile`: Patient-facing React Native app.
- `/docs`: Detailed system and clinical specifications.

### **Persistent Preferences:**
1. **Design:** Modern Warm Earth (Espresso, Stone, Terracotta).
2. **Arch:** No JS frameworks; rely on HTMX for all interactivity.
3. **Clinical:** High density, high numeric legibility, longitudinal views.

### **Next Steps Log:**
- Implement real document file uploads (currently metadata mock).
- Add cardiologist-specific intervention workflows.
- Expand mobile app with BLE-PLX hardware hooks.
