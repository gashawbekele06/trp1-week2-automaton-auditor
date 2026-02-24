import tempfile
import subprocess
import ast
import os
from typing import Dict, List, Any, Tuple
from langchain_core.tools import tool


@tool
def safe_git_clone(repo_url: str) -> Dict[str, Any]:
    """Clone repo safely into a temporary directory, handling authentication errors gracefully."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        try:
            result = subprocess.run(
                ["git", "clone", "--depth", "1", repo_url, tmp_dir],
                check=True, capture_output=True, text=True
            )
            return {"success": True, "path": tmp_dir, "stdout": result.stdout, "stderr": result.stderr}
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.lower()
            if "authentication" in error_msg or "access token" in error_msg:
                return {"success": False, "path": None, "error": "Git authentication failed – check repo URL or access token."}
            return {"success": False, "path": None, "error": e.stderr}


@tool
def extract_git_history(repo_path: str) -> Dict[str, Any]:
    """Extract git log to analyze history: atomicity, timestamps, commit count. Returns list of commits and summary."""
    try:
        result = subprocess.run(
            ["git", "-C", repo_path, "log", "--oneline", "--reverse", "--pretty=format:%H|%ad|%s", "--date=iso"],
            capture_output=True, text=True, check=True
        )
        commits = []
        lines = result.stdout.strip().split("\n")
        for line in lines if line:
            hash_, date, msg = line.split("|", 2)
            commits.append({"hash": hash_, "timestamp": date, "message": msg})
        
        # Analyze atomicity
        commit_count = len(commits)
        is_monolithic = commit_count <= 1 or (commit_count == 2 and "init" in commits[0]["message"].lower())
        timestamps = [c["timestamp"] for c in commits]
        summary = {
            "commit_count": commit_count,
            "is_atomic": not is_monolithic and commit_count > 3,
            "first_commit": commits[0] if commits else None,
            "last_commit": commits[-1] if commits else None,
            "timestamps_span": (timestamps[-1] - timestamps[0]) if len(timestamps) > 1 else "N/A"
        }
        return {"success": True, "commits": commits, "summary": summary}
    except Exception as e:
        return {"success": False, "error": str(e)}


@tool
def analyze_graph_structure(repo_path: str) -> Dict[str, Any]:
    """Parse Python files in repo to verify StateGraph instantiation and parallel fan-out via AST (no regex)."""
    graph_files = []
    for root, _, files in os.walk(repo_path):
        for file in files:
            if file.endswith(".py"):
                graph_files.append(os.path.join(root, file))
    
    findings = {"state_graph_found": False, "fan_out_detected": False, "details": []}
    
    for file_path in graph_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read(), filename=file_path)
            
            for node in ast.walk(tree):
                # Check for StateGraph instantiation
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "StateGraph":
                    findings["state_graph_found"] = True
                    findings["details"].append(f"StateGraph instantiated in {file_path}")
                
                # Check for fan-out (e.g., add_edge calls in a loop or to multiple nodes)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "add_edge":
                    # Simple heuristic for fan-out: multiple add_edge calls or in a loop
                    if isinstance(node.parent, ast.For) or len([n for n in node.parent.body if isinstance(n, ast.Call) and n.func.attr == "add_edge"]) > 2:
                        findings["fan_out_detected"] = True
                        findings["details"].append(f"Potential fan-out architecture in {file_path} via multiple add_edge calls")
        except SyntaxError:
            findings["details"].append(f"Syntax error in {file_path} – skipped")
    
    return findings