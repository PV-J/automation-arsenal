## 4. MedRecon — `projects/medrecon/README.md`

```markdown
# MedRecon — Patient Data Reconciliation & Clinical Anomaly Detection

**Problem:** Healthcare organizations maintain patient records across multiple systems (EHR, lab, pharmacy). Data drift between these systems leads to medication errors, missed diagnoses, and compliance violations.

**Solution:** A clinical reconciliation engine that probabilistically matches patient records across systems, reconciles lab results and medication lists, detects clinically significant anomalies, and generates auditable reports — all with HIPAA-aware logging that never exposes PHI.

## What It Does

- **Probabilistic patient matching:** Weighted field comparison across demographic sources
- **Lab trend analysis:** Delta checks with severity classification (critical/abnormal/borderline/normal)
- **Medication reconciliation:** Cross-system comparison with drug-drug interaction checking
- **Clinical decision support:** Generates actionable recommendations for critical findings
- **PHI protection:** All identifiers hashed before storage; PHI filter prevents accidental logging
- **Full audit trail:** Every data access and transformation logged for compliance

## Architecture Decision: Why probabilistic matching over deterministic

Patient records from different systems rarely match perfectly. Names have typos, dates of birth are off by one year, zip codes change. Deterministic matching on a single field (like MRN) misses these records entirely. A weighted scoring system with configurable thresholds catches both exact matches and probable matches that need human review — mimicking what a clinical data analyst would do manually.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Reconcile patient demographics from two sources
python clinical_recon.py \
  --ehr sample_data/ehr_export.csv \
  --lab sample_data/lab_feed.csv \
  --threshold 0.75

# Full reconciliation with lab trends and medications
python clinical_recon.py \
  --ehr sample_data/ehr_export.csv \
  --lab sample_data/lab_feed.csv \
  --pharmacy sample_data/pharmacy_data.csv \
  --full-recon

# Generate PDF report
python clinical_recon.py \
  --ehr sample_data/ehr_export.csv \
  --lab sample_data/lab_feed.csv \
  --report reconciliation_report.json
  
Expected Output

==================================================
CLINICAL RECONCILIATION REPORT
==================================================

Patient Matching:
  Matched (high confidence):     4,231  (95%+ match score)
  Partial matches (review):        127  (75-94% match score)
  Unmatched in EHR only:            43
  Unmatched in Lab only:            18

Lab Analysis:
  Critical findings:                12  (requires immediate action)
  Abnormal findings:                89  (requires follow-up)
  Borderline findings:             234  (monitor)

Critical Finding Example:
  Patient: [REDACTED_HASH]
  Test: POTASSIUM
  Value: 6.2 mmol/L (Ref: 3.5-5.1)
  Severity: CRITICAL
  Action: URGENT — Immediate ECG and cardiac monitoring.
          Administer calcium gluconate.

Medication Reconciliation:
  Discrepancies found:              34
  Potential drug interactions:       7

HIGH RISK INTERACTION:
  Warfarin + Aspirin → Increased bleeding risk
  Affected patients: 3
  
PHI Protection Measures

    All patient identifiers one-way hashed (SHA-256) before any processing

    Log filter redacts SSN/MRN patterns automatically

    Audit trail records actions without exposing patient data

    Configurable data retention policies

    Sample data uses synthetic, non-real patient information

Clinical Rules Implemented

    Lab delta checks: Flags values >50% outside reference range as critical

    Trend detection: Linear regression on last 5 results; rapid changes trigger alerts

    Drug interactions: 40+ known interaction pairs (warfarin-aspirin, lisinopril-potassium, etc.)

    Dose reconciliation: Flags when dose or frequency differs between systems

Edge Cases Handled

    Duplicate patient records: Cross-referenced before matching

    Missing lab reference ranges: Flagged as inconclusive, not errored

    Discontinued medications: Excluded from interaction checks

    Pediatric patients: Separate reference ranges configurable

    International lab units: Unit conversion for common tests (future)

⚠️ Important Disclaimer

This software is for demonstration and educational purposes. It is not FDA-approved, not validated for clinical use, and should never be used to make actual patient care decisions. Drug interaction data is simplified and incomplete. Always consult licensed clinical decision support systems for real healthcare workflows.

Dependencies

See requirements.txt.
License

MIT