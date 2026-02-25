# The Automaton Auditor (Interim Submission)
FDE Challenge Week 2: Orchestrating Deep LangGraph Swarms for Autonomous Governance

The Automaton Auditor is a Deep LangGraph Swarm designed to autonomously governance code repositories. 

This repository reflects the **Interim Phase**, containing the Detective Layer. It utilizes isolated Detectives (`RepoInvestigator`, `DocAnalyst`, and `VisionInspector`) running in a Fan-Out pattern, parsing GitHub Repositories (AST verification, git log analysis) and PDF documentation. It extracts structured Pydantic `Evidence` objects and aggregates them via a central Fan-In node (`EvidenceAggregator`).

## Architecture (Interim)

- **Layer 1: Detectives** execute Forensics by collecting parsed evidence:
  - `RepoInvestigator`: Clones the repo to a sandboxed `tempfile` and uses Python `ast` to verify `StateGraph` usage and typed reducers.
  - `DocAnalyst`: Uses `docling` to chunk and semantically review PDF files.
  - `VisionInspector`: Extensible node for diagram analysis.
- **Layer 2: Synchronization** (`EvidenceAggregator`) enforces a Fan-In state synchronization, outputting the gathered proof locally.
- *(Judges and ChiefJustice logic reserved for Final Submission).*

## Prerequisites

Before setting up the project, ensure you have the following installed:

- **[uv](https://docs.astral.sh/uv/)**: A fast Python package and project manager.
- **Git**: Required for cloning target repositories for analysis.
- **System Dependencies**: Some dependencies (like `docling`) may require standard build tools or specific libraries depending on your OS.

## Setup Instructions

This project uses `uv` for minimal, lightning-fast dependency management.

1. Ensure `uv` is installed globally.
2. Initialize environment:
```bash
uv sync
```
3. **Setup Environment Variables**:
   Copy the example file and fill in your credentials:
   ```bash
   cp .env.example .env
   ```

   | Variable | Description | Required |
   | :--- | :--- | :--- |
   | `OPENAI_API_KEY` | Your OpenAI API key for LLM analysis. | Yes |
   | `LANGCHAIN_TRACING_V2` | Enable LangSmith tracing (set to `true`). | No |
   | `LANGCHAIN_API_KEY` | Your LangSmith API key. | No |
   | `LANGCHAIN_PROJECT` | Project name for LangSmith. | No |

## Running the Swarm

The interim graph requires a target `--repo` and target `--pdf`.

```bash
uv run python src/graph.py --repo "https://github.com/gashawbekele06/trp1-week2-automaton-auditor.git" --pdf "reports/interim_report.pdf"
```
