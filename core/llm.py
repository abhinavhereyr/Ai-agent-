"""LLM interface — Meta Llama 3 via Groq Cloud (primary) with Ollama fallback.

Provider selection:
- If the GROQ_API_KEY environment variable is set, requests are routed to the
  Groq Cloud API (OpenAI-compatible) using Meta Llama 3 (default model:
  llama-3.1-8b-instant).
- If GROQ_API_KEY is absent, the local Ollama server is used as a fallback.

The public API (chat / generate / list_models / pull_model / is_running /
embed / _chat_stream) is unchanged, so existing callers — including the
tool-calling workflow in core/engine.py — keep working as-is.
"""
import json
import os
import urllib.request
import urllib.error

from core.config import config


def groq_api_key():
    """API key is read dynamically from the GROQ_API_KEY environment variable."""
    return os.environ.get("GROQ_API_KEY", "").strip()


def groq_enabled():
    return bool(groq_api_key())


def _default_model():
    return config.get("groq", "model", default="llama-3.1-8b-instant")


def _call_ollama(method="POST", path="", body=None, stream=False):
    host = config.get("llm", "ollama_host")
    url = f"{host}/api/{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        if stream:
            # Keep the response open so the caller can stream it line-by-line.
            return urllib.request.urlopen(req, timeout=120)
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.read().decode()}"}
    except Exception as e:
        return {"error": str(e)}


def _call_groq(body, stream=False):
    """POST to the Groq Cloud API (OpenAI-compatible)."""
    url = f"{config.get('groq', 'base_url', default='https://api.groq.com/openai/v1')}/chat/completions"
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {groq_api_key()}")
    try:
        if stream:
            # Keep the response open so the caller can stream it line-by-line.
            return urllib.request.urlopen(req, timeout=120)
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.read().decode()}"}
    except Exception as e:
        return {"error": str(e)}


def _groq_to_ollama_style(groq_resp):
    """Normalize a Groq (OpenAI-format) response to the Ollama shape callers expect.

    Ollama shape: {"message": {"role": "assistant", "content": "...", "tool_calls": [...]}}
    Groq shape:   {"choices": [{"message": {"role": "assistant", "content": "...", "tool_calls": [...]}}]}
    """
    if "error" in groq_resp:
        return groq_resp
    try:
        msg = groq_resp["choices"][0]["message"]
    except (KeyError, IndexError, TypeError):
        return {"error": "Unexpected Groq response: no choices"}
    out = {
        "message": {
            "role": msg.get("role", "assistant"),
            "content": msg.get("content") or "",
        }
    }
    if msg.get("tool_calls"):
        out["message"]["tool_calls"] = msg["tool_calls"]
    return out


def _groq_stream(resp):
    """Yield content deltas from a Groq streaming response."""
    for line in resp:
        if not line:
            continue
        try:
            chunk = json.loads(line)
        except json.JSONDecodeError:
            continue
        try:
            delta = chunk["choices"][0]["delta"].get("content") or ""
        except (KeyError, IndexError, TypeError):
            delta = ""
        if delta:
            yield delta
        if chunk.get("choices") and chunk["choices"][0].get("finish_reason"):
            return


def list_models():
    """List available models (Groq when enabled, else Ollama)."""
    if groq_enabled():
        url = f"{config.get('groq', 'base_url', default='https://api.groq.com/openai/v1')}/models"
        req = urllib.request.Request(url, method="GET")
        req.add_header("Authorization", f"Bearer {groq_api_key()}")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
            return [m["id"] for m in data.get("data", [])]
        except Exception:
            return []
    result = _call_ollama("GET", "tags")
    if "error" in result:
        return []
    return [m["name"] for m in result.get("models", [])]


def pull_model(name):
    """Pull a model (Ollama only — Groq models are hosted, nothing to pull)."""
    if groq_enabled():
        return {"message": f"Groq models are hosted remotely; '{name}' needs no pull."}
    return _call_ollama(body={"name": name}, path="pull")


def is_running():
    """Check if the active provider is reachable (Groq or Ollama)."""
    if groq_enabled():
        try:
            url = f"{config.get('groq', 'base_url', default='https://api.groq.com/openai/v1')}/models"
            req = urllib.request.Request(url, method="GET")
            req.add_header("Authorization", f"Bearer {groq_api_key()}")
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status == 200
        except Exception:
            return False
    try:
        _call_ollama("GET", "")
        return True
    except Exception:
        return False


def _chat_stream(body):
    """Stream chat response, yielding content chunks."""
    if groq_enabled():
        body["stream"] = True
        resp = _call_groq(body, stream=True)
        if not hasattr(resp, "read"):
            return
        for delta in _groq_stream(resp):
            yield delta
        return
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


def chat(messages, model=None, stream=False, tools=None, max_tokens=None):
    """Chat completion. Returns an Ollama-style dict, or yields deltas if stream.

    tools: optional list of OpenAI-format tool definitions. Groq passes them
    through so tool-calling responses (message.tool_calls) flow back to the
    caller unchanged.
    """
    provider = "groq" if groq_enabled() else "ollama"
    model = model or (_default_model() if provider == "groq" else config.get("llm", "model"))
    max_tokens = max_tokens or config.get("llm", "max_tokens", default=4096)

    if provider == "groq":
        body = {
            "model": model,
            "messages": messages,
            "temperature": config.get("llm", "temperature", default=0.7),
            "max_tokens": max_tokens,
        }
        if tools:
            body["tools"] = tools
        if stream:
            body["stream"] = True
            resp = _call_groq(body, stream=True)
            if not hasattr(resp, "read"):
                return None
            return _groq_stream(resp)
        raw = _call_groq(body)
        return _groq_to_ollama_style(raw)

    # Ollama path
    body = {
        "model": model,
        "messages": messages,
        "stream": stream,
        "options": {
            "temperature": config.get("llm", "temperature", default=0.7),
            "num_predict": max_tokens,
        },
    }
    if tools:
        body["tools"] = tools
    if stream:
        return _chat_stream(body)
    return _call_ollama(body=body, path="chat")


def generate(prompt, system=None, model=None, stream=False, max_tokens=None):
    """Simple text generation."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    if stream:
        return chat(messages, model=model, stream=True, max_tokens=max_tokens)
    return chat(messages, model=model, max_tokens=max_tokens)


def embed(text, model=None):
    """Embeddings (Ollama only — Groq exposes no compatible embedding endpoint)."""
    if groq_enabled():
        return None
    result = _call_ollama(body={"model": model or config.get("llm", "model"), "prompt": text}, path="embeddings")
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
