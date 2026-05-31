import uuid
import enum
from datetime import datetime, timezone, date
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, Date, Enum, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass

# --- Australian Standard Enums ---

class SexEnum(str, enum.Enum):
    MALE = "Male"
    FEMALE = "Female"
    INTERSEX = "Intersex"
    NOT_STATED = "Not Stated"

class IndigenousStatusEnum(str, enum.Enum):
    ABORIGINAL = "1"
    TORRES_STRAIT = "2"
    BOTH = "3"
    NEITHER = "4"
    NOT_STATED = "9"

class NYHAClassEnum(str, enum.Enum):
    I = "I"
    II = "II"
    III = "III"
    IV = "IV"

class NOKRelationshipEnum(str, enum.Enum):
    SPOUSE = "Spouse"
    CHILD = "Child"
    CARER = "Carer"
    OTHER = "Other"


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    first_name: Mapped[str] = mapped_column(String, nullable=False)
    last_name: Mapped[str] = mapped_column(String, nullable=False)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    sex: Mapped[SexEnum] = mapped_column(Enum(SexEnum), nullable=False)
    indigenous_status: Mapped[IndigenousStatusEnum] = mapped_column(Enum(IndigenousStatusEnum), nullable=False)

    medicare_number: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    medicare_irn: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    dva_file_number: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    ihi_number: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)

    phone: Mapped[str] = mapped_column(String, nullable=False)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    nok_name: Mapped[str] = mapped_column(String, nullable=False)
    nok_phone: Mapped[str] = mapped_column(String, nullable=False)
    nok_relationship: Mapped[NOKRelationshipEnum] = mapped_column(Enum(NOKRelationshipEnum), nullable=False)

    primary_diagnosis: Mapped[str] = mapped_column(String, nullable=False)
    nyha_class: Mapped[NYHAClassEnum] = mapped_column(Enum(NYHAClassEnum), nullable=False)
    baseline_weight: Mapped[float] = mapped_column(Float, nullable=False)
    target_systolic: Mapped[int] = mapped_column(Integer, nullable=False)
    target_diastolic: Mapped[int] = mapped_column(Integer, nullable=False)
    primary_gp: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    @property
    def name(self):
        return f"{self.first_name} {self.last_name}"

    tokens: Mapped[List["DeviceToken"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    vitals: Mapped[List["Vital"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    questionnaire_responses: Mapped[List["QuestionnaireResponse"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    alerts: Mapped[List["AlertLog"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    events: Mapped[List["Event"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    notes: Mapped[List["PatientNote"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    documents: Mapped[List["Document"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    care_plan: Mapped[Optional["CarePlan"]] = relationship(back_populates="patient", cascade="all, delete-orphan")


class CarePlan(Base):
    __tablename__ = "care_plans"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), unique=True, nullable=False)
    
    require_weight: Mapped[bool] = mapped_column(Boolean, default=True)
    require_bp: Mapped[bool] = mapped_column(Boolean, default=True)
    require_spo2: Mapped[bool] = mapped_column(Boolean, default=False)
    require_hr: Mapped[bool] = mapped_column(Boolean, default=True)
    
    active_questions: Mapped[Optional[str]] = mapped_column(Text, default="EDEMA_CHECK", nullable=True) 

    patient: Mapped["Patient"] = relationship(back_populates="care_plan")


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), nullable=False)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    doc_type: Mapped[str] = mapped_column(String, nullable=False) 
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    patient: Mapped["Patient"] = relationship(back_populates="documents")


class Event(Base):
    __tablename__ = "events"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    scheduled_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    event_type: Mapped[str] = mapped_column(String, nullable=False) 
    description: Mapped[str] = mapped_column(Text, nullable=False)
    
    patient: Mapped["Patient"] = relationship(back_populates="events")


class PatientNote(Base):
    __tablename__ = "patient_notes"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("staff_users.id"), nullable=False)

    patient: Mapped["Patient"] = relationship(back_populates="notes")
    author: Mapped["StaffUser"] = relationship()


class DeviceToken(Base):
    __tablename__ = "device_tokens"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), nullable=False)
    auth_token: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    patient: Mapped["Patient"] = relationship(back_populates="tokens")


class Vital(Base):
    __tablename__ = "vitals"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, default=lambda: datetime.now(timezone.utc), nullable=False)
    
    weight: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    systolic: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    diastolic: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    heart_rate: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    spo2: Mapped[Optional[int]] = mapped_column(Integer, nullable=True) 
    
    is_acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("staff_users.id"), nullable=True)
    acknowledgement_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    patient: Mapped["Patient"] = relationship(back_populates="vitals")
    acknowledged_by: Mapped[Optional["StaffUser"]] = relationship()


class QuestionnaireResponse(Base):
    __tablename__ = "questionnaire_responses"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    question_id: Mapped[str] = mapped_column(String, nullable=False)
    answer_value: Mapped[str] = mapped_column(Text, nullable=False)

    patient: Mapped["Patient"] = relationship(back_populates="questionnaire_responses")


class StaffUser(Base):
    __tablename__ = "staff_users"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)


class AlertLog(Base):
    __tablename__ = "alert_logs"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    trigger_metric: Mapped[str] = mapped_column(String, nullable=False)
    alert_status: Mapped[str] = mapped_column(String, default="pending", nullable=False)

    patient: Mapped["Patient"] = relationship(back_populates="alerts")
