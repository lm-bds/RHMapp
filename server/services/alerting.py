import uuid
from sqlalchemy import select, desc
from sqlalchemy.orm import Session
from .. import models

def notify_clinician_mock(patient_name: str, delta: float):
    """
    Mock notification service (Twilio/SendGrid simulation)
    """
    print(f"\n[NOTIFICATION MOCK] ****************************************")
    print(f"URGENT: Patient {patient_name} has exceeded weight threshold by {delta:.2f}kg.")
    print(f"************************************************************\n")

def evaluate_patient_vitals(patient_id: uuid.UUID, db: Session):
    """
    Background task to evaluate clinical thresholds and trigger alerts.
    """
    # Fetch Patient
    patient = db.get(models.Patient, patient_id)
    if not patient or patient.baseline_weight is None:
        return

    # Fetch Most Recent Vital
    stmt = (
        select(models.Vital)
        .where(models.Vital.patient_id == patient_id)
        .order_by(desc(models.Vital.timestamp))
        .limit(1)
    )
    latest_vital = db.scalar(stmt)

    if not latest_vital or latest_vital.weight is None:
        return

    # Threshold Logic: Weight Spike >= 2.0kg
    delta = latest_vital.weight - patient.baseline_weight
    
    if delta >= 2.0:
        # Audit Trail: Create AlertLog
        alert = models.AlertLog(
            patient_id=patient_id,
            trigger_metric='weight_spike',
            alert_status='triggered'
        )
        db.add(alert)
        db.commit()

        # Trigger Mock Notification
        notify_clinician_mock(patient.name, delta)
