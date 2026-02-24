from typing import Dict, List
from src.state import AgentState, Evidence


def evidence_aggregator(state: AgentState) -> AgentState:
    """
    Fan-in node: merges evidence from all detectives into state["evidences"].
    Uses operator.ior reducer semantics (latest per key wins).
    """
    # In real parallel execution, LangGraph would already have merged via reducer
    # This node can be used as a synchronization / validation point
    if not state.get("evidences"):
        state["evidences"] = {}

    # Optional: validate / deduplicate if needed
    for dim_id in state["rubric_dimensions"]:
        dim_id = dim_id["id"]
        if dim_id not in state["evidences"]:
            state["evidences"][dim_id] = []

    return state