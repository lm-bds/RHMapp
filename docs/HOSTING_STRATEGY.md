# Hosting & Deployment Strategy

This document outlines the production-ready hosting strategy for the **RHMapp** system, ensuring compliance with Australian healthcare privacy standards and high availability for clinical workflows.

---

## 1. Server & Clinician Dashboard (Backend)

The FastAPI server and HTMX clinician dashboard are deployed as a single containerized unit.

### **Option A: Aptible (Recommended for Compliance)**
- **Why:** Aptible is a PaaS designed specifically for healthcare. It handles HIPAA/HITRUST compliance (transferable to Australian Privacy Act requirements) out of the box.
- **Setup:**
  - Link GitHub repository to Aptible.
  - Deploy using the existing `server/Dockerfile`.
  - **Managed Database:** Use Aptible's managed PostgreSQL 15.

### **Option B: AWS (Enterprise Standard)**
- **Compute:** AWS ECS (Elastic Container Service) with **Fargate** (Serverless).
- **Database:** AWS RDS for PostgreSQL (Multi-AZ for high availability).
- **Security:** Deploy within a VPC; use AWS WAF for application-layer security.

### **Infrastructure Requirements**
- **SSL/TLS:** Essential. Handled by AWS Certificate Manager or Aptible managed SSL.
- **Static Assets:** The "Modern Warm Earth" CSS and Chart.js are currently via CDN, but for production, these should be served via the FastAPI static folder or an S3 bucket with CloudFront.

---

## 2. Patient Kiosk (Mobile App)

The React Native application requires a build and distribution strategy that bypasses traditional web hosting.

### **Build System: Expo EAS**
- **EAS Build:** Use `eas build` to generate production `.ipa` (iOS) and `.aab` (Android) binaries.
- **OTA Updates:** Use **EAS Update** for Over-The-Air clinical logic changes without requiring a full App Store re-submission.

### **Distribution**
- **Internal Testing:** Apple TestFlight and Google Play Internal Testing for clinician review.
- **Production:** 
  - **Android:** Google Play Store.
  - **iOS:** Apple App Store.
- **Private Deployment:** For a "locked-down kiosk" feel, consider **Apple Business Manager** or **managed MDM** (Mobile Device Management) to push the app directly to patient devices.

---

## 3. Database & Data Residency

Given the Australian clinical context (NHDD/AIHW):
- **Data Residency:** All data **MUST** remain within Australian borders.
- **Region:** Use `ap-southeast-2` (Sydney) for AWS or the Australian region for your chosen provider.
- **Backups:** Daily automated snapshots with a 35-day retention policy.
- **Encryption:** Encryption-at-rest (AES-256) for the database and Encryption-in-transit (TLS 1.2+) for all API calls.

---

## 4. Deployment Pipeline (CI/CD)

We utilize **GitHub Actions** for an automated deployment lifecycle:

1. **Lint & Test:** Every Pull Request triggers Pydantic validation checks and SQLAlchemy model integrity tests.
2. **Staging:** Merges to the `develop` branch deploy to a staging environment (e.g., `staging-api.rhmapp.com.au`).
3. **Production:** Merges to the `main` branch trigger:
   - A new Docker image build and push to a private registry (ECR).
   - An zero-downtime rolling deployment to the ECS/Aptible cluster.
   - A notification to clinicians of the new version.

---

## 5. Domain & Connectivity Strategy

| Component | URL (Example) | Role |
| :--- | :--- | :--- |
| **Clinician Portal** | `portal.rhmapp.com.au` | Dashboard & EHR Access. |
| **Mobile API** | `api.rhmapp.com.au` | Mobile app communication hub. |
| **Documentation** | `docs.rhmapp.com.au` | Internal clinical user guides. |
