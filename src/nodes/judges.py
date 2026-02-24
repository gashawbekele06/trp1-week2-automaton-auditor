from typing import Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser, OutputFixingParser
from langchain_core.exceptions import OutputParserException
from src.state import JudicialOpinion, AgentState


llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.15)


def create_judge_chain(judge_type: str) -> Any:
    """
    Factory for judge chains with distinct personas and structured output.
    Dynamically injects rubric judicial_logic for the current criterion.
    """
    if judge_type == "Prosecutor":
        system = """You are the Prosecutor. Trust no one. Assume vibe coding. Be harsh and critical.
        Scrutinize for gaps, security flaws, laziness, hallucination liability.
        {judicial_logic}
        Return ONLY valid JudicialOpinion JSON."""
    elif judge_type == "Defense":
        system = """You are the Defense Attorney. Reward effort, intent, creative workarounds.
        Look for spirit of the law, deep thought, iteration in git history.
        {judicial_logic}
        Return ONLY valid JudicialOpinion JSON."""
    else:  # TechLead
        system = """You are the Tech Lead. Pragmatic, focus on maintainability and real workability.
        Ignore vibe/struggle. Assess architectural soundness, code cleanliness, technical debt.
        You are the tie-breaker.
        {judicial_logic}
        Return ONLY valid JudicialOpinion JSON."""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system),
        ("human", "Criterion: {dimension_name}\nEvidence: {evidence_json}\nApply your lens strictly."),
    ])

    # Structured output with Pydantic
    chain = prompt | llm.with_structured_output(JudicialOpinion, method="json_schema")

    # Add retry parser in case of malformed JSON
    fixing_parser = OutputFixingParser.from_llm(parser=JsonOutputParser(), llm=llm)
    return chain | fixing_parser


def judge_node(state: AgentState, judge_type: str) -> AgentState:
    """
    Single judge execution (called in parallel via Send).
    Retries up to 2 times on parse failure.
    """
    idx = state["current_dimension_index"] - 1  # last processed
    dim = state["rubric_dimensions"][idx]
    evidence = state["evidences"].get(dim["id"], [])

    chain = create_judge_chain(judge_type)

    for attempt in range(2):
        try:
            opinion = chain.invoke({
                "judicial_logic": dim["judicial_logic"][judge_type.lower()],
                "dimension_name": dim["name"],
                "evidence_json": str(evidence),  # or json.dumps(evidence)
            })
            opinion["judge"] = judge_type
            opinion["criterion_id"] = dim["id"]
            state["opinions"].append(opinion)
            return state
        except OutputParserException:
            if attempt == 1:
                # Final fallback: record failure
                state["opinions"].append({
                    "judge": judge_type,
                    "criterion_id": dim["id"],
                    "score": 0,
                    "argument": "Parser failed after retry – hallucination or malformed output",
                    "cited_evidence": []
                })
    return state