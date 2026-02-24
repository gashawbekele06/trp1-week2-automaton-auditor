import json
import os
from typing import Dict
from src.state import AgentState, CriterionResult, AuditReport, JudicialOpinion


def chief_justice_node(state: AgentState) -> AgentState:
    """
    Deterministic Python synthesis engine: resolves dialectical conflicts per criterion.
    Uses hardcoded rules from rubric["synthesis_rules"].
    No LLM – pure logic.
    """
    rubric = state["rubric"]
    rules = rubric["synthesis_rules"]
    criteria = []
    total_score = 0
    remediations = []

    for dim in rubric["rubric_dimensions"]:
        dim_id = dim["id"]
        opinions: List[JudicialOpinion] = [op for op in state["opinions"] if op["criterion_id"] == dim_id]
        if len(opinions) != 3:
            continue  # skip incomplete

        # Extract scores by judge
        pros_score = next((op["score"] for op in opinions if op["judge"] == "Prosecutor"), 0)
        def_score = next((op["score"] for op in opinions if op["judge"] == "Defense"), 0)
        tech_score = next((op["score"] for op in opinions if op["judge"] == "TechLead"), 0)
        scores = [pros_score, def_score, tech_score]

        # Calculate variance
        variance = max(scores) - min(scores)
        dissent = None
        if variance > 2:
            dissent = f"Variance {variance}: Prosecutor argued '{opinions[0]['argument'][:100]}...'; Defense countered '{opinions[1]['argument'][:100]}...'; TechLead resolved '{opinions[2]['argument'][:100]}...'."

            # Trigger re-evaluation: weight TechLead higher + check evidence
            # Simple heuristic: if Prosecutor cited security flaw, cap; else average with TechLead bias
            final_score = int((tech_score * 0.6 + sum(scores) / 3 * 0.4))  # bias to TechLead

        else:
            final_score = sum(scores) // 3  # simple avg if low variance

        # Apply hardcoded rules
        # Security override
        if "security flaw" in opinions[0]["argument"].lower() or "os.system" in opinions[0]["argument"].lower():
            final_score = min(final_score, 3)  # cap at 3

        # Fact supremacy
        if "hallucination" in opinions[1]["argument"].lower() or len(opinions[1]["cited_evidence"]) == 0:
            final_score = pros_score  # overrule Defense

        # Functionality weight
        if dim_id == "graph_orchestration" and tech_score >= 4:
            final_score = max(final_score, 4)  # boost if TechLead confirms modular

        # Remediation: aggregate from TechLead + general advice
        remediation = opinions[2]["argument"] + "\nTo improve: Follow rubric forensic_instruction."

        criteria.append(CriterionResult(
            dimension_id=dim_id,
            dimension_name=dim["name"],
            final_score=final_score,
            judge_opinions=opinions,
            dissent_summary=dissent,
            remediation=remediation
        ))
        total_score += final_score
        remediations.append(remediation)

    overall = total_score / len(criteria) if criteria else 0.0
    report = AuditReport(
        repo_url=state["repo_url"],
        executive_summary=f"Audit complete. Overall score: {overall:.1f}/5. Key issues: {len([c for c in criteria if c.final_score < 3])} low-scoring criteria.",
        overall_score=overall,
        criteria=criteria,
        remediation_plan="\n\n".join(remediations)
    )

    state["final_report"] = report

    # Generate Markdown file
    generate_markdown_report(report, output_path="audit/report_onself_generated/audit_report.md")  # adjust path as needed

    return state


def generate_markdown_report(report: AuditReport, output_path: str) -> None:
    """Write structured Markdown file to disk (not console)."""
    md_content = f"# Audit Report for {report.repo_url}\n\n"

    # Executive Summary
    md_content += "## Executive Summary\n"
    md_content += report.executive_summary + "\n"
    md_content += f"Overall Score: {report.overall_score:.1f}/5\n\n"

    # Criterion Breakdown
    md_content += "## Criterion Breakdown\n"
    for crit in report.criteria:
        md_content += f"### {crit.dimension_name} ({crit.dimension_id})\n"
        md_content += f"Final Score: {crit.final_score}/5\n\n"
        md_content += "#### Judge Opinions:\n"
        for op in crit.judge_opinions:
            md_content += f"- **{op.judge} (Score {op.score}):** {op.argument}\n  Cited: {', '.join(op.cited_evidence)}\n"
        if crit.dissent_summary:
            md_content += f"#### Dissent Summary: {crit.dissent_summary}\n"
        md_content += "\n"

    # Remediation Plan
    md_content += "## Remediation Plan\n"
    md_content += report.remediation_plan + "\n"

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(md_content)