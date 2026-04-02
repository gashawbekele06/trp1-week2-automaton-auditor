import os
from typing import Dict, List, Optional
from src.state import AgentState, JudicialOpinion, Evidence

# --- Distinct system prompts — the "Constitution" of each judge persona ---

PROSECUTOR_SYSTEM_PROMPT = """\
You are The Prosecutor, a forensic software auditor with a deeply skeptical and adversarial mindset.
Core Philosophy: "Trust No One. Assume Vibe Coding."
Objective: Scrutinize the provided evidence for gaps, security flaws, and laziness. Do NOT give the benefit of the doubt.

Strict Scoring Rules:
- Required parallel orchestration not present → Score MUST be 1. Charge: "Orchestration Fraud."
- Judge nodes lack Pydantic structured output binding → Score MUST be ≤ 2. Charge: "Hallucination Liability."
- os.system() detected without sandboxing → Score MUST be 1. Charge: "Security Negligence."
- Required files or artifacts completely missing → Score MUST be 1.
- Evidence is partial or uncertain → Score 2.
- Implementation exists but has minor violations → Score 3.
- Never give 4 or 5.

Respond ONLY with a JSON object for the JudicialOpinion schema: judge="Prosecutor", criterion_id, score (int 1-5), argument (str), cited_evidence (list of str).
"""

DEFENSE_SYSTEM_PROMPT = """\
You are The Defense Attorney, a compassionate software advocate who rewards effort and intent.
Core Philosophy: "Reward Effort and Intent. Look for the Spirit of the Law."
Objective: Highlight creative workarounds, deep thought, and genuine effort, even if the implementation is imperfect.

Scoring Rules:
- Any positive implementation present, even partial → Score 4 or 5.
- Git history shows iterative commits and progression → Argue for a higher score (Engineering Process).
- Architecture sound conceptually even if syntax has minor errors → "Engineer achieved deep comprehension but tripped on framework syntax" → Score 3+.
- Chief Justice synthesis LLM-based rather than hardcoded BUT judge personas are distinct and genuinely disagreeing → Partial credit Score 3-4.
- Multiple positive signals aligned → Score 5.
- Any demonstrated effort → Minimum Score 3.

Respond ONLY with a JSON object for the JudicialOpinion schema: judge="Defense", criterion_id, score (int 1-5), argument (str), cited_evidence (list of str).
"""

TECHLEAD_SYSTEM_PROMPT = """\
You are The Tech Lead, a pragmatic senior engineer evaluating production readiness.
Core Philosophy: "Does it actually work? Is it maintainable?"
Objective: Evaluate architectural soundness, code cleanliness, and practical viability. You are the tie-breaker.

Scoring Rules:
- Ignore "vibe" and "struggle." Focus on concrete artifacts only.
- Score 5: Architecture modular, reducers prevent overwrites, sandboxing correct, structured outputs enforced.
- Score 4: Mostly correct with minor issues (e.g., LLM stub instead of real call, minor missing field).
- Score 3 (Technical Debt): Standard Python dicts instead of Pydantic, or functional but brittle.
- Score 1-2: Confirmed security vulnerabilities (os.system unsanitized), no error handling, broken architecture.
- For "graph_orchestration" specifically: if architecture is modular and workable, your score carries the highest weight.
- Include specific technical remediation advice in your argument.

Respond ONLY with a JSON object for the JudicialOpinion schema: judge="TechLead", criterion_id, score (int 1-5), argument (str), cited_evidence (list of str).
"""

# --- LLM Setup: each persona gets its own .with_structured_output(JudicialOpinion) binding ---

STRUCTURED_BIND_AVAILABLE = False
_prosecutor_llm = None
_defense_llm = None
_techlead_llm = None

try:
    if os.getenv("OPENAI_API_KEY"):
        from langchain_openai import ChatOpenAI

        _base_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        # Each judge uses .with_structured_output() bound to the JudicialOpinion Pydantic schema.
        # This enforces structured JSON output and is detectable by AST-based forensic tools.
        _prosecutor_llm = _base_llm.with_structured_output(JudicialOpinion)
        _defense_llm = _base_llm.with_structured_output(JudicialOpinion)
        _techlead_llm = _base_llm.with_structured_output(JudicialOpinion)
        STRUCTURED_BIND_AVAILABLE = True
except Exception:
    STRUCTURED_BIND_AVAILABLE = False

# --- Helpers ---


def _find_dimension_meta(rubric_dimensions: List[Dict], dim_id: str) -> Optional[Dict]:
    if not rubric_dimensions:
        return None
    for d in rubric_dimensions:
        if d.get("id") == dim_id:
            return d
    return None


def _format_evidence_for_prompt(dim_id: str, ev_list: List[Evidence], meta: Optional[Dict]) -> str:
    lines = [f"Criterion ID: {dim_id}"]
    if meta:
        lines.append(f"Criterion Name: {meta.get('name', dim_id)}")
        lines.append(f"Success Pattern: {meta.get('success_pattern', '')}")
        lines.append(f"Failure Pattern: {meta.get('failure_pattern', '')}")
        lines.append(f"Forensic Instruction: {meta.get('forensic_instruction', '')[:400]}")
    lines.append("\nEvidence collected by Detectives:")
    for ev in ev_list:
        found_str = "FOUND" if ev.found else "NOT FOUND"
        lines.append(f"  [{found_str}] Goal: {ev.goal}")
        lines.append(f"    Location: {ev.location}")
        lines.append(f"    Rationale: {ev.rationale}")
        if ev.content:
            lines.append(f"    Content: {ev.content[:300]}")
        lines.append(f"    Confidence: {ev.confidence}")
    return "\n".join(lines)


def _validate_and_append(opinion_data: Dict, out_list: List[JudicialOpinion], state: AgentState, judge_name: str):
    """Validate a JudicialOpinion dict against the Pydantic schema.

    On validation failure, mark the state for judge retry and record an error.
    """
    try:
        opinion = JudicialOpinion(**opinion_data)
        out_list.append(opinion)
    except Exception as e:
        errs = list(state.get("errors", []) or [])
        msg = f"Judge {judge_name} produced invalid output for criterion {opinion_data.get('criterion_id')}: {e}"
        errs.append(msg)
        state["errors"] = errs
        counts = dict(state.get("retry_counts", {}) or {})
        counts["judges"] = counts.get("judges", 0) + 1
        state["retry_counts"] = counts
        state["needs_judge_retry"] = True
        print(msg)


def _call_llm_judge(
    llm,
    system_prompt: str,
    judge_name: str,
    dim_id: str,
    ev_list: List[Evidence],
    meta: Optional[Dict],
) -> Optional[JudicialOpinion]:
    """Invoke an LLM judge with .with_structured_output(JudicialOpinion). Returns None on failure."""
    try:
        from langchain_core.messages import SystemMessage, HumanMessage

        evidence_text = _format_evidence_for_prompt(dim_id, ev_list, meta)
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Evaluate the following evidence and produce your JudicialOpinion:\n\n{evidence_text}"),
        ]
        opinion: JudicialOpinion = llm.invoke(messages)
        # Normalise fields that the LLM might fill incorrectly
        return JudicialOpinion(
            judge=judge_name,  # type: ignore[arg-type]
            criterion_id=dim_id,
            score=max(1, min(5, opinion.score)),
            argument=opinion.argument,
            cited_evidence=opinion.cited_evidence or [ev.goal for ev in ev_list],
        )
    except Exception as e:
        print(f"LLM judge {judge_name} failed for {dim_id}: {e}")
        return None


# --- Heuristic fallbacks (used when OPENAI_API_KEY is absent) ---


def _heuristic_prosecutor(dim_id: str, ev_list: List[Evidence], rubric: List[Dict], state: AgentState) -> JudicialOpinion:
    score = 3
    argument_lines = []
    cited = [ev.goal for ev in ev_list]
    meta = _find_dimension_meta(rubric, dim_id)
    if meta:
        argument_lines.append(f"(Rubric: {meta.get('name')} — {meta.get('forensic_instruction', '')[:200]}...)")
    for ev in ev_list:
        if not ev.found:
            score = 1
            argument_lines.append(f"Missing evidence: {ev.goal}")
        if ev.content and "os.system" in (ev.content or ""):
            score = 1
            argument_lines.append("Raw os.system usage detected: security risk")
    if score == 3 and any(ev.found for ev in ev_list):
        score = 2
    argument = "; ".join(argument_lines) if argument_lines else "Found concerning patterns or insufficient evidence."
    return JudicialOpinion(judge="Prosecutor", criterion_id=dim_id, score=score, argument=argument, cited_evidence=cited)


def _heuristic_defense(dim_id: str, ev_list: List[Evidence], rubric: List[Dict]) -> JudicialOpinion:
    cited = [ev.goal for ev in ev_list]
    meta = _find_dimension_meta(rubric, dim_id)
    if any(ev.found for ev in ev_list):
        score = 5
        argument = "Evidence of intent and partial implementation found; reward effort and intent."
        if meta:
            argument += f" ({meta.get('name')}: {meta.get('success_pattern', '')[:120]}...)"
    else:
        score = 3
        argument = "No direct evidence found in this dimension, but allow mitigation for effort shown elsewhere."
        if meta:
            argument += f" Consider forensic instruction: {meta.get('forensic_instruction', '')[:120]}..."
    return JudicialOpinion(judge="Defense", criterion_id=dim_id, score=score, argument=argument, cited_evidence=cited)


def _heuristic_techlead(dim_id: str, ev_list: List[Evidence], rubric: List[Dict]) -> JudicialOpinion:
    cited = [ev.goal for ev in ev_list]
    score = 3
    reasons = []
    meta = _find_dimension_meta(rubric, dim_id)
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
        if any(ev.found for ev in ev_list):
            score = 4
            reasons.append("Artifacts present; pragmatic functionality likely.")
        else:
            score = 2
            reasons.append("No clear artifacts; technical debt suspected.")
    if meta:
        reasons.insert(0, f"Rubric: {meta.get('name')}. Guidance: {meta.get('forensic_instruction', '')[:120]}...")
    return JudicialOpinion(judge="TechLead", criterion_id=dim_id, score=score, argument="; ".join(reasons), cited_evidence=cited)


# --- Judge Nodes ---


def prosecutor_judge(state: AgentState) -> Dict:
    """Adversarial persona: looks for security flaws, hallucinations, and orchestration fraud.

    Uses LLM with .with_structured_output(JudicialOpinion) bound to the Prosecutor system prompt
    when OPENAI_API_KEY is set. Falls back to deterministic heuristics otherwise.
    """
    print("--- PROSECUTOR ---")
    out: List[JudicialOpinion] = []
    evidences = state.get("evidences", {})
    rubric = state.get("rubric_dimensions", [])

    for dim_id, ev_list in evidences.items():
        opinion: Optional[JudicialOpinion] = None
        meta = _find_dimension_meta(rubric, dim_id)

        if STRUCTURED_BIND_AVAILABLE and _prosecutor_llm is not None:
            opinion = _call_llm_judge(_prosecutor_llm, PROSECUTOR_SYSTEM_PROMPT, "Prosecutor", dim_id, ev_list, meta)

        if opinion is None:
            opinion = _heuristic_prosecutor(dim_id, ev_list, rubric, state)

        out.append(opinion)

    return {"opinions": out}


def defense_judge(state: AgentState) -> Dict:
    """Optimistic persona: rewards intent and effort, mitigates minor infractions.

    Uses LLM with .with_structured_output(JudicialOpinion) bound to the Defense system prompt
    when OPENAI_API_KEY is set. Falls back to deterministic heuristics otherwise.
    """
    print("--- DEFENSE ATTORNEY ---")
    out: List[JudicialOpinion] = []
    evidences = state.get("evidences", {})
    rubric = state.get("rubric_dimensions", [])

    for dim_id, ev_list in evidences.items():
        opinion: Optional[JudicialOpinion] = None
        meta = _find_dimension_meta(rubric, dim_id)

        if STRUCTURED_BIND_AVAILABLE and _defense_llm is not None:
            opinion = _call_llm_judge(_defense_llm, DEFENSE_SYSTEM_PROMPT, "Defense", dim_id, ev_list, meta)

        if opinion is None:
            opinion = _heuristic_defense(dim_id, ev_list, rubric)

        out.append(opinion)

    return {"opinions": out}


def techlead_judge(state: AgentState) -> Dict:
    """Pragmatic persona: focuses on maintainability, correctness, and sandboxing.

    Uses LLM with .with_structured_output(JudicialOpinion) bound to the TechLead system prompt
    when OPENAI_API_KEY is set. Falls back to deterministic heuristics otherwise.
    """
    print("--- TECH LEAD ---")
    out: List[JudicialOpinion] = []
    evidences = state.get("evidences", {})
    rubric = state.get("rubric_dimensions", [])

    for dim_id, ev_list in evidences.items():
        opinion: Optional[JudicialOpinion] = None
        meta = _find_dimension_meta(rubric, dim_id)

        if STRUCTURED_BIND_AVAILABLE and _techlead_llm is not None:
            opinion = _call_llm_judge(_techlead_llm, TECHLEAD_SYSTEM_PROMPT, "TechLead", dim_id, ev_list, meta)

        if opinion is None:
            opinion = _heuristic_techlead(dim_id, ev_list, rubric)

        out.append(opinion)

    return {"opinions": out}
