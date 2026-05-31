from datetime import datetime, date
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from .models import SexEnum, IndigenousStatusEnum, NYHAClassEnum, NOKRelationshipEnum


# --- Patient Schemas ---

class PatientBase(BaseModel):
    first_name: str
    last_name: str
    date_of_birth: date
    sex: SexEnum
    indigenous_status: IndigenousStatusEnum
    
    # Identifiers
    medicare_number: Optional[str] = Field(None, min_length=10, max_length=10)
    medicare_irn: Optional[int] = Field(None, ge=1, le=9)
    dva_file_number: Optional[str] = None
    ihi_number: Optional[str] = Field(None, min_length=16, max_length=16)
    
    # Contact
    phone: str
    address: str
    nok_name: str
    nok_phone: str
    nok_relationship: NOKRelationshipEnum
    
    # Clinical
    primary_diagnosis: str
    nyha_class: NYHAClassEnum
    baseline_weight: float
    target_systolic: int
    target_diastolic: int
    primary_gp: Optional[str] = None

class PatientCreate(PatientBase):
    pass

class PatientRead(PatientBase):
    id: UUID
    is_active: bool
    model_config = ConfigDict(from_attributes=True)


# --- Existing Schemas ---

class StaffLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class DeviceBind(BaseModel):
    setup_token: str

class VitalSubmit(BaseModel):
    weight: Optional[float] = Field(None, description="Weight in kg")
    systolic: Optional[int] = Field(None, description="Systolic blood pressure")
    diastolic: Optional[int] = Field(None, description="Diastolic blood pressure")
    heart_rate: Optional[int] = Field(None, description="Heart rate in bpm")
    spo2: Optional[int] = Field(None, description="Oxygen saturation %")

class QuestionnaireItem(BaseModel):
    question_id: str
    answer_value: str

class TaskSubmit(BaseModel):
    vitals: Optional[VitalSubmit] = None
    questionnaire: Optional[List[QuestionnaireItem]] = None

class TaskItem(BaseModel):
    id: str
    type: str
    label: str
    required: bool = True
    metadata: Optional[dict] = None

class DailyTasksResponse(BaseModel):
    patient_name: str
    tasks: List[TaskItem]
    upcoming_appointments: List[dict] # Simplified for MVP: list of date/description strings
