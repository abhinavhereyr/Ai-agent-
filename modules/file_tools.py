"""File operations tools - read, write, edit, list, search files.

Merged from OpenHermes file tools.
"""
import os
import subprocess
from pathlib import Path


def file_read(path: str) -> str:
    """Read contents of a file with line numbers.

    Args:
        path: Absolute path to the file

    Returns:
        File contents with line numbers (up to 20000 chars)
    """
    try:
        p = Path(path).expanduser().resolve()
        if not p.exists():
            return f"File not found: {path}"
        content = p.read_text(encoding="utf-8", errors="replace")
        lines = content.split("\n")
        numbered = "\n".join(f"{i+1:4d} | {l}" for i, l in enumerate(lines))
        preface = f"📄 {path} ({len(lines)} lines, {p.stat().st_size} bytes)"
        result = f"{preface}\n\n{numbered}"
        if len(result) > 20000:
            result = result[:20000] + "\n\n... (truncated)"
        return result
    except Exception as e:
        return f"Read error: {e}"


def file_write(path: str, content: str) -> str:
    """Write content to a file (creates directories if needed).

    Args:
        path: Absolute path to the file
        content: Content to write

    Returns:
        Success/error message
    """
    try:
        p = Path(path).expanduser().resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"✅ Written {len(content)} bytes to {path}"
    except Exception as e:
        return f"Write error: {e}"


def file_edit(path: str, old_string: str, new_string: str) -> str:
    """Replace first occurrence of text in a file.

    Args:
        path: Absolute path to the file
        old_string: Text to replace
        new_string: Replacement text

    Returns:
        Success/error message
    """
    try:
        p = Path(path).expanduser().resolve()
        content = p.read_text(encoding="utf-8")
        if old_string not in content:
            return f"String not found in {path}"
        new_content = content.replace(old_string, new_string, 1)
        p.write_text(new_content, encoding="utf-8")
        return f"✅ Edited {path}"
    except Exception as e:
        return f"Edit error: {e}"


def file_list(path: str = ".", pattern: str = "*") -> str:
    """List files in a directory with glob pattern.

    Args:
        path: Directory path
        pattern: Glob filter (default: *)

    Returns:
        Directory listing
    """
    try:
        p = Path(path).expanduser().resolve()
        if not p.exists():
            return f"Directory not found: {path}"
        if not p.is_dir():
            return f"Not a directory: {path}"

        items = list(p.glob(pattern))
        if not items:
            return f"No files matching '{pattern}' in {path}"

        lines = []
        total_size = 0
        for item in sorted(items):
            if item.is_dir():
                lines.append(f"  [DIR]  {item.name}/")
            else:
                size = item.stat().st_size
                total_size += size
                modified = item.stat().st_mtime
                import datetime
                mtime = datetime.datetime.fromtimestamp(modified).strftime("%Y-%m-%d %H:%M")
                lines.append(f"  {size:>8}  {mtime}  {item.name}")

        summary = f"📁 {p} ({len(items)} items, {total_size:,} bytes)"
        return f"{summary}\n" + "\n".join(lines[:200])
    except Exception as e:
        return f"List error: {e}"


def file_delete(path: str) -> str:
    """Delete a file or empty directory.

    Args:
        path: Absolute path to delete

    Returns:
        Success/error message
    """
    try:
        p = Path(path).expanduser().resolve()
        if not p.exists():
            return f"Path not found: {path}"
        if p.is_file():
            size = p.stat().st_size
            p.unlink()
            return f"✅ Deleted file: {path} ({size} bytes)"
        elif p.is_dir():
            import shutil
            shutil.rmtree(p)
            return f"✅ Deleted directory: {path}"
        return f"Unknown path type: {path}"
    except Exception as e:
        return f"Delete error: {e}"


def file_grep(path: str, pattern: str) -> str:
    """Search for a pattern in a file.

    Args:
        path: File path to search in
        pattern: Text or regex pattern to find

    Returns:
        Matching lines with line numbers
    """
    try:
        p = Path(path).expanduser().resolve()
        if not p.exists():
            return f"File not found: {path}"
        content = p.read_text(encoding="utf-8", errors="replace")
        lines = content.split("\n")
        matches = []
        for i, line in enumerate(lines, 1):
            if pattern in line:
                matches.append(f"{i:4d} | {line[:200]}")
        if not matches:
            return f"No matches for '{pattern}' in {path}"
        result = f"🔍 {len(matches)} matches in {path}\n" + "\n".join(matches)
        if len(result) > 5000:
            result = result[:5000] + "\n\n... (truncated)"
        return result
    except Exception as e:
        return f"Grep error: {e}"


def file_download(url: str, dest: str = None) -> str:
    """Download a file from URL to local path.

    Args:
        url: Source URL to download from
        dest: Destination path (default: basename from URL in downloads dir)

    Returns:
        Success/error message
    """
    try:
        if not dest:
            downloads = Path.home() / "downloads"
            downloads.mkdir(exist_ok=True)
            dest = str(downloads / url.split("/")[-1].split("?")[0])

        import requests
        resp = requests.get(url, stream=True, timeout=30)
        resp.raise_for_status()

        total = 0
        p = Path(dest)
        with open(p, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
                total += len(chunk)

        return f"✅ Downloaded {total:,} bytes to {dest}"
    except Exception as e:
        return f"Download error: {e}"
