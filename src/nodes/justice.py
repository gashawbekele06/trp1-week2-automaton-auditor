from typing import Dict, List
import os
from statistics import median
from src.state import AgentState, JudicialOpinion, CriterionResult, AuditReport, Evidence
from src.tools.doc_tools import ingest_pdf


def _group_opinions_by_criterion(opinions: List[JudicialOpinion]) -> Dict[str, List[JudicialOpinion]]:
    grouped: Dict[str, List[JudicialOpinion]] = {}
    for op in opinions:
        grouped.setdefault(op.criterion_id, []).append(op)
    return grouped


def _serialize_criterion_result(criterion_id: str, criterion_name: str, final_score: int, opinions: List[JudicialOpinion], dissent: str, remediation: str) -> CriterionResult:
    return CriterionResult(
        dimension_id=criterion_id,
        dimension_name=criterion_name,
        final_score=final_score,
        judge_opinions=opinions,
        dissent_summary=dissent if dissent else None,
        remediation=remediation,
    )


def chief_justice(state: AgentState) -> Dict:
    """Deterministic synthesis node implementing the Chief Justice rules.

    Rules enforced (from rubric):
    - security_override: if Prosecutor finds confirmed security vulnerability, cap score at 3
    - fact_supremacy: detective facts override judge claims
    - functionality_weight: TechLead carries highest weight for architecture criterion
    - dissent_requirement: include dissent summary if variance > 2
    - variance_re_evaluation: if variance > 2, re-evaluate cited evidence
    """
    print("--- CHIEF JUSTICE ---")
    opinions: List[JudicialOpinion] = state.get("opinions", []) or []
    evidences: Dict[str, List[Evidence]] = state.get("evidences", {}) or {}
    rubric_dimensions = state.get("rubric_dimensions", []) or []

    # Map dimension id to readable name
    dim_name_map = {d.get("id"): d.get("name") for d in rubric_dimensions}

    grouped = _group_opinions_by_criterion(opinions)
    criteria_results: List[CriterionResult] = []

    for dim_id, ops in grouped.items():
        scores = [o.score for o in ops]
        max_score = max(scores)
        min_score = min(scores)
        var = max_score - min_score

        # Default final score is median
        final = int(median(scores))

        # Security override: if any prosecutor argument mentions os.system or 'security' or missing evidence
        security_flag = any((o.judge == "Prosecutor" and ("os.system" in o.argument or "security" in o.argument.lower())) for o in ops)
        if security_flag:
            final = min(final, 3)

        # Functionality weight: if techlead exists for graph_orchestration, use its score
        if dim_id == "graph_orchestration":
            tech_ops = [o for o in ops if o.judge == "TechLead"]
            if tech_ops:
                final = tech_ops[0].score

        # Fact supremacy: if defense claims 'Deep Metacognition' but detectives have no evidence for theoretical_depth
        if dim_id == "theoretical_depth":
            defense_claims = [o for o in ops if o.judge == "Defense" and "Deep Metacognition" in o.argument]
            if defense_claims and not evidences.get("theoretical_depth"):
                # Overrule defense by lowering its contribution
                final = min(final, 3)

        # Variance re-evaluation
        dissent = ""
        if var > 2:
            # Re-evaluate cited evidence: if any cited evidence is missing, bias towards Prosecutor
            reeval_fail = False
            for o in ops:
                for cited in o.cited_evidence:
                    # find evidence by goal name
                    found_flag = False
                    for ev in evidences.get(dim_id, []):
                        if ev.goal == cited:
                            found_flag = ev.found
                            break
                    if not found_flag:
                        reeval_fail = True
            if reeval_fail:
                # If re-eval fails, choose the min score
                final = min_score
                dissent = "High variance and re-evaluation found missing cited evidence; prosecutor position favored."
                # Signal graph-level detective retry request so the orchestrator can re-run targeted probes
                # Respect a retry bound to avoid infinite loops
                retry_counts = state.get("retry_counts", {}) or {}
                detectives_retries = retry_counts.get("detectives", 0)
                max_retries = int(os.getenv("MAX_DETECTIVE_RETRIES", "2"))
                if detectives_retries < max_retries:
                    state["needs_detective_retry"] = True
                    print(f"ChiefJustice requested detective retry (current={detectives_retries}, max={max_retries})")
                else:
                    print(f"ChiefJustice: detective retry limit reached ({detectives_retries})")
            else:
                dissent = "High variance across judges; median score used after re-evaluation."
                # If variance is high but cited evidence exists, prefer a judge-level retry to reduce nondeterminism
                retry_counts = state.get("retry_counts", {}) or {}
                judge_retries = retry_counts.get("judges", 0)
                max_j_retries = int(os.getenv("MAX_JUDGE_RETRIES", "1"))
                if judge_retries < max_j_retries:
                    state["needs_judge_retry"] = True
                    print(f"ChiefJustice requested judge retry (current={judge_retries}, max={max_j_retries})")

        # Construct remediation: simple actionable hint based on dimension
        remediation = "See detective evidence and implement missing artifacts."
        if dim_id == "safe_tool_engineering":
            remediation = "Ensure git clone uses tempfile.TemporaryDirectory and subprocess.run with error handling; remove raw os.system calls."
        if dim_id == "state_management_rigor":
            remediation = "Define AgentState with Pydantic or TypedDict and use Annotated reducers (operator.add, operator.ior) to avoid parallel overwrites."
        if dim_id == "graph_orchestration":
            remediation = "Implement parallel fan-out for Detectives and Judges with a fan-in EvidenceAggregator node; add conditional edges for failure handling."

        criteria_results.append(_serialize_criterion_result(dim_id, dim_name_map.get(dim_id, dim_id), final, ops, dissent, remediation))

    # Compute overall score as simple average
    overall = 0.0
    if criteria_results:
        overall = sum(c.final_score for c in criteria_results) / len(criteria_results)

    report = AuditReport(
        repo_url=state.get("repo_url", ""),
        executive_summary="Auto-generated audit report by Chief Justice.",
        overall_score=overall,
        criteria=criteria_results,
        remediation_plan="See per-criterion remediation above."
    )

    # Persist a Markdown copy under audit/report_onself_generated for inspection
    try:
        out_dir = os.path.join(os.getcwd(), "audit", "report_onself_generated")
        os.makedirs(out_dir, exist_ok=True)
        md_path = os.path.join(out_dir, "audit_report.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(f"# Audit Report\n\n")
            f.write(f"Repo: {report.repo_url}\n\n")
            f.write(f"Overall Score: {report.overall_score}\n\n")
            f.write("## Criteria\n\n")
            for c in report.criteria:
                f.write(f"### {c.dimension_name} ({c.dimension_id})\n")
                f.write(f"Final Score: {c.final_score}  \n")
                if c.dissent_summary:
                    f.write(f"Dissent: {c.dissent_summary}\n")
                f.write("Judge Opinions:\n")
                for j in c.judge_opinions:
                    f.write(f"- {j.judge}: {j.score} — {j.argument}\n")
                f.write(f"Remediation:\n{c.remediation}\n\n")
        print(f"Chief Justice: persisted markdown report to {md_path}")
    except Exception as e:
        print(f"Failed to write audit markdown: {e}")

    # Additionally prepare a richer 'final_report.md' suitable for conversion to PDF.
    try:
        final_md = os.path.join(out_dir, "final_report.md")
        pdf_path = state.get("pdf_path")
        chunks = []
        if pdf_path and os.path.exists(pdf_path):
            chunks = ingest_pdf(pdf_path)
        else:
            fallback = os.path.join(os.getcwd(), "reports", "final_report.pdf")
            if os.path.exists(fallback):
                chunks = ingest_pdf(fallback)

        # Pull architecture and reflection snippets from PDF chunks
        keywords = ["Dialectical Synthesis", "Fan-In", "Fan-Out", "Metacognition", "State Synchronization", "MinMax"]
        arch_sections: List[str] = []
        reflections: List[str] = []
        for chunk in chunks:
            text = chunk.get("text", "")
            if not text:
                continue
            for kw in keywords:
                if kw.lower() in text.lower():
                    arch_sections.append(f"**Context for {kw}:**\n\n{text.strip()}\n\n")
            if "peer" in text.lower() or "feedback" in text.lower() or "minmax" in text.lower():
                reflections.append(text.strip())

        with open(final_md, "w", encoding="utf-8") as f:
            f.write("# Final Audit Report\n\n")
            f.write("## Executive Summary\n\n")
            f.write(report.executive_summary + "\n\n")

            f.write("## Architecture Deep Dive\n\n")
            if arch_sections:
                for s in arch_sections:
                    f.write(s + "\n")
            else:
                f.write("(No architecture deep-dive found in provided PDF; please add sections on Dialectical Synthesis, Fan-In/Fan-Out, and Metacognition.)\n\n")

            f.write("## Architectural Diagrams\n\n")
            diagram_paths = []
            candidates = ["automaton_flow.png", "automaton_flow.jpg", "architecture.png", "reports/architecture.png"]
            for p in candidates:
                p_abs = os.path.join(os.getcwd(), p)
                if os.path.exists(p_abs):
                    diagram_paths.append(p)
            if diagram_paths:
                for dp in diagram_paths:
                    f.write(f"![Architecture Diagram]({dp})\n\n")
            else:
                f.write("(No architectural diagrams found. Add a StateGraph visualization showing parallel flow.)\n\n")

            f.write("## Criterion-by-Criterion Breakdown\n\n")
            for c in report.criteria:
                f.write(f"### {c.dimension_name} — Final Score: {c.final_score}\n\n")
                if c.dissent_summary:
                    f.write(f"**Dissent:** {c.dissent_summary}\n\n")
                f.write("**Judge Opinions:**\n\n")
                for j in c.judge_opinions:
                    f.write(f"- **{j.judge}** ({j.score}): {j.argument}\n")
                    if j.cited_evidence:
                        f.write(f"  - Cited Evidence: {', '.join(j.cited_evidence)}\n")
                f.write(f"\n**Remediation:** {c.remediation}\n\n")

            f.write("## Reflection on the MinMax Feedback Loop\n\n")
            if reflections:
                for r in reflections:
                    f.write(r + "\n\n")
            else:
                f.write("(Add reflections: what peer agents caught, how you updated your agent, and remaining gaps.)\n\n")

            f.write("## Remediation Plan\n\n")
            f.write(report.remediation_plan + "\n\n")

        print(f"Chief Justice: persisted final markdown report to {final_md}")
    except Exception as e:
        print(f"Failed to write final markdown: {e}")

    return {"final_report": report}
