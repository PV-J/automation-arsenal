# FinVoice — Invoice Data Extraction & Accounting Pipeline

**Problem:** Finance teams waste hours manually extracting data from supplier invoices in varying formats and entering it into accounting systems.

**Solution:** An end-to-end pipeline that ingests PDF invoices, extracts structured data using text parsing with OCR fallback, validates totals against line items, and exports accounting-ready CSV files with a complete audit trail.

## What It Does

- Parses standard and multi-page PDF invoices
- Falls back to OCR for image-based or scanned invoices
- Validates arithmetic (subtotal + tax = total)
- Detects duplicate invoices
- Generates timestamped CSV output ready for import into QuickBooks, Xero, or SAP
- Logs every action for audit compliance

## Architecture Decision: Why pdfplumber over PyPDF2

pdfplumber preserves table structure and character positioning, which matters when invoices use varying layouts. PyPDF2 loses spatial information that is critical for extracting line items from non-table formats.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Process a single invoice
python invoice_pipeline.py --input sample_data/invoice.pdf --output results/

# Process all PDFs in a folder
python invoice_pipeline.py --input sample_data/ --output results/ --batch

# Dry run (validate without saving)
python invoice_pipeline.py --input sample_data/ --dry-run

Expected Output

results/
├── processed_invoices_20260127_143022.csv
├── audit_trail_20260127_143022.json
└── logs/
    └── pipeline.log
	
Sample CSV Output

Invoice_Number	Vendor	Invoice_Date	Due_Date	Subtotal	Tax	    Total
INV-2026-0042	Acme Corp	2026-01-15	2026-02-15	1250.00	  100.00	1350.00

Edge Cases Handled

    Missing fields: Logged as warnings, not crashes

    Currency symbols: Stripped automatically

    Multi-currency: Detected from invoice text and preserved

    Zero-amount invoices: Flagged for manual review

    Corrupted PDFs: Skipped with error logged to audit trail

Limits

    Does not handle handwritten invoices (requires human review)

    Assumes English-language invoices by default (extendable via config)

    Table extraction accuracy depends on PDF generation quality

Dependencies

See requirements.txt.

License

MIT