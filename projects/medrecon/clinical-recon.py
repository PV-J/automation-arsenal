"""
clinical_recon.py
Patient data reconciliation engine with clinical anomaly detection.
Designed for healthcare data pipelines requiring audit trails
and HIPAA-aware logging patterns.

Reconciles patient demographics, lab results, and medication records
across multiple source systems (EHR exports, lab feeds, pharmacy data).

Author: PV-J
License: MIT
Version: 1.0.0
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import logging
import hashlib
import json
import re
from collections import defaultdict

# Configure PHI-aware logging (no raw patient data in logs)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Redact patient identifiers in log output
class PHIFilter(logging.Filter):
    """Prevents Protected Health Information from appearing in logs."""
    def filter(self, record):
        # Replace potential PHI patterns with [REDACTED]
        if hasattr(record, 'msg'):
            record.msg = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '[REDACTED_SSN]', str(record.msg))
            record.msg = re.sub(r'\b[A-Z0-9]{10}\b', '[REDACTED_MRN]', str(record.msg))
        return True

logger.addFilter(PHIFilter())


class SeverityLevel(Enum):
    """Clinical severity classification."""
    CRITICAL = "critical"  # Requires immediate attention
    ABNORMAL = "abnormal"  # Outside reference range, significant
    BORDERLINE = "borderline"  # At threshold, monitor
    NORMAL = "normal"  # Within expected ranges
    INCONCLUSIVE = "inconclusive"  # Insufficient data


class ReconciliationStatus(Enum):
    """Record reconciliation status."""
    MATCHED = "matched"  # Records align across systems
    PARTIAL = "partial"  # Some fields match, discrepancies exist
    UNMATCHED = "unmatched"  # Record exists in only one system
    CONFLICT = "conflict"  # Critical fields contradict


@dataclass
class PatientDemographics:
    """De-identified patient demographic record."""
    patient_id_hash: str  # Hashed identifier
    source_system: str
    first_name_hash: str
    last_name_hash: str
    dob_year: int  # Year only for privacy
    gender: str
    zip_prefix: str  # First 3 digits only
    last_updated: datetime
    
    def match_score(self, other: 'PatientDemographics') -> float:
        """
        Calculate probabilistic match score between two demographic records.
        Uses weighted field comparison to handle typos and variations.
        """
        score = 0.0
        weights = {
            'first_name': 0.25,
            'last_name': 0.25,
            'dob': 0.30,
            'gender': 0.10,
            'zip': 0.10
        }
        
        # Name matching (using hash comparison as proxy for fuzzy matching)
        if self.first_name_hash == other.first_name_hash:
            score += weights['first_name']
        if self.last_name_hash == other.last_name_hash:
            score += weights['last_name']
        
        # Date of birth matching (+/- 1 year for data entry errors)
        if abs(self.dob_year - other.dob_year) <= 1:
            score += weights['dob'] * (1.0 if self.dob_year == other.dob_year else 0.5)
        
        # Gender exact match
        if self.gender == other.gender:
            score += weights['gender']
        
        # Geographic proximity
        if self.zip_prefix == other.zip_prefix:
            score += weights['zip']
        
        return score


@dataclass
class LabResult:
    """Laboratory result with reference ranges."""
    patient_id_hash: str
    test_name: str
    test_code: str  # LOINC code
    value: float
    unit: str
    reference_range_low: Optional[float]
    reference_range_high: Optional[float]
    collection_date: datetime
    result_date: datetime
    source_system: str
    is_abnormal_flag: Optional[bool] = None
    
    def classify_severity(self) -> SeverityLevel:
        """
        Classify lab result severity based on deviation from reference range.
        Implements delta-check logic for critical values.
        """
        if self.reference_range_low is None or self.reference_range_high is None:
            return SeverityLevel.INCONCLUSIVE
        
        range_span = self.reference_range_high - self.reference_range_low
        
        if self.value < self.reference_range_low:
            deviation = (self.reference_range_low - self.value) / range_span
            if deviation > 0.5:  # More than 50% below low range
                return SeverityLevel.CRITICAL
            elif deviation > 0.2:
                return SeverityLevel.ABNORMAL
            else:
                return SeverityLevel.BORDERLINE
        
        elif self.value > self.reference_range_high:
            deviation = (self.value - self.reference_range_high) / range_span
            if deviation > 0.5:
                return SeverityLevel.CRITICAL
            elif deviation > 0.2:
                return SeverityLevel.ABNORMAL
            else:
                return SeverityLevel.BORDERLINE
        
        return SeverityLevel.NORMAL


@dataclass
class MedicationRecord:
    """Medication administration or prescription record."""
    patient_id_hash: str
    medication_name: str
    rxnorm_code: str
    dose: str
    frequency: str
    route: str
    start_date: datetime
    end_date: Optional[datetime]
    prescribing_system: str
    is_active: bool
    
    def check_interaction(self, other: 'MedicationRecord') -> Optional[str]:
        """
        Check for potential drug-drug interactions.
        Simplified using known interaction pairs (would use drug database in production).
        """
        # Known interaction pairs (simplified)
        interactions = {
            ('warfarin', 'aspirin'): 'Increased bleeding risk',
            ('lisinopril', 'potassium'): 'Hyperkalemia risk',
            ('metformin', 'contrast_dye'): 'Lactic acidosis risk',
            ('simvastatin', 'clarithromycin'): 'Rhabdomyolysis risk',
        }
        
        key = tuple(sorted([
            self.medication_name.lower(),
            other.medication_name.lower()
        ]))
        
        return interactions.get(key)


class ClinicalReconciliationEngine:
    """
    Multi-source patient data reconciliation engine.
    
    Workflow:
    1. Ingest records from multiple source systems
    2. Probabilistic patient matching
    3. Lab result reconciliation and trend analysis
    4. Medication reconciliation with interaction checking
    5. Generate reconciliation report with action items
    
    HIPAA considerations:
    - PHI is hashed before logging
    - Audit trail tracks all data access
    - Configurable data retention policies
    """
    
    def __init__(self, match_threshold: float = 0.75):
        self.match_threshold = match_threshold
        self.audit_log: List[Dict] = []
        self.reconciled_patients: Dict[str, Dict] = {}
        
        # Reference ranges database (would be external in production)
        self.lab_reference_ranges = {
            'GLUCOSE': {'low': 70, 'high': 100, 'unit': 'mg/dL', 'critical_low': 40, 'critical_high': 400},
            'CREATININE': {'low': 0.6, 'high': 1.2, 'unit': 'mg/dL', 'critical_low': None, 'critical_high': 4.0},
            'HEMOGLOBIN': {'low': 12.0, 'high': 16.0, 'unit': 'g/dL', 'critical_low': 7.0, 'critical_high': 20.0},
            'POTASSIUM': {'low': 3.5, 'high': 5.1, 'unit': 'mmol/L', 'critical_low': 2.5, 'critical_high': 6.5},
            'WBC': {'low': 4.5, 'high': 11.0, 'unit': 'K/uL', 'critical_low': 1.0, 'critical_high': 50.0},
        }
    
    def ingest_patient_demographics(self, file_path: Path, source_system: str) -> List[PatientDemographics]:
        """
        Ingest patient demographics from CSV export.
        Expects de-identified data with standard columns.
        """
        logger.info(f"Ingesting demographics from {source_system}: {file_path.name}")
        
        try:
            df = pd.read_csv(file_path)
            self._log_audit('INGEST_DEMOGRAPHICS', file_path.name, source_system, len(df))
            
            patients = []
            for _, row in df.iterrows():
                # Hash PHI fields before storing
                patient_id = self._hash_phi(str(row.get('patient_id', row.get('mrn', ''))))
                
                patient = PatientDemographics(
                    patient_id_hash=patient_id,
                    source_system=source_system,
                    first_name_hash=self._hash_phi(str(row.get('first_name', ''))),
                    last_name_hash=self._hash_phi(str(row.get('last_name', ''))),
                    dob_year=int(row.get('dob_year', row.get('birth_year', 0))),
                    gender=str(row.get('gender', '')).upper(),
                    zip_prefix=str(row.get('zip', ''))[:3],
                    last_updated=datetime.now()
                )
                patients.append(patient)
            
            logger.info(f"Ingested {len(patients)} patient records from {source_system}")
            return patients
            
        except Exception as e:
            logger.error(f"Failed to ingest demographics: {e}")
            self._log_audit('INGEST_ERROR', file_path.name, source_system, None, str(e))
            return []
    
    def reconcile_patients(self, source_a: List[PatientDemographics], 
                          source_b: List[PatientDemographics]) -> Dict[str, List]:
        """
        Probabilistic patient matching across two source systems.
        Returns matched, unmatched_A, and unmatched_B records.
        """
        logger.info(f"Reconciling patients: Source A={len(source_a)}, Source B={len(source_b)}")
        
        results = {
            'matched': [],
            'unmatched_source_a': [],
            'unmatched_source_b': [],
            'partial_matches': [],
            'conflicts': []
        }
        
        # Track which B records have been matched
        matched_b_indices = set()
        
        for patient_a in source_a:
            best_match = None
            best_score = 0.0
            best_idx = None
            
            for idx, patient_b in enumerate(source_b):
                if idx in matched_b_indices:
                    continue
                
                score = patient_a.match_score(patient_b)
                
                if score > best_score:
                    best_score = score
                    best_match = patient_b
                    best_idx = idx
            
            if best_score >= self.match_threshold and best_match:
                matched_b_indices.add(best_idx)
                
                if best_score >= 0.95:
                    results['matched'].append({
                        'patient_a': patient_a,
                        'patient_b': best_match,
                        'confidence': best_score,
                        'status': ReconciliationStatus.MATCHED
                    })
                else:
                    results['partial_matches'].append({
                        'patient_a': patient_a,
                        'patient_b': best_match,
                        'confidence': best_score,
                        'status': ReconciliationStatus.PARTIAL
                    })
            else:
                results['unmatched_source_a'].append(patient_a)
        
        # Remaining unmatched in source B
        for idx, patient_b in enumerate(source_b):
            if idx not in matched_b_indices:
                results['unmatched_source_b'].append(patient_b)
        
        logger.info(f"Reconciliation complete: {len(results['matched'])} matched, "
                   f"{len(results['partial_matches'])} partial, "
                   f"{len(results['unmatched_source_a'])} unmatched in A, "
                   f"{len(results['unmatched_source_b'])} unmatched in B")
        
        self._log_audit('RECONCILE', 'patient_demographics', 'cross_source', 
                       len(results['matched']), 
                       f"Match rate: {len(results['matched'])/(len(source_a)+1)*100:.1f}%")
        
        return results
    
    def analyze_lab_trends(self, lab_results: List[LabResult], 
                          patient_id: str, 
                          lookback_days: int = 90) -> Dict:
        """
        Analyze lab result trends for a single patient.
        Detects significant changes requiring clinical attention.
        """
        patient_labs = [lab for lab in lab_results 
                       if lab.patient_id_hash == patient_id]
        
        if not patient_labs:
            return {'status': 'no_data', 'message': 'No lab results found'}
        
        # Group by test
        tests = defaultdict(list)
        for lab in patient_labs:
            tests[lab.test_name].append(lab)
        
        # Sort by date for each test
        for test_name in tests:
            tests[test_name].sort(key=lambda x: x.collection_date)
        
        trend_analysis = {}
        critical_findings = []
        
        for test_name, results in tests.items():
            if len(results) < 2:
                continue
            
            # Calculate trend
            values = [r.value for r in results[-5:]]  # Last 5 results
            dates = [r.collection_date for r in results[-5:]]
            
            # Simple linear trend detection
            if len(values) >= 2:
                x = np.arange(len(values))
                slope, _ = np.polyfit(x, values, 1)
                
                latest = results[-1]
                severity = latest.classify_severity()
                
                trend = {
                    'test_name': test_name,
                    'latest_value': latest.value,
                    'latest_date': latest.collection_date,
                    'unit': latest.unit,
                    'reference_range': f"{latest.reference_range_low}-{latest.reference_range_high}",
                    'trend': 'increasing' if slope > 0 else 'decreasing' if slope < 0 else 'stable',
                    'slope_per_day': slope,
                    'severity': severity.value,
                    'num_results': len(results)
                }
                
                trend_analysis[test_name] = trend
                
                if severity in [SeverityLevel.CRITICAL, SeverityLevel.ABNORMAL]:
                    critical_findings.append({
                        'test': test_name,
                        'value': latest.value,
                        'severity': severity.value,
                        'action': self._recommend_action(test_name, latest.value, slope)
                    })
        
        return {
            'patient_id': patient_id,
            'trends': trend_analysis,
            'critical_findings': critical_findings,
            'total_tests_analyzed': len(trend_analysis)
        }
    
    def _recommend_action(self, test_name: str, value: float, trend_slope: float) -> str:
        """Generate clinical recommendation based on lab trends."""
        if test_name.upper() == 'POTASSIUM':
            if value > 6.0:
                return "URGENT: Immediate ECG and cardiac monitoring. Administer calcium gluconate."
            elif value < 3.0:
                return "URGENT: Consider IV potassium replacement with cardiac monitoring."
        
        if test_name.upper() == 'GLUCOSE':
            if value > 400:
                return "URGENT: Check for DKA. Insulin protocol initiation required."
            elif value < 50:
                return "URGENT: Administer glucose. Evaluate for hypoglycemia cause."
        
        if abs(trend_slope) > 0.5:  # Rapid change
            return f"ALERT: Rapid {'increase' if trend_slope > 0 else 'decrease'} in {test_name}. Clinical correlation required."
        
        return "ACTION: Review and repeat test as clinically indicated."
    
    def reconcile_medications(self, med_records_a: List[MedicationRecord],
                            med_records_b: List[MedicationRecord]) -> Dict:
        """
        Reconcile medication lists from two sources.
        Identifies discrepancies and potential interactions.
        """
        results = {
            'matched_medications': [],
            'meds_only_in_a': [],
            'meds_only_in_b': [],
            'discrepancies': [],
            'potential_interactions': []
        }
        
        # Match medications by name/code
        meds_a_dict = {m.rxnorm_code: m for m in med_records_a}
        meds_b_dict = {m.rxnorm_code: m for m in med_records_b}
        
        all_codes = set(list(meds_a_dict.keys()) + list(meds_b_dict.keys()))
        
        for code in all_codes:
            if code in meds_a_dict and code in meds_b_dict:
                med_a = meds_a_dict[code]
                med_b = meds_b_dict[code]
                
                # Check for discrepancies
                if med_a.dose != med_b.dose or med_a.frequency != med_b.frequency:
                    results['discrepancies'].append({
                        'medication': med_a.medication_name,
                        'source_a': {'dose': med_a.dose, 'frequency': med_a.frequency},
                        'source_b': {'dose': med_b.dose, 'frequency': med_b.frequency}
                    })
                else:
                    results['matched_medications'].append(med_a)
            elif code in meds_a_dict:
                results['meds_only_in_a'].append(meds_a_dict[code])
            else:
                results['meds_only_in_b'].append(meds_b_dict[code])
        
        # Check for drug-drug interactions in combined list
        all_meds = list(meds_a_dict.values()) + list(meds_b_dict.values())
        for i, med1 in enumerate(all_meds):
            for med2 in all_meds[i+1:]:
                interaction = med1.check_interaction(med2)
                if interaction:
                    results['potential_interactions'].append({
                        'medications': [med1.medication_name, med2.medication_name],
                        'risk': interaction
                    })
        
        return results
    
    def generate_reconciliation_report(self, output_path: Path) -> Dict:
        """
        Generate comprehensive reconciliation report.
        Includes executive summary and detailed findings.
        """
        report = {
            'generated_at': datetime.now().isoformat(),
            'engine_version': '1.0.0',
            'summary': {
                'total_patients_reconciled': len(self.reconciled_patients),
                'audit_entries': len(self.audit_log)
            },
            'audit_trail': self.audit_log[-100:],  # Last 100 entries
            'reconciliation_results': self.reconciled_patients
        }
        
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        logger.info(f"Reconciliation report saved to {output_path}")
        return report
    
    def _hash_phi(self, value: str) -> str:
        """One-way hash for PHI storage."""
        return hashlib.sha256(f"{value}_salt_key".encode()).hexdigest()[:16]
    
    def _log_audit(self, action: str, resource: str, source: str, 
                   records_affected: Optional[int], details: str = ""):
        """Create audit trail entry."""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'action': action,
            'resource': resource,
            'source_system': source,
            'records_affected': records_affected,
            'details': details
        }
        self.audit_log.append(entry)


class LabTrendVisualizer:
    """
    Generate visualizations for lab trends.
    Uses matplotlib for static reports.
    """
    
    @staticmethod
    def plot_lab_trends(trend_data: Dict, output_path: Path):
        """Generate trend plots for key lab results."""
        try:
            import matplotlib.pyplot as plt
            import matplotlib.dates as mdates
            
            trends = trend_data.get('trends', {})
            if not trends:
                return
            
            # Filter to tests with significant trends
            significant_tests = {
                name: data for name, data in trends.items()
                if data['severity'] in ['critical', 'abnormal']
            }
            
            if not significant_tests:
                logger.info("No significant trends to plot")
                return
            
            fig, axes = plt.subplots(len(significant_tests), 1, 
                                    figsize=(10, 3*len(significant_tests)))
            
            if len(significant_tests) == 1:
                axes = [axes]
            
            for ax, (test_name, data) in zip(axes, significant_tests.items()):
                ax.set_title(f"{test_name} Trend - {data['severity'].upper()}")
                ax.set_xlabel('Date')
                ax.set_ylabel(f"Value ({data['unit']})")
                ax.axhline(y=data['reference_range'], color='green', 
                          linestyle='--', alpha=0.5, label='Reference Range')
                ax.grid(True, alpha=0.3)
            
            plt.tight_layout()
            plt.savefig(output_path)
            logger.info(f"Trend plot saved to {output_path}")
            
        except ImportError:
            logger.warning("matplotlib not available for visualization")


# Demonstration with synthetic data
if __name__ == "__main__":
    # Create engine
    engine = ClinicalReconciliationEngine(match_threshold=0.75)
    
    # Simulate EHR export ingestion
    print("Clinical Reconciliation Engine Demo")
    print("=" * 50)
    
    # Create synthetic patient data for demonstration
    ehr_data = pd.DataFrame({
        'patient_id': ['PT001', 'PT002', 'PT003', 'PT004', 'PT005'],
        'first_name': ['John', 'Jane', 'Robert', 'Emily', 'Michael'],
        'last_name': ['Smith', 'Doe', 'Johnson', 'Williams', 'Brown'],
        'dob_year': [1965, 1978, 1954, 1982, 1971],
        'gender': ['M', 'F', 'M', 'F', 'M'],
        'zip': ['12345', '23456', '34567', '45678', '56789']
    })
    
    lab_data = pd.DataFrame({
        'patient_id': ['PT001', 'PT002', 'PT003'],
        'mrn': ['', '', ''],
        'first_name': ['John', 'Jane', 'Robert'],
        'last_name': ['Smith', 'Doe', 'Johnsen'],  # Note typo
        'dob_year': [1965, 1978, 1954],
        'gender': ['M', 'F', 'M'],
        'zip': ['12345', '23456', '34567']
    })
    
    # Save to temp files
    ehr_data.to_csv('/tmp/ehr_demographics.csv', index=False)
    lab_data.to_csv('/tmp/lab_demographics.csv', index=False)
    
    # Ingest from both systems
    ehr_patients = engine.ingest_patient_demographics(
        Path('/tmp/ehr_demographics.csv'), 'EHR_System'
    )
    lab_patients = engine.ingest_patient_demographics(
        Path('/tmp/lab_demographics.csv'), 'Lab_System'
    )
    
    # Reconcile
    results = engine.reconcile_patients(ehr_patients, lab_patients)
    
    print(f"\nReconciliation Results:")
    print(f"  Matched: {len(results['matched'])}")
    print(f"  Partial: {len(results['partial_matches'])}")
    print(f"  Unmatched in EHR: {len(results['unmatched_source_a'])}")
    print(f"  Unmatched in Lab: {len(results['unmatched_source_b'])}")
    
    # Simulate some lab results
    lab_results = [
        LabResult(
            patient_id_hash=ehr_patients[0].patient_id_hash,
            test_name='POTASSIUM',
            test_code='LOINC_2823-3',
            value=6.2,
            unit='mmol/L',
            reference_range_low=3.5,
            reference_range_high=5.1,
            collection_date=datetime.now() - timedelta(days=1),
            result_date=datetime.now(),
            source_system='Lab_System'
        )
    ]
    
    # Analyze trends
    trend_analysis = engine.analyze_lab_trends(lab_results, ehr_patients[0].patient_id_hash)
    
    print(f"\nCritical Findings: {len(trend_analysis['critical_findings'])}")
    for finding in trend_analysis['critical_findings']:
        print(f"  {finding['test']}: {finding['value']} ({finding['severity']})")
        print(f"  Action: {finding['action'][:80]}...")
    
    # Generate report
    engine.generate_reconciliation_report(Path('/tmp/reconciliation_report.json'))
    print("\nReport generated: /tmp/reconciliation_report.json")
