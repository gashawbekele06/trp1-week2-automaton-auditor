from langgraph.graph import StateGraph, START, END, Send
from src.state import AgentState
from src.nodes.setup import setup_node
from src.nodes.detectives import detective_node
from src.nodes.aggregator import evidence_aggregator
from src.nodes.judges import judge_node
from src.nodes.justice import chief_justice_node


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