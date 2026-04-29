"""
generate_sample.py
Creates a realistic sample invoice PDF for FinVoice demonstration.
Run once: python generate_sample.py
Output: sample_invoice.pdf in the same directory
"""

from fpdf import FPDF
from pathlib import Path
from datetime import datetime, timedelta


class InvoicePDF(FPDF):
    """Generate a realistic invoice PDF with header, line items, and totals."""

    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=20)

    def header(self):
        """Company header with logo placeholder and invoice title."""
        # Company name
        self.set_font("Helvetica", "B", 18)
        self.set_text_color(40, 60, 120)
        self.cell(0, 10, "ACME CORPORATION", ln=True, align="L")

        # Company details
        self.set_font("Helvetica", "", 9)
        self.set_text_color(100, 100, 100)
        self.cell(0, 5, "123 Business Park Drive, Suite 400", ln=True, align="L")
        self.cell(0, 5, "San Francisco, CA 94105 | Tax ID: 12-3456789", ln=True, align="L")
        self.cell(0, 5, "Phone: (415) 555-0192 | billing@acmecorp.example.com", ln=True, align="L")

        # Separator line
        self.ln(4)
        self.set_draw_color(40, 60, 120)
        self.set_line_width(0.5)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(6)

    def footer(self):
        """Page footer with page number and payment terms."""
        self.set_y(-25)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")

    def invoice_title(self, invoice_number: str, invoice_date: str, due_date: str):
        """Large INVOICE title with number and dates."""
        self.set_font("Helvetica", "B", 26)
        self.set_text_color(40, 60, 120)
        self.cell(0, 12, "INVOICE", ln=True, align="L")

        self.set_font("Helvetica", "", 10)
        self.set_text_color(60, 60, 60)
        self.cell(0, 6, f"Invoice #: {invoice_number}", ln=True, align="L")
        self.cell(0, 6, f"Invoice Date: {invoice_date}", ln=True, align="L")
        self.cell(0, 6, f"Due Date: {due_date}", ln=True, align="L")
        self.ln(6)

    def bill_to_section(self, company: str, contact: str, address: str, email: str):
        """Bill To section with recipient details."""
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(40, 60, 120)
        self.cell(0, 6, "Bill To:", ln=True, align="L")

        self.set_font("Helvetica", "", 10)
        self.set_text_color(60, 60, 60)
        self.cell(0, 5, company, ln=True, align="L")
        self.cell(0, 5, f"Attn: {contact}", ln=True, align="L")
        self.cell(0, 5, address, ln=True, align="L")
        self.cell(0, 5, email, ln=True, align="L")
        self.ln(6)

    def line_item_table(self, items: list[dict]):
        """Professional line item table with headers, rows, and subtotal."""
        # Column widths
        col_widths = [16, 72, 18, 20, 26, 28]
        headers = ["Item #", "Description", "Qty", "Unit", "Rate ($)", "Amount ($)"]
        total_width = sum(col_widths)

        # Table header
        self.set_fill_color(40, 60, 120)
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 9)

        for i, header in enumerate(headers):
            align = "R" if i >= 2 else "L"
            self.cell(col_widths[i], 8, header, border=1, fill=True, align=align)
        self.ln()

        # Table rows
        self.set_font("Helvetica", "", 9)
        subtotal = 0

        for idx, item in enumerate(items):
            row_total = item["qty"] * item["rate"]
            subtotal += row_total

            # Alternating row colors
            if idx % 2 == 0:
                self.set_fill_color(245, 247, 250)
                self.set_text_color(60, 60, 60)
            else:
                self.set_fill_color(255, 255, 255)
                self.set_text_color(60, 60, 60)

            row_data = [
                str(item["item_num"]),
                item["description"],
                str(item["qty"]),
                item["unit"],
                f"${item['rate']:,.2f}",
                f"${row_total:,.2f}",
            ]

            for i, value in enumerate(row_data):
                align = "R" if i >= 2 else "L"
                self.cell(col_widths[i], 7, value, border=1, fill=True, align=align)
            self.ln()

        return subtotal

    def totals_section(self, subtotal: float, tax_rate: float = 0.08):
        """Subtotal, tax, and total with bold styling."""
        tax = round(subtotal * tax_rate, 2)
        total = subtotal + tax
        label_width = 150
        value_width = 30

        self.ln(3)

        # Subtotal
        self.set_font("Helvetica", "", 10)
        self.set_text_color(60, 60, 60)
        self.cell(label_width, 7, "", align="R")
        self.cell(value_width, 7, "Subtotal:", align="R")
        self.cell(value_width, 7, f"${subtotal:,.2f}", align="R", ln=True)

        # Tax
        self.cell(label_width, 7, "", align="R")
        self.cell(value_width, 7, f"Tax (8%):", align="R")
        self.cell(value_width, 7, f"${tax:,.2f}", align="R", ln=True)

        # Separator before total
        self.cell(label_width, 2, "", align="R")
        y_before = self.get_y()
        self.set_draw_color(40, 60, 120)
        self.set_line_width(0.3)
        self.cell(value_width + value_width, 2, "", border="T", align="R", ln=True)

        # Total
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(40, 60, 120)
        self.cell(label_width, 8, "", align="R")
        self.cell(value_width, 8, "Total Due:", align="R")
        self.cell(value_width, 8, f"${total:,.2f}", align="R", ln=True)

        self.ln(6)
        return total

    def payment_instructions(self):
        """Payment details and notes."""
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(40, 60, 120)
        self.cell(0, 6, "Payment Instructions", ln=True, align="L")

        self.set_font("Helvetica", "", 9)
        self.set_text_color(100, 100, 100)
        self.cell(0, 5, "Bank Transfer: Acme Corp | Routing: 121000248 | Account: 9876543210", ln=True, align="L")
        self.cell(0, 5, "Please include invoice number in payment reference.", ln=True, align="L")
        self.cell(0, 5, "Payment terms: Net 30 days. Late payments subject to 1.5% monthly interest.", ln=True, align="L")


def create_sample_invoice(output_path: str = "sample_invoice.pdf"):
    """Generate a realistic sample invoice and save to output_path."""

    invoice_number = f"INV-{datetime.now().strftime('%Y')}-{42:04d}"
    invoice_date = datetime.now().strftime("%B %d, %Y")
    due_date = (datetime.now() + timedelta(days=30)).strftime("%B %d, %Y")

    pdf = InvoicePDF()
    pdf.alias_nb_pages()
    pdf.add_page()

    # Invoice title
    pdf.invoice_title(invoice_number, invoice_date, due_date)

    # Bill To
    pdf.bill_to_section(
        company="TechSolutions Inc.",
        contact="Sarah Johnson, Accounts Payable",
        address="456 Innovation Drive, Austin, TX 78701",
        email="ap@techsolutions.example.com",
    )

    # Line items
    items = [
        {"item_num": 1, "description": "Cloud Infrastructure Setup - Initial Deployment", "qty": 1, "unit": "project", "rate": 2500.00},
        {"item_num": 2, "description": "API Integration Services (40 hours @ $150/hr)", "qty": 40, "unit": "hours", "rate": 150.00},
        {"item_num": 3, "description": "Data Migration - Legacy System to Cloud", "qty": 1, "unit": "project", "rate": 1800.00},
        {"item_num": 4, "description": "Security Audit & Compliance Review", "qty": 1, "unit": "audit", "rate": 3200.00},
        {"item_num": 5, "description": "Monthly Monitoring & Support (Annual Contract)", "qty": 12, "unit": "months", "rate": 450.00},
    ]

    subtotal = pdf.line_item_table(items)
    pdf.totals_section(subtotal, tax_rate=0.08)
    pdf.payment_instructions()

    # Save
    output = Path(output_path)
    pdf.output(str(output))
    print(f"Sample invoice created: {output.absolute()}")
    print(f"Invoice #: {invoice_number}")
    print(f"Subtotal: ${subtotal:,.2f}")
    print(f"Total: ${subtotal * 1.08:,.2f}")
    return output


if __name__ == "__main__":
    create_sample_invoice()
