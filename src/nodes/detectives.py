import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import base64
from typing import Dict, List

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI

from src.state import AgentState, Evidence
from src.tools.repo_tools import clone_or_use_local, extract_git_history, analyze_graph_structure, check_file_exists
from src.tools.doc_tools import ingest_pdf, query_pdf, extract_cited_filepaths


def repo_investigator(state: AgentState) -> Dict:
    """Executes target_artifact='github_repo' forensics.
    
    Falls back to local repo analysis when network is unavailable.
    """
    print("--- REPO INVESTIGATOR ---")
    repo_url = state["repo_url"]
    rubric = state["rubric_dimensions"]
    evidences: Dict[str, List[Evidence]] = {}

    try:
        # IMPORTANT: keep _temp_dir_handle alive for the full duration so the OS
        # does not delete the directory while we are using it.
        repo_path, is_temp, _temp_dir_handle = clone_or_use_local(repo_url)
        git_history = extract_git_history(repo_path)
        ast_analysis = analyze_graph_structure(repo_path)
        
        for dimension in rubric:
            if dimension.get("target_artifact") != "github_repo":
                continue
                
            dim_id = dimension["id"]
            evidences[dim_id] = []
            
            if dim_id == "git_forensic_analysis":
                commit_count = len(git_history.splitlines())
                evidences[dim_id].append(Evidence(
                    goal="Extract Git History Progression",
                    found=commit_count > 3,
                    content=git_history[:1000],
                    location="git log",
                    rationale=f"History extracted ({commit_count} commits). {'Clone succeeded.' if is_temp else 'Local fallback used.'}",
                    confidence=1.0 if is_temp else 0.8
                ))
            
            elif dim_id == "state_management_rigor":
                has_state = check_file_exists(repo_path, "src/state.py") or check_file_exists(repo_path, "src/graph.py")
                evidences[dim_id].append(Evidence(
                    goal="Verify State File Existence",
                    found=has_state,
                    content="src/state.py or src/graph.py detected",
                    location="src/state.py",
                    rationale="Verified file path",
                    confidence=1.0
                ))
                evidences[dim_id].append(Evidence(
                    goal="Verify Pydantic/TypedDict usage",
                    found=ast_analysis.has_pydantic or ast_analysis.has_typed_dict,
                    content=f"Pydantic: {ast_analysis.has_pydantic}, TypedDict: {ast_analysis.has_typed_dict}",
                    location="State classes",
                    rationale="Parsed AST for base classes",
                    confidence=0.9
                ))
                evidences[dim_id].append(Evidence(
                    goal="Verify Reducers",
                    found=len(ast_analysis.state_reducers) > 0,
                    content=f"Reducers found: {', '.join(ast_analysis.state_reducers)}",
                    location="Annotated type hints",
                    rationale="Parsed AST for operator usage in AnnAssign",
                    confidence=0.9
                ))

            elif dim_id == "graph_orchestration":
                 evidences[dim_id].append(Evidence(
                    goal="Verify StateGraph Definition",
                    found=ast_analysis.state_graph_instantiated,
                    content="Graph instantiated",
                    location="src/graph.py",
                    rationale="Parsed AST for StateGraph call",
                    confidence=0.9
                ))
                 evidences[dim_id].append(Evidence(
                    goal="Verify Fan-Out / Fan-In patterns",
                    found=len(ast_analysis.fan_out_fan_in_patterns) > 0,
                    content=f"Patterns matching edge logic: {', '.join(ast_analysis.fan_out_fan_in_patterns)}",
                    location="StateGraph routing",
                    rationale="Parsed AST for add_edge / conditional arguments",
                    confidence=0.8
                ))
                
            elif dim_id == "safe_tool_engineering":
                 evidences[dim_id].append(Evidence(
                    goal="Verify Git Sandboxing",
                    found=ast_analysis.use_tempfile,
                    content="tempfile.TemporaryDirectory usage detected.",
                    location="src/tools/",
                    rationale="Parsed tool files for tempfile instantiation.",
                    confidence=0.9
                ))
                 evidences[dim_id].append(Evidence(
                    goal="Security Violations",
                    found=ast_analysis.has_os_system,
                    content="os.system call detected - Potential Sandbox Break" if ast_analysis.has_os_system else "No os.system calls found.",
                    location="AST traversal",
                    rationale="Parsed os.system call",
                    confidence=0.9
                ))
                
            elif dim_id == "structured_output_enforcement":
                 evidences[dim_id].append(Evidence(
                    goal="Structured Output Usage",
                    found=ast_analysis.uses_structured_output,
                    content="with_structured_output or bind_tools parsed",
                    location="src/nodes/judges.py",
                    rationale="AST parsed judge definition",
                    confidence=0.9
                ))

        # Explicit cleanup of temp dir handle
        if is_temp and _temp_dir_handle is not None:
            _temp_dir_handle.cleanup()

    except Exception as e:
        # Fallback evidence on crash
        evidences["git_forensic_analysis"] = [Evidence(
            goal="Clone and Extract Repo", found=False, content=str(e), location=repo_url, rationale="Clone Failed", confidence=0.0
        )]
        return {"evidences": evidences, "errors": [f"RepoInvestigator failed: {str(e)}"]}

    return {"evidences": evidences, "errors": []}


def doc_analyst(state: AgentState) -> Dict:
    """Executes target_artifact='pdf_report' forensics."""
    print("--- DOC ANALYST ---")
    pdf_path = state["pdf_path"]
    rubric = state["rubric_dimensions"]
    evidences: Dict[str, List[Evidence]] = {}

    chunks = ingest_pdf(pdf_path)
    
    for dimension in rubric:
        if dimension.get("target_artifact") != "pdf_report":
            continue
            
        dim_id = dimension["id"]
        evidences[dim_id] = []
        
        if dim_id == "theoretical_depth":
            keywords = ["Dialectical Synthesis", "Fan-In", "Fan-Out", "Metacognition", "State Synchronization"]
            keyword_evidence = query_pdf(chunks, keywords)
            
            for ev in keyword_evidence:
                 evidences[dim_id].append(Evidence(
                    goal=f"Determine presence of {ev['keyword']}",
                    found=True,
                    content=ev['context'][:500],
                    location="PDF Document context",
                    rationale="Keyword matched in docling chunk",
                    confidence=ev['confidence']
                ))
            if not keyword_evidence:
                 evidences[dim_id].append(Evidence(
                    goal="Determine theoretical depth",
                    found=False,
                    content="No relevant keywords found",
                    location="PDF report",
                    rationale="Docling iteration complete",
                    confidence=1.0
                ))

        elif dim_id == "report_accuracy":
             cited_paths = extract_cited_filepaths(chunks)
             
             if not cited_paths:
                   evidences[dim_id].append(Evidence(
                    goal="Extract file paths from PDF",
                    found=False,
                    content="No structured file paths cited in text.",
                    location="PDF Document context",
                    rationale="Regex extraction found no paths.",
                    confidence=0.8
                ))
             else:
                   evidences[dim_id].append(Evidence(
                        goal="Extract file paths from PDF",
                        found=True,
                        content=f"Report cites files: {', '.join(cited_paths)}",
                        location="PDF Document context",
                        rationale=f"Extracted {len(cited_paths)} file path(s).",
                        confidence=0.8
                    ))

    return {"evidences": evidences, "errors": []}


def vision_inspector(state: AgentState) -> Dict:
    """Analyses architectural diagrams using OpenAI vision model.
    
    Checks for automaton_flow.png at repo root, then uses GPT-4o to
    describe and evaluate the diagram against rubric criteria.
    """
    print("--- VISION INSPECTOR ---")
    evidences: Dict[str, List[Evidence]] = {}

    # Look for the diagram file
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    diagram_candidates = [
        os.path.join(project_root, "automaton_flow.png"),
        os.path.join(project_root, "automaton_flow.jpg"),
        os.path.join(project_root, "automaton_flow.svg"),
        os.path.join(project_root, "architecture.png"),
        os.path.join(project_root, "architecture.svg"),
        os.path.join(project_root, "reports", "automaton_flow.svg"),
    ]
    
    diagram_path = None
    for candidate in diagram_candidates:
        if os.path.exists(candidate):
            diagram_path = candidate
            break
    
    if not diagram_path:
        evidences["swarm_visual"] = [Evidence(
            goal="Architectural Diagram Analysis",
            found=False,
            content="No architectural diagram found in project root.",
            location="Project root",
            rationale="Searched for automaton_flow.png/jpg, architecture.png",
            confidence=0.9
        )]
        return {"evidences": evidences, "errors": []}

    # Encode the image and send to GPT-4o for analysis
    try:
        with open(diagram_path, "rb") as f:
            data = f.read()

        # Determine content type by extension; allow SVGs as well as raster images
        ext = os.path.splitext(diagram_path)[1].lower()
        if ext == ".svg":
            mime = "image/svg+xml"
        elif ext in (".jpg", ".jpeg"):
            mime = "image/jpeg"
        else:
            mime = "image/png"

        img_b64 = base64.b64encode(data).decode("utf-8")

        llm = ChatOpenAI(model="gpt-4o", temperature=0, max_tokens=1024)

        analysis_prompt = (
            "Analyze this LangGraph architectural diagram. Determine:\n"
            "1. Does it show parallel fan-out from START to multiple Detective nodes?\n"
            "2. Is there a synchronization/aggregation node (fan-in) after detectives?\n"
            "3. Are there parallel Judge nodes (Prosecutor, Defense, TechLead)?\n"
            "4. Is there a Chief Justice synthesis node before END?\n"
            "5. Does it clearly distinguish parallel vs sequential flow?\n\n"
            "Respond with a structured assessment of each point."
        )

        response = llm.invoke([
            SystemMessage(content="You are an expert LangGraph architecture reviewer."),
            HumanMessage(content=[
                {"type": "text", "text": analysis_prompt},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{img_b64}"}}
            ])
        ])

        analysis_text = response.content
        
        # Check for key indicators of a proper swarm diagram
        has_parallel = any(kw in analysis_text.lower() for kw in ["parallel", "fan-out", "fan out", "concurrent"])
        has_sync = any(kw in analysis_text.lower() for kw in ["aggregat", "synchroniz", "fan-in", "fan in", "collect"])
        
        evidences["swarm_visual"] = [Evidence(
            goal="Architectural Diagram Analysis",
            found=has_parallel and has_sync,
            content=analysis_text[:800],
            location=os.path.basename(diagram_path),
            rationale="GPT-4o vision analysis of architectural diagram",
            confidence=0.85
        )]

    except Exception as e:
        evidences["swarm_visual"] = [Evidence(
            goal="Architectural Diagram Analysis",
            found=False,
            content=f"Vision analysis failed: {str(e)}",
            location=os.path.basename(diagram_path) if diagram_path else "N/A",
            rationale=f"Diagram exists but vision API call failed",
            confidence=0.3
        )]

    return {"evidences": evidences, "errors": []}
