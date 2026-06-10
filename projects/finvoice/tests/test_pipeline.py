"""
Tests for FinVoice invoice extraction pipeline.
Run: pytest tests/ -v
"""

import pytest
from pathlib import Path
import pandas as pd
from datetime import datetime

# Adjust import based on your actual module structure
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from invoice_pipeline import InvoiceData, AccountingPipeline


class TestInvoiceValidation:
    """Test invoice data validation logic."""

    def test_valid_invoice_passes_all_checks(self):
        invoice = InvoiceData(
            invoice_number="INV-001",
            vendor_name="Acme Corp",
            invoice_date=datetime(2026, 1, 1),
            due_date=datetime(2026, 2, 1),
            line_items=[{"desc": "Service", "amount": 100.00}],
            subtotal=100.00,
            tax=8.00,
            total=108.00,
        )
        result = invoice.validate()
        assert result["invoice_number_exists"] is True
        assert result["dates_valid"] is True
        assert result["total_matches"] is True
        assert result["positive_amounts"] is True

    def test_total_mismatch_detected(self):
        invoice = InvoiceData(
            invoice_number="INV-002",
            vendor_name="Acme Corp",
            invoice_date=datetime(2026, 1, 1),
            due_date=datetime(2026, 2, 1),
            line_items=[{"desc": "Service", "amount": 100.00}],
            subtotal=100.00,
            tax=8.00,
            total=200.00,  # Wrong: should be 108.00
        )
        result = invoice.validate()
        assert result["total_matches"] is False

    def test_negative_amount_flagged(self):
        invoice = InvoiceData(
            invoice_number="INV-003",
            vendor_name="Acme Corp",
            invoice_date=datetime(2026, 1, 1),
            due_date=datetime(2026, 2, 1),
            line_items=[],
            subtotal=-50.00,
            tax=0.00,
            total=-50.00,
        )
        result = invoice.validate()
        assert result["positive_amounts"] is False

    def test_due_date_before_invoice_date_rejected(self):
        invoice = InvoiceData(
            invoice_number="INV-004",
            vendor_name="Acme Corp",
            invoice_date=datetime(2026, 2, 1),
            due_date=datetime(2026, 1, 1),  # Due before issued
            line_items=[],
            subtotal=100.00,
            tax=0.00,
            total=100.00,
        )
        result = invoice.validate()
        assert result["dates_valid"] is False


class TestPipelineBatchProcessing:
    """Test end-to-end batch processing."""

    def test_empty_directory_returns_empty_dataframe(self, tmp_path):
        pipeline = AccountingPipeline(
            input_dir=str(tmp_path),
            output_dir=str(tmp_path / "output")
        )
        result = pipeline.process_batch()
        assert len(result) == 0

    def test_audit_log_generated(self, tmp_path):
        pipeline = AccountingPipeline(
            input_dir=str(tmp_path),
            output_dir=str(tmp_path / "output")
        )
        pipeline.process_batch()
        assert len(pipeline.audit_log) > 0

