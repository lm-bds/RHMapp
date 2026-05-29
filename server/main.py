import os
import uuid
import io
import base64
import qrcode
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, Generator, Optional

from fastapi import Depends, FastAPI, HTTPException, status, Request, BackgroundTasks
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from . import models, schemas
from .services.alerting import evaluate_patient_vitals
from .services.reminders import schedule_appointment_reminders, send_immediate_confirmation

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "super-secret-key-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 30 
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./rpm_db.db") # Default to SQLite for local run

# Database Setup
# connect_args={"check_same_thread": False} is needed only for SQLite
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables on startup
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
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_staff(
    request: Request,
    db: Session = Depends(get_db)
) -> models.StaffUser:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        # --- PROTOTYPE OVERRIDE ---
        # For local testing, if no token is present, we'll return the first staff user (admin)
        staff = db.scalar(select(models.StaffUser).limit(1))
        if staff:
            return staff
        # --------------------------
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
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid device token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        patient_id: str = payload.get("sub")
        token_id: str = payload.get("tid")
        if patient_id is None or token_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    db_token = db.scalar(
        select(models.DeviceToken).where(
            models.DeviceToken.id == uuid.UUID(token_id),
            models.DeviceToken.is_revoked == False
        )
    )
    if not db_token:
        raise credentials_exception

    patient = db.get(models.Patient, uuid.UUID(patient_id))
    if not patient:
        raise credentials_exception
    return patient


# Routes
@app.post("/api/v1/staff/login", response_model=schemas.Token)
async def staff_login(form_data: schemas.StaffLogin, db: Session = Depends(get_db)):
    staff = db.scalar(select(models.StaffUser).where(models.StaffUser.email == form_data.email))
    if not staff or not pwd_context.verify(form_data.password, staff.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(
        data={"sub": staff.email, "role": staff.role},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/api/v1/auth/bind-device", response_model=schemas.Token)
async def bind_device(data: schemas.DeviceBind, db: Session = Depends(get_db)):
    try:
        if data.setup_token == "PROTOTYPE_2024":
            patient = db.scalar(select(models.Patient).limit(1))
        else:
            patient = db.get(models.Patient, uuid.UUID(data.setup_token))
            
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found or invalid token")
            
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid setup token format")

    new_token_id = uuid.uuid4()
    access_token = create_access_token(
        data={"sub": str(patient.id), "tid": str(new_token_id)},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    db_token = models.DeviceToken(
        id=new_token_id,
        patient_id=patient.id,
        auth_token=access_token
    )
    db.add(db_token)
    db.commit()
    
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/api/v1/tasks/today", response_model=schemas.DailyTasksResponse)
async def get_daily_tasks(current_patient: Annotated[models.Patient, Depends(get_current_device)]):
    tasks = [
        {"id": "weight_reading", "type": "vital", "label": "Please step on the scale", "required": True},
        {"id": "bp_reading", "type": "vital", "label": "Please take your blood pressure", "required": True},
        {
            "id": "edema_check", 
            "type": "questionnaire", 
            "label": "Are your ankles more swollen than usual today?", 
            "required": True,
            "metadata": {"options": ["Yes", "No"]}
        }
    ]
    return {"tasks": tasks}


@app.post("/api/v1/tasks/submit")
async def submit_tasks(
    data: schemas.TaskSubmit,
    current_patient: Annotated[models.Patient, Depends(get_current_device)],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    # Process Vitals
    if data.vitals:
        db_vital = models.Vital(
            patient_id=current_patient.id,
            weight=data.vitals.weight,
            systolic=data.vitals.systolic,
            diastolic=data.vitals.diastolic,
            heart_rate=data.vitals.heart_rate
        )
        db.add(db_vital)
    
    # Process Questionnaire
    if data.questionnaire:
        for answer in data.questionnaire:
            db_resp = models.QuestionnaireResponse(
                patient_id=current_patient.id,
                question_id=answer.question_id,
                answer_value=answer.answer_value
            )
            db.add(db_resp)
            
    db.commit()

    # Queue background clinical evaluation
    background_tasks.add_task(evaluate_patient_vitals, current_patient.id, db)

    return {"status": "success", "message": "Tasks submitted successfully"}


# Dashboard Routes
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.StaffUser = Depends(get_current_staff)
):
    all_patients = db.scalars(select(models.Patient)).all()
    
    patient_data = []
    for patient in all_patients:
        # Get latest vital
        latest_vital = db.scalar(
            select(models.Vital)
            .where(models.Vital.patient_id == patient.id)
            .order_by(models.Vital.timestamp.desc())
            .limit(1)
        )
        
        acuity_score = 0
        acuity_label = "Stable"
        reasons = []
        is_acknowledged = False

        if latest_vital:
            is_acknowledged = latest_vital.is_acknowledged
            # Check Weight Spike (Acuity +3)
            if patient.baseline_weight and latest_vital.weight:
                diff = latest_vital.weight - patient.baseline_weight
                if diff >= 2.0:
                    acuity_score += 3
                    reasons.append(f"Weight Spike (+{diff:.1f}kg)")
                elif diff >= 1.0:
                    acuity_score += 1

            # Check BP (Acuity +2 for High, +1 for Elevated)
            if latest_vital.systolic:
                if latest_vital.systolic >= 140 or (latest_vital.diastolic and latest_vital.diastolic >= 90):
                    acuity_score += 2
                    reasons.append("Hypertension Stage 2")
                elif latest_vital.systolic >= 130 or (latest_vital.diastolic and latest_vital.diastolic >= 80):
                    acuity_score += 1
        
        # Determine Label
        if acuity_score >= 3:
            acuity_label = "URGENT"
        elif acuity_score >= 1:
            acuity_label = "Watch"
            
        patient_data.append({
            "patient": patient,
            "latest_vital": latest_vital,
            "acuity_score": acuity_score,
            "acuity_label": acuity_label,
            "reasons": reasons,
            "is_acknowledged": is_acknowledged
        })

    # Sort by acuity score descending
    patient_data.sort(key=lambda x: x["acuity_score"], reverse=True)

    return templates.TemplateResponse(
        "dashboard.html", 
        {"request": request, "patient_data": patient_data, "current_user": current_user}
    )


@app.get("/api/v1/vitals/{vital_id}/acknowledge-modal", response_class=HTMLResponse)
async def get_acknowledge_modal(
    vital_id: uuid.UUID, 
    request: Request,
    db: Session = Depends(get_db)
):
    vital = db.get(models.Vital, vital_id)
    return templates.TemplateResponse("acknowledge_modal.html", {
        "request": request, 
        "vital_id": vital_id, 
        "patient_id": vital.patient_id
    })


@app.post("/api/v1/vitals/{vital_id}/acknowledge", response_class=HTMLResponse)
async def acknowledge_vital(
    vital_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.StaffUser = Depends(get_current_staff)
):
    form_data = await request.form()
    reason = form_data.get("reason")
    comment = form_data.get("comment")

    vital = db.get(models.Vital, vital_id)
    if not vital:
        raise HTTPException(status_code=404)
    
    # Update Vital
    vital.is_acknowledged = True
    vital.acknowledged_at = datetime.now(timezone.utc)
    vital.acknowledged_by_id = current_user.id
    vital.acknowledgement_comment = f"{reason}: {comment}" if comment else reason
    
    # Log as Event in Patient File
    new_event = models.Event(
        patient_id=vital.patient_id,
        event_type="alert_acknowledged",
        description=f"Vital Sign Alert Acknowledged. Reason: {reason}. Comment: {comment or 'None'}"
    )
    db.add(new_event)
    
    db.commit()
    
    return """
    <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-black uppercase tracking-wider bg-gray-100 text-gray-400">
        Acknowledged
    </span>
    """

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
        # Create Patient Record
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
        db.refresh(new_patient)

        # Redirect to the new patient's file
        # Using a full dashboard reload for simplicity in this prototype
        return dashboard(request, db, current_user)

    except Exception as e:
        print(f"Error creating patient: {e}")
        return f'<div class="bg-red-100 p-4 text-red-700">Error: {str(e)}</div>'


@app.get("/dashboard/patient/{patient_id}", response_class=HTMLResponse)
async def patient_detail(
    patient_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.StaffUser = Depends(get_current_staff)
):
    patient = db.get(models.Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    vitals = db.scalars(
        select(models.Vital)
        .where(models.Vital.patient_id == patient_id, models.Vital.timestamp >= seven_days_ago)
        .order_by(models.Vital.timestamp.desc())
    ).all()
    
    return templates.TemplateResponse(
        "patient_detail.html", 
        {"request": request, "patient": patient, "vitals": vitals}
    )


@app.get("/dashboard/patient/{patient_id}/file", response_class=HTMLResponse)
async def patient_file(
    patient_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.StaffUser = Depends(get_current_staff)
):
    patient = db.get(models.Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    # Fetch all relevant data
    vitals = db.scalars(select(models.Vital).where(models.Vital.patient_id == patient_id).order_by(models.Vital.timestamp.desc())).all()
    events = db.scalars(select(models.Event).where(models.Event.patient_id == patient_id).order_by(models.Event.timestamp.desc())).all()
    notes = db.scalars(select(models.PatientNote).where(models.PatientNote.patient_id == patient_id).order_by(models.PatientNote.timestamp.desc())).all()
    
    return templates.TemplateResponse(
        "patient_file.html", 
        {
            "request": request, 
            "patient": patient, 
            "vitals": vitals, 
            "events": events, 
            "notes": notes,
            "current_user": current_user
        }
    )


# Clinical Actions
@app.get("/dashboard/patient/{patient_id}/note-form", response_class=HTMLResponse)
async def get_note_form(
    patient_id: uuid.UUID, 
    request: Request,
    current_user: models.StaffUser = Depends(get_current_staff)
):
    return templates.TemplateResponse("note_form.html", {"request": request, "patient_id": patient_id, "current_user": current_user})


@app.get("/dashboard/patient/{patient_id}/event-form", response_class=HTMLResponse)
async def get_event_form(patient_id: uuid.UUID, type: str, request: Request):
    return templates.TemplateResponse("event_form.html", {"request": request, "patient_id": patient_id, "type": type})


@app.post("/dashboard/patient/{patient_id}/notes", response_class=HTMLResponse)
async def add_note(
    patient_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.StaffUser = Depends(get_current_staff)
):
    form_data = await request.form()
    new_note = models.PatientNote(
        patient_id=patient_id,
        content=form_data.get("content"),
        author_id=current_user.id
    )
    db.add(new_note)
    db.commit()
    db.refresh(new_note)
    
    # Return just the note snippet with author name
    author_name = current_user.email.split('@')[0].title()
    return f"""
    <div class="bg-yellow-50 p-4 rounded-lg border-l-4 border-yellow-400 shadow-sm animate-pulse">
        <div class="flex justify-between items-start mb-2">
            <span class="text-xs font-bold text-gray-500 uppercase">{new_note.timestamp.strftime('%d %b %Y %H:%M')}</span>
            <span class="text-[10px] font-bold text-blue-700 uppercase tracking-widest bg-blue-50 px-2 py-0.5 rounded">Dr. {author_name}</span>
        </div>
        <p class="text-gray-800 text-sm whitespace-pre-wrap">{new_note.content}</p>
    </div>
    """


@app.post("/dashboard/patient/{patient_id}/events", response_class=HTMLResponse)
async def add_event(
    patient_id: uuid.UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.StaffUser = Depends(get_current_staff)
):
    form_data = await request.form()
    event_type = form_data.get("event_type")
    scheduled_time_str = form_data.get("scheduled_time")
    
    scheduled_time = None
    if scheduled_time_str:
        scheduled_time = datetime.fromisoformat(scheduled_time_str)

    new_event = models.Event(
        patient_id=patient_id,
        event_type=event_type,
        description=form_data.get("description"),
        scheduled_time=scheduled_time
    )
    db.add(new_event)
    db.commit()
    db.refresh(new_event)
    
    patient = db.get(models.Patient, patient_id)
    
    # Trigger Reminders for Appointments
    if event_type == "appointment" and scheduled_time:
        background_tasks.add_task(schedule_appointment_reminders, new_event.id, patient.name, scheduled_time)
        background_tasks.add_task(send_immediate_confirmation, patient.name, scheduled_time)
    
    color_class = "text-red-600" if event_type == "hospitalization" else "text-purple-600" if event_type == "med_change" else "text-blue-600"
    
    scheduled_display = f'<p class="text-xs font-bold text-blue-800">Scheduled: {scheduled_time.strftime("%d %b %Y at %H:%M")}</p>' if scheduled_time else ""

    # Return just the event snippet
    return f"""
    <div class="flex animate-pulse">
        <div class="flex flex-col items-center mr-4">
            <div class="w-3 h-3 bg-blue-500 rounded-full"></div>
            <div class="w-px h-full bg-gray-200"></div>
        </div>
        <div class="pb-6">
            <p class="text-xs text-gray-400 font-mono">{new_event.timestamp.strftime('%d %b %Y')}</p>
            <p class="text-sm font-bold uppercase tracking-tight {color_class}">
                {event_type.replace('_', ' ')}
            </p>
            {scheduled_display}
            <p class="text-gray-700 mt-1">{new_event.description}</p>
        </div>
    </div>
    """


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
