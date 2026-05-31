# System Architecture: Remote Patient Monitoring (RHMapp)

## Overview
A "radically simple" Remote Patient Monitoring (RPM) system designed for super-agers (90+ heart failure patients) and high-volume Australian clinical triage.

## Tech Stack
- **Backend:** FastAPI (Python 3.9+)
- **Database:** PostgreSQL (Production) / SQLite (Prototype/Dev) via SQLAlchemy 2.0
- **Frontend:** Jinja2 Templates + HTMX (Zero JS framework approach)
- **Styling:** Tailwind CSS (Modern Warm Earth Theme)
- **Mobile:** React Native / Expo (Kiosk-style, passwordless setup)
- **Async Tasks:** FastAPI BackgroundTasks (Alerting & Reminders)

## Project Structure
```text
├── server/
│   ├── main.py            # API routes, Auth, Template rendering
│   ├── models.py          # SQLAlchemy 2.0 Data Models
│   ├── schemas.py         # Pydantic validation schemas
│   ├── services/          # Business logic (Alerting, Reminders)
│   ├── templates/         # Jinja2 + HTMX HTML files
│   └── Dockerfile         # Secure multi-stage build
├── mobile/                # React Native / Expo Source
├── docs/                  # System documentation
├── docker-compose.yml     # Infrastructure orchestration
└── seed_data.py           # Automated Australian patient seeding
```

## Component Interactions
1. **Patient App:** Performs passwordless device binding via QR code. Fetches daily tasks and submits vitals.
2. **Alerting Engine:** Every vital submission triggers an async background task to evaluate clinical thresholds.
3. **Clinical Dashboard:** High-density, searchable triage table with automatic acuity sorting.
4. **EHR:** Full Australian-compliant Electronic Health Record with visual trends and document store.
