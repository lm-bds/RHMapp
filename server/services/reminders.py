import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from .. import models

def schedule_appointment_reminders(event_id: uuid.UUID, patient_name: str, scheduled_time: datetime):
    """
    Mock service to schedule reminders.
    In production, this would add jobs to a task queue (like Celery or APScheduler)
    to trigger SMS/Push notifications at specific times.
    """
    # Reminder 1: Morning of the appointment (e.g., 8:00 AM)
    day_of_reminder = scheduled_time.replace(hour=8, minute=0)
    
    # Reminder 2: 15 minutes before
    fifteen_min_reminder = scheduled_time.replace(minute=scheduled_time.minute - 15)

    print(f"\n[REMINDER SERVICE] ****************************************")
    print(f"SCHEDULING REMINDERS for {patient_name}'s appointment on {scheduled_time.strftime('%Y-%m-%d %H:%M')}")
    print(f"1. Day-of Reminder: Set for {day_of_reminder.strftime('%H:%M')}")
    print(f"2. Urgent Reminder: Set for {fifteen_min_reminder.strftime('%H:%M')}")
    print(f"************************************************************\n")

def send_immediate_confirmation(patient_name: str, scheduled_time: datetime):
    print(f"\n[NOTIFICATION] SMS Sent to {patient_name}: Your appointment is confirmed for {scheduled_time.strftime('%d %b at %H:%M')}.\n")
