# The Automaton Auditor — Final Submission

This project implements a hierarchical Deep LangGraph swarm that audits Week 2 repositories and architectural reports.

High level:
- Detectives (RepoInvestigator, DocAnalyst, VisionInspector) collect structured Pydantic `Evidence` objects.
- Judges (Prosecutor, Defense, TechLead) run in parallel and emit `JudicialOpinion` objects.
- ChiefJustice applies deterministic synthesis rules (security override, fact supremacy, dissent handling) and emits a final `AuditReport` serialized to Markdown and PDF.

Repository layout (key files)
- `src/state.py` — Pydantic models and TypedDict AgentState.
- `src/tools/repo_tools.py` — sandboxed cloning, git history extraction, AST analysis.
- `src/tools/doc_tools.py` — PDF ingestion and lightweight keyword/filepath extraction.
- `src/nodes/detectives.py` — `repo_investigator`, `doc_analyst`, `vision_inspector`.
- `src/nodes/judges.py` — `prosecutor_judge`, `defense_judge`, `techlead_judge` (structured outputs / stubbed LLM bindings).
- `src/nodes/justice.py` — `chief_justice` deterministic synthesis and report generation.
- `src/graph.py` — StateGraph wiring (detectives fan-out, evidence fan-in, judges fan-out, chief justice).

Prerequisites
- Python >= 3.12 (this repo uses 3.12 in pyproject)
- `uv` (recommended) or use `pip` inside a venv
- Git
- Optional: `weasyprint`/`pandoc` to convert the final Markdown to PDF locally

Quick setup (recommended)
1. Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies (using `uv` if you have it):

```bash
# with uv
uv sync
# or with pip (inside venv)
python -m pip install -e .
```

3. Copy `.env.example` and fill keys:

```bash
cp .env.example .env
# set OPENAI_API_KEY and optional LangSmith settings
```

Run the auditor

Interim (detectives only):

```bash
uv run python src/graph.py --repo "https://github.com/<target_repo>" --pdf "reports/interim-report..pdf"
```

Final (use your final PDF report):

```bash
uv run python src/graph.py --repo "https://github.com/<target_repo>" --pdf "reports/final-report.pdf"
```

Outputs
- `audit/report_onself_generated/audit_report.md` — structured per-criterion audit (machine-readable, Pydantic-backed objects serialized as Markdown).
- `audit/report_onself_generated/final_report.md` — human-facing final report ready for PDF conversion.
- `reports/final_report_generated.pdf` — generated PDF (committed) from `final_report.md`.

Convert `final_report.md` to PDF locally

Option A — weasyprint (recommended for HTML rendering):

```bash
python -m pip install weasyprint markdown2
python - <<'PY'
import markdown2
from weasyprint import HTML
html = markdown2.markdown(open('audit/report_onself_generated/final_report.md').read())
HTML(string=html).write_pdf('reports/final_report_generated.pdf')
print('Wrote reports/final_report_generated.pdf')
PY
```

Option B — pandoc (if available):

```bash
pandoc audit/report_onself_generated/final_report.md -o reports/final_report_generated.pdf
```

Notes & limitations
- The repository includes heuristic (local) judge implementations to keep the agent self-contained. You can upgrade the judges to real LLM-backed personas by replacing the stubs in `src/nodes/judges.py` with calls to an LLM and using `.with_structured_output(JudicialOpinion)`.
- The environment used for automated testing here may not allow installing system packages; if PDF conversion fails locally, run conversion in your development environment.

Docker (optional)
- You can containerize the runtime; a Dockerfile is recommended but not included by default. If you want, I can add one.

How to extend
- Add more forensic checks in `src/tools/repo_tools.py` (AST-based proofs are preferred over regex).
- Improve `doc_tools.ingest_pdf` with OCR or image extraction for richer diagram analysis.
- Replace heuristic judge logic with LLM calls bound to `JudicialOpinion` using `.with_structured_output()` for stronger dialectical opinions.

Contact / License
- MIT. See `LICENSE` for details.

Enjoy — run the auditor against peers' repos and iterate on the MinMax loop.
