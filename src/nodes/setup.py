import json
import os
from typing import Dict, Any
from src.state import AgentState
from src.tools.repo_tools import safe_git_clone
from src.tools.doc_tools import ingest_pdf


def setup_node(state: AgentState) -> AgentState:
    """
    Phase 1 / entry node: 
    - Safely clone the target GitHub repo
    - Ingest and chunk the PDF report
    - Load the machine-readable rubric.json
    - Initialize state counters and collections
    """
    repo_url = state["repo_url"]
    pdf_path = state["pdf_path"]

    # 1. Safe repo clone (sandboxed tempfile)
    clone_result: Dict[str, Any] = safe_git_clone.invoke({"repo_url": repo_url})
    if not clone_result["success"]:
        raise RuntimeError(f"Git clone failed: {clone_result.get('error', 'Unknown error')}")
    
    repo_path = clone_result["path"]
    state["repo_path"] = repo_path  # temporary path — cleaned up automatically

    # 2. Ingest PDF report (RAG-lite chunking)
    pdf_result: Dict[str, Any] = ingest_pdf.invoke({"pdf_path": pdf_path})
    if not pdf_result["success"]:
        raise RuntimeError(f"PDF ingestion failed: {pdf_result.get('error', 'Unknown error')}")
    
    state["pdf_chunks"] = pdf_result["chunks"]      # for DocAnalyst queries
    state["pdf_full_length"] = pdf_result["total_length"]

    # 3. Load rubric constitution (dynamic scoring rules)
    rubric_path = os.path.join(os.path.dirname(__file__), "../../rubric/week2_rubric.json")
    if not os.path.exists(rubric_path):
        raise FileNotFoundError(f"Rubric not found at {rubric_path}")
    
    with open(rubric_path, "r", encoding="utf-8") as f:
        rubric = json.load(f)
    
    state["rubric"] = rubric
    state["rubric_dimensions"] = rubric["dimensions"]
    state["current_dimension_index"] = 0

    # 4. Initialize accumulators (reducers will handle parallel updates later)
    state["evidences"] = {}
    state["opinions"] = []
    state["final_report"] = None

    return state