import uuid
import random
from datetime import datetime, timedelta, timezone, date
from passlib.context import CryptContext
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from server import models

DATABASE_URL = "sqlite:///./rpm_db.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def setup_demo_data():
    db = SessionLocal()
    
    # Create Staff
    admin = models.StaffUser(
        id=uuid.uuid4(),
        email="admin@example.com",
        hashed_password=pwd_context.hash("admin123"),
        role="admin"
    )
    db.add(admin)
    db.flush()

    # Generate 50 Patients
    names = [
        ("James", "Wilson"), ("Mary", "Smith"), ("Robert", "Brown"), ("Patricia", "Taylor"), ("John", "Johnson"),
        ("Linda", "White"), ("Michael", "Miller"), ("Barbara", "Davis"), ("William", "Garcia"), ("Elizabeth", "Martinez"),
        ("David", "Anderson"), ("Jennifer", "Thomas"), ("Richard", "Jackson"), ("Maria", "Lewis"), ("Joseph", "Lee"),
        ("Susan", "Walker"), ("Thomas", "Hall"), ("Margaret", "Allen"), ("Charles", "Young"), ("Dorothy", "Hernandez"),
        ("Christopher", "King"), ("Lisa", "Wright"), ("Daniel", "Lopez"), ("Nancy", "Hill"), ("Matthew", "Scott"),
        ("Karen", "Green"), ("Anthony", "Adams"), ("Betty", "Baker"), ("Mark", "Gonzalez"), ("Helen", "Nelson"),
        ("Donald", "Carter"), ("Sandra", "Mitchell"), ("Steven", "Perez"), ("Donna", "Roberts"), ("Paul", "Turner"),
        ("Carol", "Phillips"), ("Andrew", "Campbell"), ("Ruth", "Parker"), ("Joshua", "Evans"), ("Sharon", "Edwards")
    ]

    print(f"Generating {len(names)} Australian patient records...")

    for first, last in names:
        patient_id = uuid.uuid4()
        baseline = random.uniform(60, 100)
        
        # Calculate random DOB for super-agers (75-98)
        age_days = random.randint(75 * 365, 98 * 365)
        dob = date.today() - timedelta(days=age_days)

        patient = models.Patient(
            id=patient_id,
            first_name=first,
            last_name=last,
            date_of_birth=dob,
            sex=random.choice(list(models.SexEnum)),
            indigenous_status=models.IndigenousStatusEnum.NEITHER,
            medicare_number="".join([str(random.randint(0, 9)) for _ in range(10)]),
            medicare_irn=random.randint(1, 3),
            phone=f"04{random.randint(10000000, 99999999)}",
            address=f"{random.randint(1, 200)} High St, Melbourne VIC 3000",
            nok_name=f"NOK for {first}",
            nok_phone="0400 000 000",
            nok_relationship=models.NOKRelationshipEnum.CHILD,
            primary_diagnosis="Chronic Heart Failure (CHF)",
            nyha_class=random.choice(list(models.NYHAClassEnum)),
            baseline_weight=round(baseline, 1),
            target_systolic=120,
            target_diastolic=80,
            is_active=True
        )
        db.add(patient)
        db.flush()

        # Randomly assign acuity
        rand_val = random.random()
        
        if rand_val > 0.8: # URGENT (Weight Spike)
            vital = models.Vital(
                patient_id=patient_id,
                weight=round(baseline + random.uniform(2.1, 4.5), 1),
                systolic=random.randint(145, 180),
                diastolic=random.randint(95, 110),
                heart_rate=random.randint(80, 110)
            )
        elif rand_val > 0.6: # WATCH (BP Elevation)
            vital = models.Vital(
                patient_id=patient_id,
                weight=round(baseline + random.uniform(0.5, 1.2), 1),
                systolic=random.randint(132, 139),
                diastolic=random.randint(82, 88),
                heart_rate=random.randint(60, 90)
            )
        else: # STABLE
            vital = models.Vital(
                patient_id=patient_id,
                weight=round(baseline + random.uniform(-0.5, 0.5), 1),
                systolic=random.randint(110, 125),
                diastolic=random.randint(70, 78),
                heart_rate=random.randint(60, 80)
            )
        db.add(vital)

    db.commit()
    print("Database seeded successfully with Australian patient records.")
    db.close()

if __name__ == "__main__":
    models.Base.metadata.create_all(bind=engine)
    setup_demo_data()
