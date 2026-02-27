import json
import argparse
import sys
import os

# Ensure the project root is on the path so `src` is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langgraph.graph import StateGraph, START, END
import hashlib
from src.state import AgentState
from src.nodes.detectives import repo_investigator, doc_analyst, vision_inspector
from src.tools.repo_tools import clone_or_use_local
from src.nodes.judges import prosecutor_judge, defense_judge, techlead_judge
from src.nodes.justice import chief_justice


def evidence_aggregator(state: AgentState):
    """Synchronization node (Fan-In) collecting all evidence."""
    print("\n--- EVIDENCE AGGREGATED ---")
    evidences = state.get("evidences", {})
    # Log summary
    for dim, ev_list in evidences.items():
        print(f"Dimension: {dim} - Found {len(ev_list)} evidence items.")
        for ev in ev_list:
            # ev may be a Pydantic model or a plain dict
            try:
                found = ev.found
                goal = ev.goal
                rationale = ev.rationale
            except Exception:
                found = ev.get("found") if isinstance(ev, dict) else None
                goal = ev.get("goal") if isinstance(ev, dict) else str(ev)
                rationale = ev.get("rationale") if isinstance(ev, dict) else ""
            print(f"  - [{found}] {goal}: {rationale}")

    # Create a canonical JSON snapshot and compute SHA256 for reproducibility
    try:
        canonical = {}
        for dim in sorted(evidences.keys()):
            items = evidences[dim]
            serial = []
            for ev in items:
                if hasattr(ev, "dict"):
                    evd = ev.dict()
                else:
                    evd = dict(ev)
                # Keep deterministic ordering of keys
                serial.append({k: evd.get(k) for k in sorted(evd.keys())})
            canonical[dim] = serial

        snapshot_json = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
        snapshot_hash = hashlib.sha256(snapshot_json.encode("utf-8")).hexdigest()

        # Persist snapshot under audit/snapshots/<hash>.json
        out_dir = os.path.join(os.getcwd(), "audit", "snapshots")
        os.makedirs(out_dir, exist_ok=True)
        snapshot_path = os.path.join(out_dir, f"{snapshot_hash}.json")
        if not os.path.exists(snapshot_path):
            with open(snapshot_path, "w", encoding="utf-8") as fh:
                fh.write(snapshot_json)
        print(f"Wrote evidence snapshot: {snapshot_path}")
    except Exception as e:
        print(f"Failed to write snapshot: {e}")

    return {"evidences": evidences, "snapshot_hash": snapshot_hash}


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

    def aggregator_decision(state: AgentState) -> str:
        """Decide after EvidenceAggregator: FAILURE | RETRY_DETECTIVES | CONTINUE"""
        if state.get("errors"):
            print(f"CRITICAL FAILURE DETECTED: {state['errors']}")
            return "FAILURE"
        if state.get("needs_detective_retry"):
            return "RETRY_DETECTIVES"
        return "CONTINUE"

    def chief_decision(state: AgentState) -> str:
        """Decide after ChiefJustice: RETRY_JUDGES | END"""
        if state.get("needs_judge_retry"):
            return "RETRY_JUDGES"
        return "END"

    def retry_detectives(state: AgentState):
        """Controller node to trigger targeted detective retries.

        This node should be idempotent: it increments a counter and clears the
        `needs_detective_retry` flag so retries are bounded by external config.
        """
        counts = state.get("retry_counts", {}) or {}
        counts["detectives"] = counts.get("detectives", 0) + 1
        state["retry_counts"] = counts
        # clear the request so we don't loop indefinitely; real logic may scope retries
        state.pop("needs_detective_retry", None)
        print(f"RetryDetectives invoked (count={counts['detectives']})")
        return {}

    def retry_judges(state: AgentState):
        """Controller node to trigger judge retries."""
        counts = state.get("retry_counts", {}) or {}
        counts["judges"] = counts.get("judges", 0) + 1
        state["retry_counts"] = counts
        state.pop("needs_judge_retry", None)
        print(f"RetryJudges invoked (count={counts['judges']})")
        return {}

    # Fan-Out to Detectives
    workflow.add_edge(START, "RepoInvestigator")
    workflow.add_edge(START, "DocAnalyst")
    workflow.add_edge(START, "VisionInspector")

    # Conditional Fan-In to Evidence Aggregator
    # Note: Simplified interim handling. Real fan-in usually happens after all nodes return.
    workflow.add_edge("RepoInvestigator", "EvidenceAggregator")
    workflow.add_edge("DocAnalyst", "EvidenceAggregator")
    workflow.add_edge("VisionInspector", "EvidenceAggregator")

    # Add retry controller nodes
    workflow.add_node("RetryDetectives", retry_detectives)
    workflow.add_node("RetryJudges", retry_judges)

    # After aggregation, decide whether to proceed to Judicial layer, retry, or fail
    workflow.add_conditional_edges(
        "EvidenceAggregator",
        aggregator_decision,
        {
            "CONTINUE": "Prosecutor",
            "FAILURE": END,
            "RETRY_DETECTIVES": "RetryDetectives",
        }
    )

    # RetryDetectives fans back out to the detective nodes
    workflow.add_edge("RetryDetectives", "RepoInvestigator")
    workflow.add_edge("RetryDetectives", "DocAnalyst")
    workflow.add_edge("RetryDetectives", "VisionInspector")

    # Fan-out to three judges in parallel from EvidenceAggregator
    workflow.add_edge("EvidenceAggregator", "Prosecutor")
    workflow.add_edge("EvidenceAggregator", "Defense")
    workflow.add_edge("EvidenceAggregator", "TechLead")

    # Fan-in: each judge routes to ChiefJustice
    workflow.add_edge("Prosecutor", "ChiefJustice")
    workflow.add_edge("Defense", "ChiefJustice")
    workflow.add_edge("TechLead", "ChiefJustice")

    # After ChiefJustice decide whether to end or retry judges
    workflow.add_conditional_edges(
        "ChiefJustice",
        chief_decision,
        {
            "END": END,
            "RETRY_JUDGES": "RetryJudges",
        }
    )

    # RetryJudges fans back out to the judge nodes
    workflow.add_edge("RetryJudges", "Prosecutor")
    workflow.add_edge("RetryJudges", "Defense")
    workflow.add_edge("RetryJudges", "TechLead")

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
    parser.add_argument("--mode", type=str, choices=["self", "peer"], required=False,
                        help="(optional) force evaluation mode: 'self' or 'peer'. If omitted the runner will attempt to infer mode from cloning behavior.")
    args = parser.parse_args()

    with open("rubric.json", "r", encoding="utf-8") as f:
         rubric_data = json.load(f)

    # Try to clone the repo; if cloning fails, clone_or_use_local will fall back
    # to the local workspace. Keep a handle to any temporary clone so it isn't
    # garbage-collected while the run is active. The optional --mode flag can
    # also force 'self' or 'peer' evaluation and will override auto-detection.
    temp_clone_handle = None
    try:
        repo_path, is_temporary, temp_clone_handle = clone_or_use_local(args.repo)
    except Exception:
        # If clone_or_use_local raises, fall back to the provided URL string
        repo_path = args.repo
        is_temporary = False

    # If user supplied explicit mode, override detection
    if getattr(args, "mode", None) is not None:
        forced_self = True if args.mode == "self" else False
        is_self = forced_self
        print(f"Evaluation mode forced by CLI: {'self' if is_self else 'peer'}")
    else:
        is_self = not bool(is_temporary)

    initial_state = {
        "repo_url": args.repo,
        "repo_path": repo_path,
        "is_self_audit": is_self,
        "pdf_path": args.pdf,
        "rubric_dimensions": rubric_data["dimensions"],
        "synthesis_rules": rubric_data.get("synthesis_rules", {}),
        "evidences": {},
        "opinions": []
    }
    # Startup logging to help verify mode detection and routing
    print(f"Starting Interim Automaton Auditor for {args.repo}...")
    print(f"  -> Resolved repo_path: {repo_path}")
    print(f"  -> Temporary clone in use: {bool(is_temporary)}")
    print(f"  -> Effective mode (is_self_audit): {is_self}")
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
