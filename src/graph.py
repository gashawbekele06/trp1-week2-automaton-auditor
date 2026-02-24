from langgraph.graph import StateGraph, START, END, Send
from src.state import AgentState
from src.nodes.setup import setup_node
from src.nodes.detectives import detective_node  # assume exists from Phase 2
from src.nodes.aggregator import evidence_aggregator
from src.nodes.judges import judge_node
# from src.nodes.justice import chief_justice_node  # Phase 4

graph = StateGraph(AgentState)

# Nodes
graph.add_node("setup", setup_node)
graph.add_node("detective", detective_node)           # per-dimension detective (sequential loop for simplicity)
graph.add_node("aggregator", evidence_aggregator)

# Judge nodes (will be called via Send)
graph.add_node("prosecutor", lambda s: judge_node(s, "Prosecutor"))
graph.add_node("defense",     lambda s: judge_node(s, "Defense"))
graph.add_node("techlead",    lambda s: judge_node(s, "TechLead"))

# Placeholder for Chief Justice (Phase 4)
graph.add_node("justice", lambda s: s)  # replace later

# Edges
graph.add_edge(START, "setup")
graph.add_edge("setup", "detective")

# Loop over dimensions for detectives
def route_dimensions(state: AgentState):
    if state["current_dimension_index"] < len(state["rubric_dimensions"]):
        return "detective"
    return "aggregator"

graph.add_conditional_edges("detective", route_dimensions, {
    "detective": "detective",
    "aggregator": "aggregator"
})

# After aggregator → fan-out judges for current dimension
def fan_out_judges(state: AgentState) -> List[Send]:
    if state["current_dimension_index"] >= len(state["rubric_dimensions"]):
        return []  # done

    dim_id = state["rubric_dimensions"][state["current_dimension_index"] - 1]["id"]
    return [
        Send("prosecutor", state),
        Send("defense", state),
        Send("techlead", state),
    ]

graph.add_conditional_edges("aggregator", fan_out_judges, {
    "prosecutor": "prosecutor",
    "defense": "defense",
    "techlead": "techlead",
})

# After judges → back to next dimension or justice
graph.add_edge(["prosecutor", "defense", "techlead"], "aggregator")  # loop until done

# When all dimensions processed → justice
def route_to_justice(state: AgentState):
    if state["current_dimension_index"] >= len(state["rubric_dimensions"]):
        return "justice"
    return "aggregator"

graph.add_conditional_edges("aggregator", route_to_justice, {
    "justice": "justice",
    "aggregator": "aggregator"
})

graph.add_edge("justice", END)

app = graph.compile()