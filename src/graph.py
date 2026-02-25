from langgraph.graph import StateGraph, START, END, Send
from src.state import AgentState
from src.nodes.setup import setup_node
from src.nodes.detectives import detective_node
from src.nodes.aggregator import evidence_aggregator
from src.nodes.judges import judge_node
from src.nodes.justice import chief_justice_node
import json
import argparse
import sys
import os

# Ensure the project root is on the path so `src` is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langgraph.graph import StateGraph, START, END
from src.state import AgentState
from src.nodes.detectives import repo_investigator, doc_analyst, vision_inspector


def evidence_aggregator(state: AgentState):
    """Synchronization node (Fan-In) collecting all evidence."""
    print("\n--- EVIDENCE AGGREGATED ---")
    evidences = state.get("evidences", {})
    for dim, ev_list in evidences.items():
        print(f"Dimension: {dim} - Found {len(ev_list)} evidence items.")
        for ev in ev_list:
             print(f"  - [{ev.found}] {ev.goal}: {ev.rationale}")
    return {"evidences": evidences}


def build_interim_graph() -> StateGraph:
    """Constructs the Interim Deep LangGraph Swarm architecture (Detectives Only)."""
    workflow = StateGraph(AgentState)

    # Layer 1: The Detective Layer
    workflow.add_node("RepoInvestigator", repo_investigator)
    workflow.add_node("DocAnalyst", doc_analyst)
    workflow.add_node("VisionInspector", vision_inspector)

    # Layer 2: Aggregation
    workflow.add_node("EvidenceAggregator", evidence_aggregator)

    # Fan-Out to Detectives
    workflow.add_edge(START, "RepoInvestigator")
    workflow.add_edge(START, "DocAnalyst")
    workflow.add_edge(START, "VisionInspector")

    # Fan-In to Evidence Aggregator
    workflow.add_edge("RepoInvestigator", "EvidenceAggregator")
    workflow.add_edge("DocAnalyst", "EvidenceAggregator")
    workflow.add_edge("VisionInspector", "EvidenceAggregator")

    # Judges not required yet per Interim Submission instructions
    workflow.add_edge("EvidenceAggregator", END)

    return workflow.compile()


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    parser = argparse.ArgumentParser(description="Run the Interim Automaton Auditor Swarm.")
    parser.add_argument("--repo", type=str, required=True, help="GitHub repository URL to evaluate")
    parser.add_argument("--pdf", type=str, required=True, help="Path to the PDF architectural report")
    args = parser.parse_args()

    with open("rubric.json", "r", encoding="utf-8") as f:
         rubric_data = json.load(f)

    initial_state = {
        "repo_url": args.repo,
        "pdf_path": args.pdf,
        "rubric_dimensions": rubric_data["dimensions"],
        "synthesis_rules": rubric_data.get("synthesis_rules", {}),
        "evidences": {},
        "opinions": []
    }

    print(f"Starting Interim Automaton Auditor for {args.repo}...")
    app = build_interim_graph()

    final_output = app.invoke(initial_state)
    print("\n--- INTERIM EXECUTION COMPLETE ---")
    print("Collected Evidence Keys:", list(final_output.get("evidences", {}).keys()))


graph = StateGraph(AgentState)

# Nodes
graph.add_node("setup", setup_node)
graph.add_node("detective", detective_node)
graph.add_node("aggregator", evidence_aggregator)

# Judge nodes
graph.add_node("prosecutor", lambda s: judge_node(s, "Prosecutor"))
graph.add_node("defense", lambda s: judge_node(s, "Defense"))
graph.add_node("techlead", lambda s: judge_node(s, "TechLead"))

# Chief Justice
graph.add_node("justice", chief_justice_node)

# Edges & conditionals (from Phase 3) remain the same
# ...

graph.add_edge("justice", END)

app = graph.compile()

def run_self_audit(repo_url: str, pdf_path: str) -> None:
    """Operationalize MinMax feedback loop: run graph on own repo, print remediation summary."""
    result = app.invoke({
        "repo_url": repo_url,
        "pdf_path": pdf_path,
    })
    report = result["final_report"]
    print("Self-audit complete. Remediation summary:")
    print(report.remediation_plan)
    # Manual step: use this to refine code, then re-run