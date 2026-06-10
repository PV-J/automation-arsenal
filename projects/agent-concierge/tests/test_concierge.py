"""
Tests for Agent Concierge intent classification and safety validation.
Run: pytest tests/ -v
"""

import pytest
import sys
from pathlib import Path

# Add concierge to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from concierge import IntentRouter, Intent, RoutedRequest


class TestIntentClassification:
    """Test that the keyword router classifies intents correctly."""

    def setup_method(self):
        self.router = IntentRouter()

    def test_health_check_intent(self):
        result = self.router.classify("Is the auth API slow today?")
        assert result.intent == Intent.CHECK_SERVICE_HEALTH

    def test_lab_results_intent(self):
        result = self.router.classify("Show me critical potassium levels")
        assert result.intent == Intent.ANALYZE_LAB_RESULTS

    def test_invoice_intent(self):
        result = self.router.classify("Extract data from invoice INV-2026-0042")
        assert result.intent == Intent.PROCESS_INVOICES

    def test_duplicate_intent(self):
        result = self.router.classify(
            "Find duplicate identical copies of the same file and remove redundancy"
        )
        assert result.intent == Intent.FIND_DUPLICATES

    def test_organize_intent(self):
        result = self.router.classify("Organize my desktop folder")
        assert result.intent == Intent.ORGANIZE_FILES

    def test_ambiguous_input_falls_to_general(self):
        result = self.router.classify("help")
        assert result.intent == Intent.GENERAL_QUESTION

    def test_empty_input(self):
        result = self.router.classify("")
        assert result.intent == Intent.GENERAL_QUESTION


class TestSafetyValidation:
    """Test that dangerous requests trigger safety flags."""

    def setup_method(self):
        self.router = IntentRouter()

    def test_healthcare_triggers_safety(self):
        result = self.router.classify("Show me patient lab results")
        assert "healthcare_data_access" in result.safety_flags
        assert result.requires_confirmation is True

    def test_reconcile_patients_triggers_safety(self):
        result = self.router.classify("Reconcile patient records between EHR and lab")
        assert "healthcare_data_access" in result.safety_flags
        assert result.requires_confirmation is True

    def test_filesystem_modification_flagged(self):
        result = self.router.classify("Organize my desktop folder")
        assert "filesystem_modification" in result.safety_flags

    def test_health_check_is_safe(self):
        result = self.router.classify("Is the API healthy?")
        assert len(result.safety_flags) == 0
        assert result.requires_confirmation is False

    def test_invoice_processing_is_safe(self):
        result = self.router.classify("Process invoice PDF")
        assert len(result.safety_flags) == 0
        assert result.requires_confirmation is False


class TestConfidenceScoring:
    """Test confidence scores reflect match quality."""

    def setup_method(self):
        self.router = IntentRouter()

    def test_high_confidence_for_clear_match(self):
        result = self.router.classify(
            "Check the health of the auth API endpoint and monitor response time"
        )
        assert result.confidence > 0.5

    def test_low_confidence_for_vague_input(self):
        result = self.router.classify("invoice")
        assert result.confidence < 0.5

    def test_zero_confidence_for_no_match(self):
        result = self.router.classify("xyzzy flobber gargleblaster")
        assert result.confidence == 0.0


class TestParameterExtraction:
    """Test that time ranges and parameters are extracted."""

    def setup_method(self):
        self.router = IntentRouter()

    def test_extracts_today(self):
        result = self.router.classify("Any critical labs today?")
        assert result.parameters.get("time_range") == "today"

    def test_extracts_week(self):
        result = self.router.classify("Show me lab results from this week")
        assert result.parameters.get("time_range") == "week"

    def test_default_time_range(self):
        result = self.router.classify("Show me lab results")
        assert result.parameters.get("time_range") == "latest"