#!/usr/bin/env python3
"""REST API server - standalone FastAPI server for remote access.

Merged from OpenHermes server mode.
"""
import json
import os
import sys
import time
import threading

# Add project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn

from core.config import config
from core.engine import engine
from core.llm import is_running, list_models, chat
from memory.store import memory
from core.self_improve import health

app = FastAPI(title="AI Agent Beast API")


@app.get("/")
def root():
    return {
        "name": "AI Agent Beast",
        "version": "2.0",
        "status": "running" if engine.running else "stopped",
        "docs": "/docs",
    }


@app.get("/v1/status")
def v1_status():
    return engine.status()


@app.post("/v1/chat")
async def v1_chat(request: Request):
    data = await request.json()
    message = data.get("message", "")
    system = data.get("system",
                       "You are a powerful local AI agent. Respond helpfully.")

    if not message:
        return {"error": "No message"}

    # Process through engine for action execution
    response = engine.process_text(message)

    return {
        "response": response,
        "timestamp": time.time(),
    }


@app.post("/v1/chat/completions")  # OpenAI-compatible endpoint
async def v1_chat_completions(request: Request):
    data = await request.json()
    messages = data.get("messages", [])
    stream = data.get("stream", False)

    if not messages:
        return {"error": "No messages"}

    # Get last user message
    last_msg = messages[-1]["content"] if messages else ""

    # Process
    response = engine.process_text(last_msg)

    return {
        "id": "chatcmpl-" + str(int(time.time())),
        "object": "chat.completion",
        "created": int(time.time()),
        "model": "agent-beast",
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": response,
            },
            "finish_reason": "stop",
        }],
    }


@app.get("/v1/models")
def v1_models():
    return {
        "object": "list",
        "data": [
            {"id": "agent-beast", "object": "model",
             "created": int(time.time()),
             "owned_by": "local"},
        ]
    }


@app.get("/v1/health")
def v1_health():
    return health.json_report()


@app.get("/v1/tools")
def v1_tools():
    from modules.tool_registry import registry
    return {"tools": registry.list_tools()}


@app.post("/v1/tool/{tool_name}")
async def v1_call_tool(tool_name: str, request: Request):
    from modules.tool_registry import registry
    data = await request.json() if request.headers.get("content-type") else {}
    result = registry.call(tool_name, **(data if isinstance(data, dict) else {}))
    return result


@app.post("/v1/execute")
async def v1_execute(request: Request):
    """Execute arbitrary action by name."""
    data = await request.json()
    action = data.get("action", "")
    params = data.get("params", {})
    if not action:
        return {"error": "No action specified"}
    result = engine.actions.call(action, **params)
    return result


@app.get("/v1/memory")
def v1_memory(limit: int = 50):
    return {"messages": memory.get_history(limit=limit)}


@app.post("/v1/memory")
async def v1_memory_add(request: Request):
    data = await request.json()
    key = data.get("key", "")
    value = data.get("value", "")
    category = data.get("category", "general")
    if key and value:
        memory.remember(key, value, category)
        return {"success": True}
    return {"error": "Key and value required"}


def start_api_server(host="0.0.0.0", port=8000):
    """Start the REST API server."""
    engine.start()
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    engine.start()
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
