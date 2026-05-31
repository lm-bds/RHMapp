# Clinical & EHR Specification (Australian Standard)

## Australian Compliance
The system implements demographics according to the National Health Data Dictionary (NHDD):
- **Indigenous Status:** AIHW codes (1, 2, 3, 4, 9).
- **Health Identifiers:** Validated Medicare Number (10 digits), IRN, DVA File, and IHI.
- **Enums:** Sex, NOK Relationships, and NYHA symptom severity classes.

## Clinical Triage Logic
Patients are ranked on the dashboard by an **Acuity Score**:
- **URGENT (Red, Score 3+):** 
  - Weight spike ≥ 2.0kg over dry weight.
  - SpO2 < 92% (Hypoxia).
  - Hypertension Stage 2 (≥140 systolic).
- **Watch (Yellow, Score 1+):**
  - Weight increase ≥ 1.0kg.
  - Elevated BP (≥130 systolic).
- **Stable (Green, Score 0):** Within normal bounds.

## EHR Features
1. **Pinned Visual Trends:** Weight, BP, and SpO2 graphs (Chart.js) always visible at the top.
2. **Tabbed Workspace:** Toggles between Vitals list, Clinical Notes, and Documents.
3. **Longitudinal Timeline:** Right-sidebar history of clinical events, hospitalisations, and acknowledgements.
4. **Formal Acknowledgement:** Requires a clinical rationale (reason + comment) to clear an alert from the triage dashboard.
5. **Document Store:** Metadata-based storage for Referrals, Imaging, and Pathology.
