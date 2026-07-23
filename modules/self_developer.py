"""Self-Developer - Base44-style no-code feature builder.

Describe what you want in natural language, and the agent:
  1. Generates the Python code using LLM
  2. Creates the file(s)
  3. Validates syntax
  4. Auto-registers tools
  5. Creates git commits & PRs
"""
import ast
import json
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path


# ---------------------------------------------------------------------------
# Code Generator
# ---------------------------------------------------------------------------

def generate_module_from_prompt(prompt: str, module_name: str = None) -> dict:
    """Generate a Python module from a natural language description using LLM.

    Args:
        prompt: Description of what to build
        module_name: Optional filename (without .py), auto-generated if not given

    Returns:
        Dict with {success, filepath, code, error, actions}
    """
    try:
        from core.llm import chat

        if not module_name:
            # Generate name from prompt
            name_prompt = (
                f"Generate a single short Python module filename (without .py) for this feature. "
                f"Reply with ONLY the filename, nothing else.\n\nFeature: {prompt}"
            )
            result = chat([{"role": "user", "content": name_prompt}])
            module_name = result.get("message", {}).get("content", "").strip().lower()
            module_name = "".join(c for c in module_name if c.isalnum() or c == "_")
            if not module_name:
                module_name = f"custom_{int(time.time())}"

        # System prompt for code generation
        system_prompt = """You are a Python code generator. Generate ONLY valid Python code.
Rules:
- Output ONLY the code, no explanations, no markdown (no ```python etc.)
- Use proper imports at the top
- Each function must have a docstring with Args and Returns
- Make functions standalone and self-contained
- Use type hints
- Handle errors gracefully (try/except)
- Max 200 lines per file
- The file will be placed in /root/Desktop/agent/modules/
- Name the functions clearly based on their purpose"""

        code_prompt = f"{system_prompt}\n\nGenerate a Python module called '{module_name}' that does:\n{prompt}"

        result_dict = chat([{"role": "user", "content": code_prompt}])
        response = result_dict.get("message", {}).get("content", "")

        # Clean up the response - remove markdown code blocks if present
        code = response.strip()
        if "```" in code:
            # Extract code from markdown blocks
            parts = code.split("```")
            for i, part in enumerate(parts):
                if i % 2 == 1:  # Odd indices are code blocks
                    # Skip language identifier line if present
                    lines = part.split("\n")
                    if lines and lines[0] and not lines[0].startswith(("import", "def ", "class ", "#")):
                        lines = lines[1:]
                    code = "\n".join(lines)
                    break

        # Validate syntax
        try:
            ast.parse(code)
        except SyntaxError as e:
            return {"success": False, "error": f"Syntax error in generated code: {e}", "code": code}

        # Determine the file path
        filepath = os.path.join(os.path.dirname(os.path.dirname(__file__)), "modules", f"{module_name}.py")

        # Check if file already exists
        if os.path.exists(filepath):
            # If exists, add _new suffix
            module_name = f"{module_name}_new"
            filepath = os.path.join(os.path.dirname(os.path.dirname(__file__)), "modules", f"{module_name}.py")

        # Write the file
        with open(filepath, "w") as f:
            f.write(code)

        # Parse functions for tool registration
        actions = _parse_functions(code, module_name)

        return {
            "success": True,
            "filepath": filepath,
            "module_name": module_name,
            "code": code,
            "actions": actions,
        }

    except Exception as e:
        return {"success": False, "error": str(e), "code": None}


def _parse_functions(code: str, module_name: str) -> list:
    """Parse Python code and extract function signatures for tool registration."""
    actions = []
    try:
        tree = ast.parse(code)
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.FunctionDef):
                # Get docstring
                docstring = ast.get_docstring(node) or "No description"
                # Get params
                params = []
                for arg in node.args.args:
                    if arg.arg == "self":
                        continue
                    arg_name = arg.arg
                    annotation = "str"
                    if arg.annotation and hasattr(arg.annotation, "id"):
                        annotation = arg.annotation.id
                    elif arg.annotation and hasattr(arg.annotation, "attr"):
                        annotation = arg.annotation.attr
                    params.append({
                        "name": arg_name,
                        "type": annotation,
                        "required": True,
                    })
                actions.append({
                    "name": node.name,
                    "description": docstring.split("\n")[0] if docstring else module_name,
                    "params": params,
                    "module": module_name,
                })
    except Exception:
        pass
    return actions


# ---------------------------------------------------------------------------
# Auto-Register Tool
# ---------------------------------------------------------------------------

def auto_register_module(module_name: str) -> dict:
    """Auto-import and register all functions from a generated module.

    Args:
        module_name: Name of the module (without .py)

    Returns:
        Dict with {success, registered_functions, error}
    """
    try:
        # Import the module dynamically
        import importlib

        try:
            mod = importlib.import_module(f"modules.{module_name}")
        except ImportError:
            # Try reload
            importlib.reload(importlib.import_module(f"modules.{module_name}"))
            mod = importlib.import_module(f"modules.{module_name}")

        # Get all functions
        functions = []
        for name in dir(mod):
            obj = getattr(mod, name)
            if callable(obj) and not name.startswith("_"):
                doc = obj.__doc__ or "No description"
                functions.append({"name": name, "doc": doc.split("\n")[0]})
                functions.append(name)

        # Register in core engine
        try:
            from core.engine import engine, actions

            for func_name in dir(mod):
                obj = getattr(mod, func_name)
                if callable(obj) and not func_name.startswith("_"):
                    # Register in action registry
                    actions.register(
                        name=func_name,
                        handler=obj,
                        description=obj.__doc__ or f"From {module_name}",
                    )
                    # Register in tool registry
                    try:
                        from modules.tool_registry import registry
                        registry.register(
                            name=func_name,
                            description=obj.__doc__ or f"From {module_name}",
                            handler=obj,
                            icon="🧰",
                            category="Custom",
                        )
                    except Exception:
                        pass

            return {"success": True, "registered_functions": functions, "module": module_name}
        except Exception as e:
            return {"success": False, "error": f"Failed to register: {e}", "module": module_name}

    except Exception as e:
        return {"success": False, "error": str(e), "module": module_name}


# ---------------------------------------------------------------------------
# Git & PR Integration
# ---------------------------------------------------------------------------

def create_git_commit(message: str, files: list = None) -> dict:
    """Create a git commit with the given message.

    Args:
        message: Commit message
        files: List of file paths to commit (None = all changes)

    Returns:
        Dict with {success, commit_hash, output, error}
    """
    try:
        repo_dir = os.path.dirname(os.path.dirname(__file__))
        cmds = [
            ["git", "-C", repo_dir, "add"] + (files if files else ["-A"]),
            ["git", "-C", repo_dir, "commit", "-m", message],
        ]
        for cmd in cmds:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if r.returncode not in (0, 1):  # 1 = nothing to commit
                return {"success": False, "error": r.stderr, "output": r.stdout}

        # Get commit hash
        r = subprocess.run(
            ["git", "-C", repo_dir, "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10,
        )
        commit_hash = r.stdout.strip()

        return {"success": True, "commit_hash": commit_hash, "message": message}

    except Exception as e:
        return {"success": False, "error": str(e)}


def create_github_pr(title: str, body: str = None) -> dict:
    """Create a GitHub Pull Request using gh CLI.

    Args:
        title: PR title
        body: PR description (optional)

    Returns:
        Dict with {success, pr_url, error}
    """
    try:
        repo_dir = os.path.dirname(os.path.dirname(__file__))

        # Check if gh is installed
        r = subprocess.run(["which", "gh"], capture_output=True, text=True, timeout=5)
        if r.returncode != 0:
            return {"success": False, "error": "GitHub CLI (gh) not installed. Install with: apt install gh"}

        # Check if we're on a branch (not main)
        r = subprocess.run(
            ["git", "-C", repo_dir, "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=10,
        )
        branch = r.stdout.strip()
        if branch == "main":
            # Create a feature branch
            branch_name = f"feature/auto-{int(time.time())}"
            subprocess.run(
                ["git", "-C", repo_dir, "checkout", "-b", branch_name],
                capture_output=True, text=True, timeout=10,
            )
            branch = branch_name

        # Push to remote
        r = subprocess.run(
            ["git", "-C", repo_dir, "push", "-u", "origin", branch],
            capture_output=True, text=True, timeout=60,
        )
        if r.returncode != 0:
            return {"success": False, "error": f"Push failed: {r.stderr}"}

        # Create PR using gh CLI
        pr_body = body or f"Auto-generated PR from AI Agent Beast\n\n{title}"
        r = subprocess.run(
            ["gh", "pr", "create", "--title", title, "--body", pr_body],
            capture_output=True, text=True, timeout=30,
            cwd=repo_dir,
        )
        if r.returncode != 0:
            return {"success": False, "error": f"PR creation failed: {r.stderr}"}

        pr_url = r.stdout.strip()
        return {"success": True, "pr_url": pr_url, "branch": branch}

    except Exception as e:
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Full Pipeline
# ---------------------------------------------------------------------------

def build_from_prompt(prompt: str, module_name: str = None, create_pr: bool = True) -> dict:
    """Full pipeline: generate code → save → register → commit → PR.

    Args:
        prompt: Natural language description of what to build
        module_name: Optional module name
        create_pr: Whether to create a GitHub PR (default: True)

    Returns:
        Dict with full result
    """
    result = {"prompt": prompt, "steps": [], "success": False}

    # Step 1: Generate
    gen = generate_module_from_prompt(prompt, module_name)
    result["steps"].append({"step": "generate", **gen})
    if not gen.get("success"):
        result["error"] = gen.get("error")
        return result

    module_name = gen["module_name"]
    filepath = gen["filepath"]

    # Step 2: Register
    reg = auto_register_module(module_name)
    result["steps"].append({"step": "register", **reg})

    # Step 3: Git commit
    commit_msg = f"✨ Auto-generated: {module_name} - {prompt[:60]}"
    commit = create_git_commit(commit_msg, [filepath])
    result["steps"].append({"step": "commit", **commit})

    # Step 4: GitHub PR
    if create_pr and commit.get("success"):
        pr_title = f"✨ {module_name}: {prompt[:50]}"
        pr_body = f"## Auto-generated by AI Agent Beast\n\n**Prompt:** {prompt}\n\n**Files:**\n- `modules/{module_name}.py`\n\n### What it does\n{gen.get('actions', [])}"
        pr = create_github_pr(pr_title, pr_body)
        result["steps"].append({"step": "pr", **pr})
        if pr.get("success"):
            result["pr_url"] = pr["pr_url"]

    result["success"] = True
    result["module_name"] = module_name
    result["filepath"] = filepath
    return result


# ---------------------------------------------------------------------------
# Quick Actions
# ---------------------------------------------------------------------------

def list_generated_modules() -> list:
    """List all auto-generated modules."""
    modules_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "modules")
    generated = []
    prefix = "custom_"
    for f in sorted(os.listdir(modules_dir)):
        if f.startswith(prefix) and f.endswith(".py"):
            generated.append(f.replace(".py", ""))
    return generated


def analyze_code_quality(filepath: str) -> dict:
    """Analyze Python file for code quality issues.

    Args:
        filepath: Path to Python file

    Returns:
        Dict with {success, issues, warnings, errors}
    """
    try:
        with open(filepath) as f:
            code = f.read()

        issues = []

        # Check syntax
        try:
            ast.parse(code)
        except SyntaxError as e:
            issues.append({"type": "error", "line": e.lineno, "msg": str(e)})

        # Check line length
        for i, line in enumerate(code.split("\n"), 1):
            if len(line) > 100:
                issues.append({"type": "warning", "line": i, "msg": f"Line too long ({len(line)} chars)"})

        # Check for missing docstrings
        tree = ast.parse(code)
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                if not ast.get_docstring(node):
                    issues.append({"type": "warning", "line": node.lineno, "msg": f"Missing docstring: {node.name}"})

        return {"success": True, "issues": issues, "filepath": filepath}
    except Exception as e:
        return {"success": False, "error": str(e)}
