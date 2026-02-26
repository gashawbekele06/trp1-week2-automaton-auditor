import ast
import subprocess
import tempfile
import json
import os
from typing import Tuple, Optional
from pydantic import BaseModel, Field

def clone_repo_sandboxed(repo_url: str) -> tempfile.TemporaryDirectory:
    """Clones a repo into a temporary directory for sandboxed analysis.
    
    Returns the TemporaryDirectory object (not just the name) so the caller
    keeps a reference and the directory is not garbage-collected prematurely.
    """
    temp_dir = tempfile.TemporaryDirectory()
    try:
        subprocess.run(
            ["git", "clone", "--depth=50", repo_url, temp_dir.name],
            capture_output=True,
            text=True,
            check=True,
            timeout=120,
        )
        return temp_dir
    except subprocess.CalledProcessError as e:
        temp_dir.cleanup()
        raise RuntimeError(f"Failed to clone repository: {e.stderr.strip()}")
    except subprocess.TimeoutExpired:
        temp_dir.cleanup()
        raise RuntimeError(f"Clone timed out after 120 seconds")


def clone_or_use_local(repo_url: str) -> Tuple[str, bool, Optional[tempfile.TemporaryDirectory]]:
    """Try to clone the repo; if network fails, fall back to the local project directory.

    Returns:
        (repo_path, is_temporary, temp_dir_handle): path to analyse, whether it is
        temporary, and the TemporaryDirectory handle that MUST be kept alive by the
        caller to prevent premature directory deletion.  `temp_dir_handle` is None
        when using the local fallback.
    """
    try:
        temp_dir = clone_repo_sandboxed(repo_url)
        # Return the handle so the caller keeps a strong reference
        return temp_dir.name, True, temp_dir
    except RuntimeError:
        # Network / DNS failure — fall back to current project root
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        if os.path.isdir(os.path.join(project_root, ".git")):
            print("  ⚠ Clone failed — falling back to LOCAL repo for self-evaluation")
            return project_root, False, None
        raise

def extract_git_history(repo_path: str) -> str:
    """Extracts git history in an atomic way."""
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "--reverse"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Failed to extract git history: {e.stderr}"

class ArchitectureAnalysis(BaseModel):
    has_pydantic: bool = Field(default=False)
    has_typed_dict: bool = Field(default=False)
    state_reducers: list[str] = Field(default_factory=list)
    state_graph_instantiated: bool = Field(default=False)
    fan_out_fan_in_patterns: list[str] = Field(default_factory=list)
    use_tempfile: bool = Field(default=False)
    has_os_system: bool = Field(default=False)
    uses_structured_output: bool = Field(default=False)

def analyze_graph_structure(repo_path: str) -> ArchitectureAnalysis:
    """Parses AST to determine structural characteristics of the agent."""
    analysis = ArchitectureAnalysis()
    
    # Avoid scanning common virtualenv, cache, and site-package directories which
    # may be present in some clone contexts or when falling back to local repo.
    skip_indicators = (".venv", "venv", "site-packages", "__pycache__")
    for root, _, files in os.walk(repo_path):
        if any(skip in root for skip in skip_indicators):
            continue
        for file in files:
            if not file.endswith(".py"):
                continue
            
            filepath = os.path.join(root, file)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                tree = ast.parse(content)
                
                for node in ast.walk(tree):
                    # Check for State Definition Base Classes
                    if isinstance(node, ast.ClassDef):
                        for base in node.bases:
                            if isinstance(base, ast.Name):
                                if base.id == "BaseModel":
                                    analysis.has_pydantic = True
                                elif base.id == "TypedDict":
                                    analysis.has_typed_dict = True
                                    
                    # Check for Reducers in TypedDict (Annotated type hints)
                    if isinstance(node, ast.AnnAssign):
                        if isinstance(node.annotation, ast.Subscript):
                            if isinstance(node.annotation.value, ast.Name) and node.annotation.value.id == "Annotated":
                                if hasattr(node.annotation, 'slice') and isinstance(node.annotation.slice, ast.Tuple):
                                    for elt in node.annotation.slice.elts:
                                        if isinstance(elt, ast.Attribute) and isinstance(elt.value, ast.Name):
                                            if elt.value.id == "operator":
                                                analysis.state_reducers.append(f"operator.{elt.attr}")
                                            
                    # Check for StateGraph Instantiation and edge logic
                    if isinstance(node, ast.Call):
                        if isinstance(node.func, ast.Name) and node.func.id == "StateGraph":
                            analysis.state_graph_instantiated = True
                        elif isinstance(node.func, ast.Attribute):
                            if node.func.attr in ["add_edge", "add_conditional_edges"]:
                                if hasattr(node.func.value, 'id'):
                                   analysis.fan_out_fan_in_patterns.append(f"{node.func.value.id}.{node.func.attr}")
                                else:
                                    analysis.fan_out_fan_in_patterns.append(f"builder.{node.func.attr}")
                            
                            if node.func.attr == "system":
                                if isinstance(node.func.value, ast.Name) and node.func.value.id == "os":
                                    analysis.has_os_system = True
                            
                            if node.func.attr in ["with_structured_output", "bind_tools"]:
                                analysis.uses_structured_output = True
                                
                    # Check for sandboxed tooling
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                         if node.func.attr == "TemporaryDirectory":
                             if isinstance(node.func.value, ast.Name) and node.func.value.id == "tempfile":
                                 analysis.use_tempfile = True
                             
            except Exception as e:
                # Log or handle parsing errors for non-parseable files
                pass
                
    return analysis

def check_file_exists(repo_path: str, filepath: str) -> bool:
    """Checks if a specified file exists within the cloned repo."""
    target_path = os.path.join(repo_path, filepath)
    return os.path.exists(target_path) and os.path.isfile(target_path)
