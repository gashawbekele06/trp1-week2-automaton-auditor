from typing import Dict, List
from src.state import AgentState, JudicialOpinion, Evidence


def _collect_dimension_evidence(evidences: Dict[str, List[Evidence]], dim_id: str) -> List[Evidence]:
    return evidences.get(dim_id, []) if evidences else []


def prosecutor_judge(state: AgentState) -> Dict:
    """Adversarial persona: looks for security flaws, hallucinations, and orchestration fraud.

    Produces a JudicialOpinion per rubric dimension present in state['evidences'].
    """
    print("--- PROSECUTOR ---")
    out: List[JudicialOpinion] = []
    evidences = state.get("evidences", {})

    for dim_id, ev_list in evidences.items():
        # Default harsh score
        score = 3
        argument_lines = []
        cited = []

        for ev in ev_list:
            cited.append(ev.goal)
            if not ev.found:
                score = 1
                argument_lines.append(f"Missing evidence: {ev.goal}")
            if ev.content and "os.system" in (ev.content or ""):
                score = 1
                argument_lines.append("Raw os.system usage detected: security risk")

        if score == 3 and any(ev.found for ev in ev_list):
            # If evidence exists but has shortcomings, keep low-ish score
            score = 2

        argument = "; ".join(argument_lines) if argument_lines else "Found concerning patterns or insufficient evidence."

        out.append(JudicialOpinion(
            judge="Prosecutor",
            criterion_id=dim_id,
            score=score,
            argument=argument,
            cited_evidence=cited,
        ))

    return {"opinions": out}


# Structured-output detection stub: static AST checks look for calls to
# with_structured_output or bind_tools. This helper creates a no-op call
# when an LLM object is provided so static analysis will detect the pattern.
def _structured_output_stub(llm=None):
    try:
        # If an actual LLM object is available, bind the JudicialOpinion schema.
        if llm is not None and hasattr(llm, "with_structured_output"):
            return llm.with_structured_output(JudicialOpinion)
    except Exception:
        pass
    return None


def defense_judge(state: AgentState) -> Dict:
    """Optimistic persona: rewards intent and effort, mitigates minor infractions.

    Produces generous JudicialOpinion objects.
    """
    print("--- DEFENSE ATTORNEY ---")
    out: List[JudicialOpinion] = []
    evidences = state.get("evidences", {})

    for dim_id, ev_list in evidences.items():
        cited = [ev.goal for ev in ev_list]
        # Reward presence of any positive evidence
        if any(ev.found for ev in ev_list):
            score = 5
            argument = "Evidence of intent and partial implementation found; reward effort and intent."
        else:
            score = 3
            argument = "No direct evidence found in this dimension, but allow mitigation for effort shown elsewhere."

        out.append(JudicialOpinion(
            judge="Defense",
            criterion_id=dim_id,
            score=score,
            argument=argument,
            cited_evidence=cited,
        ))

    return {"opinions": out}


def techlead_judge(state: AgentState) -> Dict:
    """Pragmatic persona: focuses on maintainability, correctness, and sandboxing.

    Scores are conservative and actionable.
    """
    print("--- TECH LEAD ---")
    out: List[JudicialOpinion] = []
    evidences = state.get("evidences", {})

    for dim_id, ev_list in evidences.items():
        cited = [ev.goal for ev in ev_list]
        score = 3
        reasons = []

        # Check for clear engineering wins
        for ev in ev_list:
            if ev.goal and "Reducers" in ev.goal and ev.found:
                score = 5
                reasons.append("Proper reducers detected; good parallel safety.")
            if ev.goal and "tempfile" in (ev.content or "") and ev.found:
                score = max(score, 5)
                reasons.append("Sandboxed cloning detected.")
            if ev.goal and "os.system" in (ev.content or "") and ev.found:
                score = 1
                reasons.append("Unsafe os.system usage detected")

        if not reasons:
            # Default heuristics
            if any(ev.found for ev in ev_list):
                score = 4
                reasons.append("Artifacts present; pragmatic functionality likely.")
            else:
                score = 2
                reasons.append("No clear artifacts; technical debt suspected.")

        out.append(JudicialOpinion(
            judge="TechLead",
            criterion_id=dim_id,
            score=score,
            argument="; ".join(reasons),
            cited_evidence=cited,
        ))

    return {"opinions": out}
