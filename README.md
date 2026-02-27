# The Automaton Auditor — Final Submission

This project implements a hierarchical Deep LangGraph swarm that audits Week 2 repositories and architectural reports.

High level:
- Detectives (RepoInvestigator, DocAnalyst, VisionInspector) collect structured Pydantic `Evidence` objects.
- Judges (Prosecutor, Defense, TechLead) run in parallel and emit `JudicialOpinion` objects.
- ChiefJustice applies deterministic synthesis rules (security override, fact supremacy, dissent handling) and emits a final `AuditReport` serialized to Markdown and PDF.

Project structure (full tree)
``` 
TRP1-WEEK2-AUTOMATON-AUDITOR/
├── audit/
│   ├── report_bypeer_received/       # Reports received from peers
│   ├── report_onpeer_generated/      # Reports generated about peers
│   ├── report_onself_generated/      # Self-evaluation reports
│   └── reports/
│       ├── final_report.md           # Final audit report (markdown)
│       ├── final_report.pdf          # Final audit report (PDF)
│       └── interim-report.pdf        # Interim / progress report
├── src/
│   ├── nodes/
│   │   ├── init.py
│   │   ├── detectives.py             # Detective node logic
│   │   ├── judges.py                 # Judge node logic
│   │   └── justice.py                # Justice / final decision node
│   ├── tools/
│   │   ├── init.py
│   │   ├── doc_tools.py              # Document processing utilities
│   │   └── repo_tools.py             # Repository analysis utilities
│   ├── init.py
│   ├── graph.py                      # Graph / workflow logic
│   └── state.py                      # Shared state management
├── tests/                            # Unit & integration tests
├── .env.example                      # Template for environment variables
├── .gitignore
├── .python-version
├── Dockerfile
├── LICENSE
├── main.py                           # Main entry point
├── pyproject.toml                    # Project metadata & dependencies
├── README.md
├── rubrics.json                      # Evaluation criteria / scoring rubrics
└── uv.lock                           # Lockfile (uv / rye / hatch / pip-tools)
```
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

This repository now includes a `Dockerfile` to build a containerized runtime for the auditor. The container installs the project from `pyproject.toml` and exposes a CLI entrypoint for `src/graph.py`.

Build the image locally:

```bash
docker build -t automaton-auditor:latest .
```

Run the auditor in a container (example):

```bash
# Run interactively and map the workspace so reports and audit outputs are persisted locally
docker run --rm -it \
	-e OPENAI_API_KEY=$OPENAI_API_KEY \
	-v "$PWD":/app \
	automaton-auditor:latest \
	python src/graph.py --repo "https://github.com/<target_repo>" --pdf "/app/reports/final_report.pdf"
```

Notes:
- Mount the workspace (`-v "$PWD":/app`) so generated reports (`/app/audit/` and `/app/reports/`) are available on the host.
- Pass required env vars (e.g., `OPENAI_API_KEY`) into the container via `-e` or an env file.
- If you want the container to generate the PDF, ensure system libraries for PDF rendering are present or perform PDF conversion on the host (we provide `final_report.md`).

LangSmith tracing (optional, recommended for grading)

This project can emit LangSmith traces for the full reasoning loop (detectives → judges → Chief Justice). To enable tracing, set the tracing flag and provide a LangSmith/LangChain API key in your environment before running the auditor.

Required environment variables (example):

```bash
export LANGCHAIN_TRACING_V2=true
export LANGCHAIN_API_KEY=<your_langchain_or_langsmith_api_key>
# Optional: set a project name to group runs
export LANGCHAIN_PROJECT=automaton-auditor
```

Run the auditor as usual; when tracing is enabled the `src/graph.py` runner will attempt to create a LangSmith Run and will print a best-effort URL after completion, e.g.:

```
LangSmith run available at: https://app.langchain.com/runs/<run-id>
```

If you don't see a URL printed, ensure the API key and tracing flag are set and that the host can reach LangSmith endpoints. Traces will appear in the LangChain / LangSmith dashboard under the configured project name.

Privacy note: traces may include inputs/outputs and metadata. Only enable tracing when you are comfortable with uploading run artifacts to your LangSmith project.

How to extend
- Add more forensic checks in `src/tools/repo_tools.py` (AST-based proofs are preferred over regex).
- Improve `doc_tools.ingest_pdf` with OCR or image extraction for richer diagram analysis.
- Replace heuristic judge logic with LLM calls bound to `JudicialOpinion` using `.with_structured_output()` for stronger dialectical opinions.

Contact / License
- MIT. See `LICENSE` for details.

Enjoy — run the auditor against peers' repos and iterate on the MinMax loop.
