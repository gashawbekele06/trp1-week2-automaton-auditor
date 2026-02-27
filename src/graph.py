import json
import argparse
import sys
import os

# Ensure the project root is on the path so `src` is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langgraph.graph import StateGraph, START, END
from src.state import AgentState
from src.nodes.detectives import repo_investigator, doc_analyst, vision_inspector
from src.nodes.judges import prosecutor_judge, defense_judge, techlead_judge
from src.nodes.justice import chief_justice


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
    
    # Layer 3: Judicial Layer (Three persona judges + Chief Justice)
    workflow.add_node("Prosecutor", prosecutor_judge)
    workflow.add_node("Defense", defense_judge)
    workflow.add_node("TechLead", techlead_judge)
    workflow.add_node("ChiefJustice", chief_justice)

    # --- Routing Logic ---

    def check_for_critical_failures(state: AgentState) -> str:
        """Route to END if critical errors (like clone failure) occur."""
        if state.get("errors"):
            print(f"CRITICAL FAILURE DETECTED: {state['errors']}")
            return "FAILURE"
        return "CONTINUE"

    # Fan-Out to Detectives
    workflow.add_edge(START, "RepoInvestigator")
    workflow.add_edge(START, "DocAnalyst")
    workflow.add_edge(START, "VisionInspector")

    # Conditional Fan-In to Evidence Aggregator
    # Note: Simplified interim handling. Real fan-in usually happens after all nodes return.
    workflow.add_edge("RepoInvestigator", "EvidenceAggregator")
    workflow.add_edge("DocAnalyst", "EvidenceAggregator")
    workflow.add_edge("VisionInspector", "EvidenceAggregator")

    # After aggregation, decide whether to proceed to Judicial layer
    workflow.add_conditional_edges(
        "EvidenceAggregator",
        check_for_critical_failures,
        {
            "CONTINUE": "Prosecutor",
            "FAILURE": END
        }
    )

    # Fan-out to three judges in parallel from EvidenceAggregator
    workflow.add_edge("EvidenceAggregator", "Prosecutor")
    workflow.add_edge("EvidenceAggregator", "Defense")
    workflow.add_edge("EvidenceAggregator", "TechLead")

    # Fan-in: each judge routes to ChiefJustice
    workflow.add_edge("Prosecutor", "ChiefJustice")
    workflow.add_edge("Defense", "ChiefJustice")
    workflow.add_edge("TechLead", "ChiefJustice")
    workflow.add_edge("ChiefJustice", END)

    return workflow.compile()


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    # Optional LangSmith tracing setup. When `LANGCHAIN_TRACING_V2` is set to
    # a truthy value and an API key is present, configure LangSmith to collect
    # a run representing this auditor execution. This creates a root RunTree
    # that will be ended after the graph invocation, which LangSmith will
    # persist (if client/API key/config is available).
    try:
        import langsmith.run_trees as ls_run_trees
        import langsmith as ls

        ls_enabled = os.getenv("LANGCHAIN_TRACING_V2")
        ls_project = os.getenv("LANGCHAIN_PROJECT") or os.getenv("LANGSMITH_PROJECT")
        if ls_enabled and ls_enabled.lower() in ("1", "true", "yes"):
            try:
                ls_run_trees.configure(enabled=True, project_name=ls_project)
                print(f"LangSmith tracing enabled (project={ls_project})")
            except Exception as e:
                print(f"LangSmith configure failed: {e}")
        else:
            # Explicitly disable tracing by default
            ls_run_trees.configure(enabled=False)
    except Exception:
        # If langsmith isn't installed or available, continue without tracing.
        pass

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

    # If LangSmith RunTree is configured, create a root run and attach inputs/metadata
    run_tree = None
    try:
        import langsmith.run_trees as ls_run_trees
        # Create a root RunTree capturing inputs
        run_tree = ls_run_trees.RunTree(name=f"Automaton Audit - {args.repo}")
        run_tree.add_inputs({"repo_url": args.repo, "pdf_path": args.pdf})
        run_tree.add_event({"name": "start", "message": "Starting audit run"})
    except Exception:
        run_tree = None

    final_output = app.invoke(initial_state)
    print("\n--- INTERIM EXECUTION COMPLETE ---")
    print("Collected Evidence Keys:", list(final_output.get("evidences", {}).keys()))

    # Finalize LangSmith run: attach outputs and end the run so it's uploaded.
    try:
        if run_tree is not None:
            # Attach some high-level outputs
            run_tree.add_outputs({"evidence_keys": list(final_output.get("evidences", {}).keys())})
            run_tree.add_event({"name": "end", "message": "Audit run completed"})
            run_tree.end()
            # Attempt to print a web link to the run (best-effort)
            client = run_tree.client
            try:
                base = client._host_url
                run_url = f"{base}/runs/{run_tree.id}"
                print(f"LangSmith run available at: {run_url}")
            except Exception:
                pass
    except Exception as e:
        print(f"LangSmith run finalization failed: {e}")
