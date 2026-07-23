"""Local LLM interface via Ollama."""
import json
import urllib.request
import urllib.error

from core.config import config


def _call_ollama(method="POST", path="", body=None, stream=False):
    host = config.get("llm", "ollama_host")
    url = f"{host}/api/{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            if stream:
                return resp
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.read().decode()}"}
    except Exception as e:
        return {"error": str(e)}


def list_models():
    """List available Ollama models."""
    result = _call_ollama("GET", "tags")
    if "error" in result:
        return []
    return [m["name"] for m in result.get("models", [])]


def pull_model(name):
    """Pull a model from Ollama."""
    return _call_ollama(body={"name": name}, path="pull")


def is_running():
    """Check if Ollama server is reachable."""
    try:
        _call_ollama("GET", "")
        return True
    except Exception:
        return False


def _chat_stream(body):
    """Stream chat response, yielding content chunks."""
    resp = _call_ollama(body=body, path="chat", stream=True)
    if not hasattr(resp, "read"):
        return
    for line in resp:
        if not line:
            continue
        try:
            chunk = json.loads(line)
        except json.JSONDecodeError:
            continue
        delta = chunk.get("message", {}).get("content", "")
        if delta:
            yield delta
        if chunk.get("done"):
            return


def chat(messages, model=None, stream=False, tools=None):
    """Send a chat completion request to Ollama.

    Args:
        messages: List of {"role": ..., "content": ...} dicts.
        model: Model name (defaults to config).
        stream: If True, returns response dict.
        tools: Optional list of tool schemas.

    Returns:
        Response dict (stream=False) or generator (stream=True).
    """
    if model is None:
        model = config.get("llm", "model")

    body = {
        "model": model,
        "messages": messages,
        "stream": stream,
        "options": {
            "temperature": config.get("llm", "temperature"),
            "num_predict": config.get("llm", "max_tokens"),
        },
    }
    if tools:
        body["tools"] = tools

    if stream:
        return _chat_stream(body)

    return _call_ollama(body=body, path="chat")


def generate(prompt, system=None, model=None, stream=False):
    """Simple text generation."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    return chat(messages, model=model, stream=stream)


def embed(text, model=None):
    """Get embeddings for text."""
    if model is None:
        model = config.get("llm", "model")
    result = _call_ollama(body={"model": model, "prompt": text}, path="embeddings")
    if "error" in result:
        return None
    return result.get("embedding")


TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "run_code",
        "description": "Execute Python code on the local machine. Use for computations, data processing, file operations.",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Python code to execute"}
            },
            "required": ["code"],
        },
    },
}
