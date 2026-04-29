# Automation Arsenal

**Production-grade automation scripts across four critical domains.**

Every script in this repository follows the same engineering standards:
comprehensive error handling, structured logging, type hints, test coverage,
and detailed documentation. These aren't tutorials — they're ready to deploy.

## 🎯 Projects

| Project | Domain | Key Capability |
|---------|--------|---------------|
| [**FinVoice**](projects/finvoice/) | Finance | PDF invoice extraction → accounting pipeline |
| [**WatchTower**](projects/watchtower/) | DevOps/SRE | Multi-endpoint health monitoring with trend analysis |
| [**DeClutter**](projects/declutter/) | Data Management | Content-aware deduplication & intelligent file organization |
| [**MedRecon**](projects/medrecon/) | Healthcare | Patient data reconciliation & clinical anomaly detection |

## 🏗️ Architecture

All projects share:
- **Structured logging** with domain-appropriate redaction (PHI filtering in MedRecon)
- **Async I/O** where beneficial (WatchTower, DeClutter)
- **Audit trails** for regulated workflows (FinVoice, MedRecon)
- **Configurable thresholds** — no hardcoded business rules
- **Dry-run modes** for safe testing

See [Architecture Decisions](docs/architecture.md) for design rationale.

## ⚡ Quick Start

```bash
# Clone and set up
git clone https://github.com/YOUR_USERNAME/automation-arsenal.git
cd automation-arsenal
./scripts/setup.sh

# Run any project
python -m projects.finvoice.invoice_pipeline --input sample_data/ --output results/
python -m projects.watchtower.monitor --config projects/watchtower/config.yaml
python -m projects.declutter.organizer ~/Downloads --dry-run
python -m projects.medrecon.clinical_recon --ehr sample_data/ehr.csv --lab sample_data/lab.csv

## 📸 See It In Action

**FinVoice** — Extracting structured data from a messy PDF invoice:
