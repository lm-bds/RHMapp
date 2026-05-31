import os
import uuid
import io
import base64
import qrcode
from datetime import datetime, timedelta, timezone, date
from typing import Annotated, Any, Generator, Optional

from fastapi import Depends, FastAPI, HTTPException, status, Request, BackgroundTasks, UploadFile, File, Form
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import create_engine, select, desc
from sqlalchemy.orm import Session, sessionmaker

from . import models, schemas
from .services.alerting import evaluate_patient_vitals
from .services.reminders import schedule_appointment_reminders, send_immediate_confirmation

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "super-secret-key-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 30 
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./rpm_db.db")

# Database Setup
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
models.Base.metadata.create_all(bind=engine)

# Security Setup
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/staff/login")

app = FastAPI(title="RPM MVP Backend")
templates = Jinja2Templates(directory="server/templates")


# Dependencies
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_staff(
    request: Request,
    db: Session = Depends(get_db)
) -> models.StaffUser:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        staff = db.scalar(select(models.StaffUser).limit(1))
        if staff: return staff
        raise HTTPException(status_code=401, detail="Not authorized")
    
    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None: raise HTTPException(status_code=401)
        staff = db.scalar(select(models.StaffUser).where(models.StaffUser.email == email))
        return staff
    except JWTError:
        raise HTTPException(status_code=401)


async def get_current_device(
    token: Annotated[str, Depends(oauth2_scheme)], db: Session = Depends(get_db)
) -> models.Patient:
    credentials_exception = HTTPException(status_code=401, detail="Invalid token")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        patient_id: str = payload.get("sub")
        token_id: str = payload.get("tid")
        if patient_id is None or token_id is None: raise credentials_exception
    except JWTError: raise credentials_exception

    db_token = db.scalar(select(models.DeviceToken).where(models.DeviceToken.id == uuid.UUID(token_id), models.DeviceToken.is_revoked == False))
    if not db_token: raise credentials_exception

    patient = db.get(models.Patient, uuid.UUID(patient_id))
    if not patient: raise credentials_exception
    return patient


# --- Mobile API Routes ---

@app.post("/api/v1/staff/login", response_model=schemas.Token)
async def staff_login(form_data: schemas.StaffLogin, db: Session = Depends(get_db)):
    staff = db.scalar(select(models.StaffUser).where(models.StaffUser.email == form_data.email))
    if not staff or not pwd_context.verify(form_data.password, staff.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect credentials")
    access_token = create_access_token(data={"sub": staff.email, "role": staff.role})
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/api/v1/auth/bind-device", response_model=schemas.Token)
async def bind_device(data: schemas.DeviceBind, db: Session = Depends(get_db)):
    try:
        patient = db.get(models.Patient, uuid.UUID(data.setup_token))
        if not patient: raise HTTPException(status_code=404, detail="Patient not found")
    except ValueError: raise HTTPException(status_code=400, detail="Invalid token")

    new_token_id = uuid.uuid4()
    access_token = create_access_token(data={"sub": str(patient.id), "tid": str(new_token_id)})
    db.add(models.DeviceToken(id=new_token_id, patient_id=patient.id, auth_token=access_token))
    db.commit()
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/api/v1/tasks/today", response_model=schemas.DailyTasksResponse)
async def get_daily_tasks(
    current_patient: Annotated[models.Patient, Depends(get_current_device)],
    db: Session = Depends(get_db)
):
    # Fetch upcoming appointments
    now = datetime.now(timezone.utc)
    appointments = db.scalars(
        select(models.Event)
        .where(
            models.Event.patient_id == current_patient.id,
            models.Event.event_type == 'appointment',
            models.Event.scheduled_time > now
        )
        .order_by(models.Event.scheduled_time.asc())
    ).all()

    apt_list = [{"date": a.scheduled_time.strftime("%d %b at %H:%M"), "description": a.description} for a in appointments]

    # Fetch Care Plan (create default if missing)
    cp = db.scalar(select(models.CarePlan).where(models.CarePlan.patient_id == current_patient.id))
    if not cp:
        cp = models.CarePlan(patient_id=current_patient.id)
        db.add(cp)
        db.commit()
        db.refresh(cp)

    # Build dynamic task list
    tasks = []
    if cp.require_weight:
        tasks.append({"id": "weight_reading", "type": "vital", "label": "Step on the scale", "required": True})
    if cp.require_bp:
        tasks.append({"id": "bp_reading", "type": "vital", "label": "Take your blood pressure", "required": True})
    if cp.require_hr:
        tasks.append({"id": "hr_reading", "type": "vital", "label": "Check your heart rate", "required": True})
    if cp.require_spo2:
        tasks.append({"id": "spo2_reading", "type": "vital", "label": "Check your oxygen (SpO2)", "required": True})

    # Add Questionnaire Tasks
    if cp.active_questions:
        q_ids = cp.active_questions.split(",")
        for q_id in q_ids:
            if q_id == "EDEMA_CHECK":
                tasks.append({"id": "edema_check", "type": "questionnaire", "label": "Are your ankles swollen?", "required": True, "metadata": {"options": ["Yes", "No"]}})
            if q_id == "KCCQ_SHORT":
                tasks.append({"id": "kccq_short", "type": "questionnaire", "label": "How restricted was your lifestyle today by heart failure?", "required": True, "metadata": {"options": ["Extremely", "Slightly", "Not at all"]}})

    return {
        "patient_name": current_patient.first_name,
        "tasks": tasks,
        "upcoming_appointments": apt_list
    }


@app.post("/api/v1/tasks/submit")
async def submit_tasks(
    data: schemas.TaskSubmit,
    current_patient: Annotated[models.Patient, Depends(get_current_device)],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    if data.vitals:
        db.add(models.Vital(
            patient_id=current_patient.id,
            weight=data.vitals.weight,
            systolic=data.vitals.systolic,
            diastolic=data.vitals.diastolic,
            heart_rate=data.vitals.heart_rate,
            spo2=data.vitals.spo2
        ))
    if data.questionnaire:
        for ans in data.questionnaire:
            db.add(models.QuestionnaireResponse(patient_id=current_patient.id, question_id=ans.question_id, answer_value=ans.answer_value))
    db.commit()
    background_tasks.add_task(evaluate_patient_vitals, current_patient.id, db)
    return {"status": "success"}


# --- Dashboard Routes ---

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.StaffUser = Depends(get_current_staff)
):
    all_patients = db.scalars(select(models.Patient)).all()
    patient_data = []
    for patient in all_patients:
        latest_vital = db.scalar(select(models.Vital).where(models.Vital.patient_id == patient.id).order_by(desc(models.Vital.timestamp)).limit(1))
        acuity_score = 0
        acuity_label = "Stable"
        reasons = []
        is_acknowledged = False

        if latest_vital:
            is_acknowledged = latest_vital.is_acknowledged
            if patient.baseline_weight and latest_vital.weight:
                diff = latest_vital.weight - patient.baseline_weight
                if diff >= 2.0:
                    acuity_score += 3
                    reasons.append(f"Weight Spike (+{diff:.1f}kg)")
                elif diff >= 1.0: acuity_score += 1
            if latest_vital.systolic:
                if latest_vital.systolic >= 140:
                    acuity_score += 2
                    reasons.append("High BP")
            if latest_vital.spo2 and latest_vital.spo2 < 92:
                acuity_score += 3
                reasons.append(f"Hypoxia ({latest_vital.spo2}%)")
        
        if acuity_score >= 3: acuity_label = "URGENT"
        elif acuity_score >= 1: acuity_label = "Watch"
            
        patient_data.append({
            "patient": patient,
            "latest_vital": latest_vital,
            "acuity_score": acuity_score,
            "acuity_label": acuity_label,
            "reasons": reasons,
            "is_acknowledged": is_acknowledged
        })
    patient_data.sort(key=lambda x: x["acuity_score"], reverse=True)
    return templates.TemplateResponse("dashboard.html", {"request": request, "patient_data": patient_data, "current_user": current_user})


@app.get("/dashboard/patient-form", response_class=HTMLResponse)
async def get_patient_form(request: Request):
    return templates.TemplateResponse("patient_form.html", {"request": request})


@app.post("/api/v1/patients", response_class=HTMLResponse)
async def create_patient(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.StaffUser = Depends(get_current_staff)
):
    form_data = await request.form()
    try:
        new_patient = models.Patient(
            first_name=form_data.get("first_name"),
            last_name=form_data.get("last_name"),
            date_of_birth=date.fromisoformat(form_data.get("date_of_birth")),
            sex=models.SexEnum(form_data.get("sex")),
            indigenous_status=models.IndigenousStatusEnum(form_data.get("indigenous_status")),
            medicare_number=form_data.get("medicare_number") or None,
            medicare_irn=int(form_data.get("medicare_irn")) if form_data.get("medicare_irn") else None,
            dva_file_number=form_data.get("dva_file_number") or None,
            ihi_number=form_data.get("ihi_number") or None,
            phone=form_data.get("phone"),
            address=form_data.get("address"),
            nok_name=form_data.get("nok_name"),
            nok_phone=form_data.get("nok_phone"),
            nok_relationship=models.NOKRelationshipEnum(form_data.get("nok_relationship")),
            primary_diagnosis=form_data.get("primary_diagnosis"),
            nyha_class=models.NYHAClassEnum(form_data.get("nyha_class")),
            baseline_weight=float(form_data.get("baseline_weight")),
            target_systolic=int(form_data.get("target_systolic")),
            target_diastolic=int(form_data.get("target_diastolic")),
            primary_gp=form_data.get("primary_gp") or None
        )
        db.add(new_patient)
        db.commit()
        return RedirectResponse(url="/dashboard", status_code=303)
    except Exception as e: return f'<div class="bg-red-100 p-4 text-red-700">Error: {str(e)}</div>'


@app.get("/dashboard/patient/{patient_id}/file", response_class=HTMLResponse)
async def patient_file(
    patient_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.StaffUser = Depends(get_current_staff)
):
    patient = db.get(models.Patient, patient_id)
    vitals_records = db.scalars(select(models.Vital).where(models.Vital.patient_id == patient_id).order_by(models.Vital.timestamp.asc())).all()
    vitals_json = [{"timestamp": v.timestamp.strftime("%d %b"), "weight": v.weight, "systolic": v.systolic, "diastolic": v.diastolic, "heart_rate": v.heart_rate, "spo2": v.spo2} for v in vitals_records]
    events = db.scalars(select(models.Event).where(models.Event.patient_id == patient_id).order_by(desc(models.Event.timestamp))).all()
    notes = db.scalars(select(models.PatientNote).where(models.PatientNote.patient_id == patient_id).order_by(desc(models.PatientNote.timestamp))).all()
    docs = db.scalars(select(models.Document).where(models.Document.patient_id == patient_id).order_by(desc(models.Document.timestamp))).all()
    
    return templates.TemplateResponse("patient_file.html", {
        "request": request, "patient": patient, "vitals": reversed(vitals_records), 
        "vitals_json": vitals_json, "events": events, "notes": notes, "documents": docs, "current_user": current_user
    })


@app.get("/dashboard/patient/{patient_id}/care-plan-form", response_class=HTMLResponse)
async def get_care_plan_form(patient_id: uuid.UUID, request: Request, db: Session = Depends(get_db)):
    cp = db.scalar(select(models.CarePlan).where(models.CarePlan.patient_id == patient_id))
    if not cp:
        cp = models.CarePlan(patient_id=patient_id)
        db.add(cp)
        db.commit()
        db.refresh(cp)
    return templates.TemplateResponse("care_plan_form.html", {"request": request, "patient_id": patient_id, "care_plan": cp})


@app.post("/dashboard/patient/{patient_id}/care-plan", response_class=HTMLResponse)
async def update_care_plan(
    patient_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.StaffUser = Depends(get_current_staff)
):
    form_data = await request.form()
    cp = db.scalar(select(models.CarePlan).where(models.CarePlan.patient_id == patient_id))
    
    # Update Booleans
    cp.require_weight = "require_weight" in form_data
    cp.require_bp = "require_bp" in form_data
    cp.require_hr = "require_hr" in form_data
    cp.require_spo2 = "require_spo2" in form_data
    
    # Update Questions
    qs = []
    if "q_edema" in form_data: qs.append("EDEMA_CHECK")
    if "q_kccq" in form_data: qs.append("KCCQ_SHORT")
    cp.active_questions = ",".join(qs)
    
    db.add(models.Event(patient_id=patient_id, event_type="care_plan_updated", description=f"Care plan updated by {current_user.email}"))
    db.commit()
    
    # Return the refreshed EHR content (redirect back to vitals tab for feedback)
    return RedirectResponse(url=f"/dashboard/patient/{patient_id}/file", status_code=303)


# --- Clinical Actions ---

@app.get("/dashboard/patient/{patient_id}/vitals-form", response_class=HTMLResponse)
async def get_vitals_form(patient_id: uuid.UUID, request: Request):
    return templates.TemplateResponse("vitals_form.html", {"request": request, "patient_id": patient_id})


@app.post("/api/v1/patients/{patient_id}/vitals", response_class=HTMLResponse)
async def clinician_add_vitals(
    patient_id: uuid.UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.StaffUser = Depends(get_current_staff)
):
    form_data = await request.form()
    
    def safe_float(val): return float(val) if val and val.strip() else None
    def safe_int(val): return int(val) if val and val.strip() else None

    new_vital = models.Vital(
        patient_id=patient_id,
        weight=safe_float(form_data.get("weight")),
        systolic=safe_int(form_data.get("systolic")),
        diastolic=safe_int(form_data.get("diastolic")),
        spo2=safe_int(form_data.get("spo2")),
        heart_rate=safe_int(form_data.get("heart_rate")),
        is_acknowledged=True,
        acknowledged_at=datetime.now(timezone.utc),
        acknowledged_by_id=current_user.id
    )
    db.add(new_vital)
    db.commit()
    
    background_tasks.add_task(evaluate_patient_vitals, patient_id, db)
    
    vitals = db.scalars(
        select(models.Vital)
        .where(models.Vital.patient_id == patient_id)
        .order_by(desc(models.Vital.timestamp))
    ).all()
    
    return "".join([f"""
    <tr class="hover:bg-canvas transition-colors">
        <td class="px-4 py-3 text-xs font-bold text-stone-500 font-mono">{v.timestamp.strftime('%d %b • %H:%M')}</td>
        <td class="px-4 py-3 text-sm font-black text-brand-dark">{v.weight or '--'}kg</td>
        <td class="px-4 py-3 text-sm font-black text-brand-dark">{v.systolic or '--'}/{v.diastolic or '--'}</td>
        <td class="px-4 py-3 text-sm font-black { 'text-status-critical' if v.spo2 and v.spo2 < 92 else 'text-status-stable' }">{v.spo2 or '--'}%</td>
        <td class="px-4 py-3 text-sm font-black text-stone-600">{v.heart_rate or '--'}</td>
    </tr>
    """ for v in vitals])


@app.get("/dashboard/patient/{patient_id}/note-form", response_class=HTMLResponse)
async def get_note_form(patient_id: uuid.UUID, request: Request, current_user: models.StaffUser = Depends(get_current_staff)):
    return templates.TemplateResponse("note_form.html", {"request": request, "patient_id": patient_id, "current_user": current_user})

@app.get("/dashboard/patient/{patient_id}/document-form", response_class=HTMLResponse)
async def get_document_form(patient_id: uuid.UUID, request: Request):
    return templates.TemplateResponse("document_form.html", {"request": request, "patient_id": patient_id})


@app.get("/dashboard/patient/{patient_id}/event-form", response_class=HTMLResponse)
async def get_event_form(patient_id: uuid.UUID, type: str, request: Request):
    return templates.TemplateResponse("event_form.html", {"request": request, "patient_id": patient_id, "type": type})

@app.post("/dashboard/patient/{patient_id}/notes", response_class=HTMLResponse)
async def add_note(patient_id: uuid.UUID, request: Request, db: Session = Depends(get_db), current_user: models.StaffUser = Depends(get_current_staff)):
    form_data = await request.form()
    new_note = models.PatientNote(patient_id=patient_id, content=form_data.get("content"), author_id=current_user.id)
    db.add(new_note)
    db.commit()
    db.refresh(new_note)
    return f"""<div class="bg-amber-50 p-4 rounded-xl border border-border-warm shadow-sm mb-4"><div class="flex justify-between items-start mb-2"><span class="text-xs font-bold text-stone-500 uppercase">{new_note.timestamp.strftime('%d %b %Y %H:%M')}</span><span class="text-[10px] font-black text-brand-accent uppercase tracking-widest bg-brand-dark/5 px-2 py-0.5 rounded-full">Dr. {current_user.email.split('@')[0].title()}</span></div><p class="text-stone-800 text-sm whitespace-pre-wrap leading-relaxed">{new_note.content}</p></div>"""

@app.post("/dashboard/patient/{patient_id}/events", response_class=HTMLResponse)
async def add_event(patient_id: uuid.UUID, request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    form_data = await request.form()
    event_type = form_data.get("event_type")
    sch_time = form_data.get("scheduled_time")
    new_event = models.Event(patient_id=patient_id, event_type=event_type, description=form_data.get("description"), scheduled_time=datetime.fromisoformat(sch_time) if sch_time else None)
    db.add(new_event)
    db.commit()
    db.refresh(new_event)
    patient = db.get(models.Patient, patient_id)
    if event_type == "appointment" and new_event.scheduled_time:
        background_tasks.add_task(schedule_appointment_reminders, new_event.id, patient.name, new_event.scheduled_time)
        background_tasks.add_task(send_immediate_confirmation, patient.name, new_event.scheduled_time)
    
    color = "text-status-critical" if event_type == "hospitalization" else "text-brand-terracotta" if event_type == "med_change" else "text-brand-accent"
    return f"""<div class="flex items-start space-x-4 pb-6 border-l-2 border-border-warm ml-2 pl-4"><div class="absolute -left-1.5 w-3 h-3 bg-brand-accent rounded-full border-2 border-white"></div><div><p class="text-[10px] font-bold text-stone-400 uppercase">{new_event.timestamp.strftime('%d %b %Y')}</p><p class="text-sm font-black {color} uppercase">{event_type.replace('_', ' ')}</p><p class="text-stone-700 mt-1 text-sm">{new_event.description}</p></div></div>"""

# --- Document Store ---

@app.post("/dashboard/patient/{patient_id}/documents", response_class=HTMLResponse)
async def upload_document(patient_id: uuid.UUID, filename: str = Form(...), doc_type: str = Form(...), db: Session = Depends(get_db)):
    # Mock upload: just save metadata
    new_doc = models.Document(patient_id=patient_id, filename=filename, doc_type=doc_type)
    db.add(new_doc)
    db.commit()
    db.refresh(new_doc)
    return f"""<div class="flex items-center justify-between p-3 bg-white border border-border-warm rounded-xl hover:shadow-md transition-all"><div class="flex items-center space-x-3"><div class="bg-brand-dark/5 p-2 rounded-lg text-brand-dark"><svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" /></svg></div><div><p class="text-sm font-bold text-stone-800">{new_doc.filename}</p><p class="text-[10px] font-black text-brand-accent uppercase tracking-widest">{new_doc.doc_type}</p></div></div><button class="text-stone-400 hover:text-status-critical"><svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg></button></div>"""

@app.post("/dashboard/patient/{patient_id}/generate-qr", response_class=HTMLResponse)
async def generate_qr(
    patient_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.StaffUser = Depends(get_current_staff)
):
    setup_token = str(patient_id)
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(setup_token)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    qr_base64 = base64.b64encode(buffered.getvalue()).decode()
    
    return templates.TemplateResponse(
        "qr_snippet.html", 
        {"request": request, "qr_base64": qr_base64, "token": setup_token}
    )


# --- Vitals ---

@app.get("/api/v1/vitals/{vital_id}/acknowledge-modal", response_class=HTMLResponse)
async def get_acknowledge_modal(vital_id: uuid.UUID, request: Request, db: Session = Depends(get_db)):
    vital = db.get(models.Vital, vital_id)
    return templates.TemplateResponse("acknowledge_modal.html", {"request": request, "vital_id": vital_id, "patient_id": vital.patient_id})

@app.post("/api/v1/vitals/{vital_id}/acknowledge", response_class=HTMLResponse)
async def acknowledge_vital(vital_id: uuid.UUID, request: Request, db: Session = Depends(get_db), current_user: models.StaffUser = Depends(get_current_staff)):
    fd = await request.form()
    v = db.get(models.Vital, vital_id)
    v.is_acknowledged, v.acknowledged_at, v.acknowledged_by_id, v.acknowledgement_comment = True, datetime.now(timezone.utc), current_user.id, f"{fd.get('reason')}: {fd.get('comment')}"
    db.add(models.Event(patient_id=v.patient_id, event_type="alert_acknowledged", description=f"Alert Acknowledged. Reason: {fd.get('reason')}"))
    db.commit()
    return '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-black uppercase tracking-wider bg-gray-100 text-gray-400">Acknowledged</span>'
