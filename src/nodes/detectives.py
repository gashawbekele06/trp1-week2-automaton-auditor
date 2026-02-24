from src.state import AgentState, Evidence
from src.tools.repo_tools import analyze_graph_structure, extract_git_history
from src.tools.doc_tools import ingest_pdf


def detectives_node(state: AgentState) -> AgentState:
    idx = state["current_dimension_index"]
    dim = state["rubric_dimensions"][idx]
    dim_id = dim["id"]

    evidence_list = []

    # RepoInvestigator logic
    if dim["target_artifact"] == "github_repo":
        graph_analysis = analyze_graph_structure.invoke({"repo_path": state["repo_path"]})
        git_hist = extract_git_history.invoke({"repo_path": state["repo_path"]})
        evidence_list.append(Evidence(
            goal="Graph structure & git history",
            found=graph_analysis["stategraph_found"],
            location=state["repo_path"],
            rationale=str(graph_analysis) + str(git_hist),
            confidence=0.9
        ))

    # DocAnalyst logic
    if dim["target_artifact"] == "pdf_report":
        pdf_text = ingest_pdf.invoke({"pdf_path": state["pdf_path"]})
        evidence_list.append(Evidence(
            goal="PDF content scan",
            found=True,
            content=pdf_text[:500],  # snippet
            location=state["pdf_path"],
            rationale="Text extracted",
            confidence=0.95
        ))

    # Add to state
    if dim_id not in state["evidences"]:
        state["evidences"][dim_id] = []
    state["evidences"][dim_id].extend(evidence_list)

    state["current_dimension_index"] += 1
    return state