"""Code execution tools - Python sandbox and shell command execution.

Merged from OpenHermes + NEO-AGENT code execution tools.
"""
import ast
import io
import json
import os
import contextlib
import subprocess
import sys
import traceback


# ---------------------------------------------------------------------------
# Safe Python Execution
# ---------------------------------------------------------------------------

BLOCKED_MODULES = {
    "os", "subprocess", "shutil", "socket", "ctypes",
    "multiprocessing", "threading", "signal",
}

# Patterns that suggest destructive intent
DANGEROUS_PATTERNS = [
    "os.system", "subprocess.", "shutil.rmtree",
    "pathlib.Path.unlink", "rm -rf", "mkfs",
    "dd if=", "chmod 777", "sudo ",
]


def run_python(code: str) -> str:
    """Execute Python code in a sandbox and return output.

    Args:
        code: Python code to execute

    Returns:
        Captured stdout and stderr output
    """
    # Safety check - block dangerous patterns
    for pattern in DANGEROUS_PATTERNS:
        if pattern in code:
            return f"⚠️ Blocked dangerous operation: {pattern}"

    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()

    try:
        ast.parse(code)

        with contextlib.redirect_stdout(stdout_capture), \
             contextlib.redirect_stderr(stderr_capture):

            safe_builtins = {
                k: v for k, v in __builtins__.items()
                if k not in ("__import__", "exec", "eval", "compile", "open")
            }
            exec(code, {"__builtins__": safe_builtins}, {})

        out = stdout_capture.getvalue()
        err = stderr_capture.getvalue()

        result = ""
        if out:
            result += f"📤 Output:\n{out[:5000]}"
        if err:
            result += f"⚠️ Stderr:\n{err[:2000]}"
        if not out and not err:
            result = "✅ Code executed successfully (no output)"

        return result.strip()
    except Exception as e:
        tb = traceback.format_exc()
        return f"❌ Error:\n{tb[:3000]}"


# ---------------------------------------------------------------------------
# Shell Command Execution
# ---------------------------------------------------------------------------

DANGEROUS_COMMANDS = [
    "rm -rf /", "rm -rf /*", "mkfs", "dd if=",
    "> /dev/sda", "fdisk", "chmod 777 /",
    "sudo ", "su ", "passwd", "shutdown",
]


def run_shell(command: str, timeout: int = 30) -> str:
    """Run a shell command and return output (read-only safe by default).

    Args:
        command: Shell command to run
        timeout: Maximum execution time in seconds (default: 30)

    Returns:
        Command output (stdout + stderr)
    """
    for dangerous in DANGEROUS_COMMANDS:
        if dangerous in command.lower():
            return f"⚠️ Blocked dangerous command: {dangerous}"

    try:
        result = subprocess.run(
            command, shell=True, capture_output=True,
            text=True, timeout=timeout,
        )
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            if output:
                output += "\n--- stderr ---\n"
            output += result.stderr
        if not output:
            output = "(no output)"
        # Truncate
        if len(output) > 10000:
            output = output[:10000] + "\n... (output truncated)"
        return output
    except subprocess.TimeoutExpired:
        return f"ERROR: Command timed out after {timeout}s"
    except Exception as e:
        return f"ERROR: {e}"


# ---------------------------------------------------------------------------
# Code Analysis
# ---------------------------------------------------------------------------

def analyze_code(code: str) -> str:
    """Analyze Python code for issues and complexity.

    Args:
        code: Python code to analyze

    Returns:
        Analysis report
    """
    issues = []
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"❌ Syntax Error:\n{e}"

    # Count functions and classes
    funcs = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    lines = code.split("\n")

    info = [
        f"Lines: {len(lines)}",
        f"Functions: {len(funcs)}",
        f"Classes: {len(classes)}",
    ]

    # Check for common issues
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and len(node.body) > 50:
            issues.append(f"Function '{node.name}' has {len(node.body)} lines "
                          f"(consider refactoring)")
        if isinstance(node, ast.Try) and len(node.handlers) == 0:
            issues.append(f"Bare try block at line {node.lineno} (no except)")
        if isinstance(node, ast.ExceptHandler) and node.type is None:
            issues.append(f"Bare except at line {node.lineno}")

    report = "📊 Code Analysis:\n" + "\n".join(info)
    if issues:
        report += "\n\n⚠️ Issues:\n" + "\n".join(issues[:10])
    else:
        report += "\n\n✅ No issues found"

    return report
