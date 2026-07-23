"""Web UI - FastAPI dashboard with merged REST API + WebSocket."""
import base64
import json
import os
import threading
import time
import subprocess

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from core.config import config
from core.engine import engine
from core.llm import is_running, list_models, pull_model, chat
from memory.store import memory
from modules.automation import automation
from modules.android import android

# Merged tool modules
from core.self_improve import health, healer, improver, profile_manager
from modules.self_developer import (
    build_from_prompt, generate_module_from_prompt,
    create_git_commit, create_github_pr,
    auto_register_module, list_generated_modules, analyze_code_quality
)
from modules.tool_registry import registry
from modules.web_tools import web_search, web_scrape, web_fetch_json, web_search_news
from modules.file_tools import file_read, file_write, file_edit, file_list
from modules.code_tools import run_python, run_shell

# Utility tools
from modules.utility_tools import (
    weather_get, weather_detailed, calculate,
    system_info_str as sys_info_str, system_info as sys_info_dict,
    process_list, process_kill, network_info, network_speed_test,
    random_password, random_number, random_uuid,
    translate_text, note_add, note_get, note_list,
    qr_generate, url_shorten, text_count, encode_base64
)

# ===========================================================================
# Access Control
# ===========================================================================
import secrets
import hashlib
from datetime import datetime, timedelta

# In-memory session store
_sessions = {}  # token -> {username, role, expires_at}

def _generate_token():
    """Generate a secure random token."""
    return secrets.token_urlsafe(32)

def create_session(username, role="user", expire_hours=24):
    """Create a new session token."""
    token = _generate_token()
    expires = (datetime.utcnow() + timedelta(hours=expire_hours)).isoformat()
    _sessions[token] = {"username": username, "role": role, "expires": expires}
    return token

def validate_session(token):
    """Validate a session token. Returns session dict or None."""
    if not token or token not in _sessions:
        return None
    session = _sessions[token]
    expires = datetime.fromisoformat(session["expires"])
    if datetime.utcnow() > expires:
        del _sessions[token]
        return None
    return session

def require_auth(request):
    """Check Authorization header or query param for token."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
    else:
        token = request.query_params.get("token", "")
    return validate_session(token)

def admin_required(session):
    """Check if session has admin role."""
    return session and session.get("role") == "admin"

app = FastAPI(title="AI Agent Beast - Free & Unlimited")


# ===========================================================================
# Auth Middleware
# ===========================================================================

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """Protect all /api/ routes except /api/auth/*."""
    path = request.url.path
    if path.startswith("/api/") and not path.startswith("/api/auth/"):
        session = require_auth(request)
        if not session:
            return JSONResponse(
                {"success": False, "error": "Authentication required"},
                status_code=401
            )
    response = await call_next(request)
    return response


# ===========================================================================
# AI Nexus Dashboard — base44 × PocketStrike inspired
# ===========================================================================

DASHBOARD_HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI Nexus — Agent Beast</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
  /* ===== RESET & VARIABLES ===== */
  *, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }

  :root {
    --bg: #07070f;
    --bg2: #0d0d24;
    --surface: rgba(255,255,255,0.03);
    --surface-hover: rgba(255,255,255,0.07);
    --border: rgba(255,255,255,0.06);
    --border-glow: rgba(108,92,231,0.3);
    --text: #ececf5;
    --text2: #8888aa;
    --text3: #666688;
    --accent1: #7c5cfc;
    --accent2: #00d4c8;
    --accent3: #f472b6;
    --gradient: linear-gradient(135deg, #7c5cfc, #00d4c8);
    --gradient2: linear-gradient(135deg, #7c5cfc, #f472b6);
    --green: #00e676;
    --red: #ff5252;
    --orange: #ffab40;
    --yellow: #ffd740;
    --radius: 14px;
    --radius-sm: 10px;
    --shadow: 0 8px 40px rgba(0,0,0,0.5);
    --sidebar-w: 68px;
    --sidebar-expanded: 200px;
    --topbar-h: 56px;
  }

  html { scroll-behavior: smooth; }
  body {
    font-family: 'Inter', -apple-system, sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
    overflow: hidden;
    height: 100vh;
  }

  /* ===== PARTICLE CANVAS ===== */
  #particleCanvas {
    position: fixed; top: 0; left: 0; width: 100%; height: 100%;
    z-index: 0; pointer-events: none;
  }

  /* ===== SCROLLBAR ===== */
  ::-webkit-scrollbar { width: 4px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: var(--accent1); border-radius: 4px; }

  /* ===== LOGIN OVERLAY ===== */
  #loginOverlay {
    position: fixed; inset: 0; z-index: 9999;
    display: none; align-items: center; justify-content: center;
    background: rgba(7,7,15,0.85);
    backdrop-filter: blur(20px);
    animation: fadeIn 0.5s ease;
  }
  #loginOverlay.active { display: flex; }

  .login-card {
    position: relative; width: 400px; max-width: 90vw;
    padding: 48px 36px 36px;
    background: rgba(13,13,36,0.9);
    border: 1px solid var(--border);
    border-radius: 20px;
    overflow: hidden;
    animation: floatIn 0.6s cubic-bezier(0.16, 1, 0.3, 1);
    box-shadow: 0 0 80px rgba(124,92,252,0.08);
  }
  .login-card::before {
    content: ''; position: absolute; top: -2px; left: -2px;
    right: -2px; height: 3px;
    background: linear-gradient(90deg, transparent, var(--accent1), var(--accent2), transparent);
    background-size: 200% 100%;
    animation: shimmer 3s ease-in-out infinite;
  }
  @keyframes shimmer {
    0% { background-position: 200% 0; }
    100% { background-position: -200% 0; }
  }

  .login-logo {
    text-align: center; margin-bottom: 8px;
    font-size: 48px; font-weight: 800;
    background: var(--gradient); -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    letter-spacing: -1px;
  }
  .login-sub {
    text-align: center; color: var(--text2); font-size: 13px;
    margin-bottom: 32px; font-weight: 500;
  }
  .login-card h2 {
    font-size: 22px; font-weight: 700; margin-bottom: 6px;
  }
  .login-card p {
    color: var(--text2); font-size: 13px; margin-bottom: 24px;
  }
  .login-card input {
    width: 100%; padding: 14px 16px; margin-bottom: 12px;
    background: rgba(255,255,255,0.04);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    color: var(--text); font-size: 14px; font-family: inherit;
    transition: border-color 0.3s, box-shadow 0.3s;
    outline: none;
  }
  .login-card input:focus {
    border-color: var(--accent1);
    box-shadow: 0 0 20px rgba(124,92,252,0.12);
  }
  .login-card .btn {
    width: 100%; padding: 14px;
    background: var(--gradient); border: none;
    border-radius: var(--radius-sm); color: #fff;
    font-size: 15px; font-weight: 600; cursor: pointer;
    font-family: inherit; transition: transform 0.2s, box-shadow 0.3s;
    margin-top: 4px;
  }
  .login-card .btn:hover {
    transform: translateY(-1px);
    box-shadow: 0 8px 30px rgba(124,92,252,0.3);
  }
  .login-error { color: var(--red); font-size: 12px; margin-top: 8px; text-align: center; }

  /* ===== APP LAYOUT ===== */
  #app {
    display: none; height: 100vh;
    position: relative; z-index: 1;
  }
  #app.active { display: flex; }

  /* ===== SIDEBAR ===== */
  #sidebar {
    width: var(--sidebar-w); min-width: var(--sidebar-w);
    height: 100vh; background: rgba(13,13,36,0.6);
    backdrop-filter: blur(24px);
    border-right: 1px solid var(--border);
    display: flex; flex-direction: column;
    align-items: center; padding: 12px 0;
    transition: width 0.3s ease;
    overflow: hidden; z-index: 10;
  }
  #sidebar:hover { width: var(--sidebar-expanded); }
  #sidebar .logo {
    font-size: 22px; font-weight: 800; margin-bottom: 24px;
    width: var(--sidebar-w); text-align: center; flex-shrink: 0;
    background: var(--gradient); -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }
  .nav-items { display: flex; flex-direction: column; gap: 2px; flex: 1; width: 100%; padding: 0 8px; }
  .nav-item {
    display: flex; align-items: center; gap: 12px; padding: 10px 12px;
    border: none; background: transparent; color: var(--text2);
    border-radius: var(--radius-sm); cursor: pointer;
    font-size: 13px; font-weight: 500; font-family: inherit;
    transition: all 0.2s; white-space: nowrap; width: 100%;
  }
  .nav-item:hover { background: var(--surface-hover); color: var(--text); }
  .nav-item.active {
    background: rgba(124,92,252,0.12); color: var(--accent1);
    box-shadow: inset 3px 0 0 var(--accent1);
  }
  .nav-item .nav-icon { font-size: 18px; width: 24px; text-align: center; flex-shrink: 0; }
  .nav-item .nav-label { opacity: 0; transition: opacity 0.2s; }
  #sidebar:hover .nav-item .nav-label { opacity: 1; }

  .nav-bottom { margin-top: auto; width: 100%; padding: 0 8px; }

  /* ===== MAIN AREA ===== */
  #main { flex: 1; display: flex; flex-direction: column; overflow: hidden; }

  /* ===== TOP BAR ===== */
  #topbar {
    height: var(--topbar-h); min-height: var(--topbar-h);
    display: flex; align-items: center; gap: 16px;
    padding: 0 24px;
    background: rgba(13,13,36,0.4);
    backdrop-filter: blur(16px);
    border-bottom: 1px solid var(--border);
  }
  .tb-left { display: flex; align-items: center; gap: 12px; flex: 1; }
  .tb-right { display: flex; align-items: center; gap: 12px; }
  .status-dot {
    width: 8px; height: 8px; border-radius: 50%; display: inline-block;
    transition: all 0.5s;
  }
  .status-dot.online { background: var(--green); box-shadow: 0 0 12px var(--green); }
  .status-dot.offline { background: var(--red); box-shadow: 0 0 12px var(--red); }
  .tb-status { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--text2); }
  .tb-badge {
    padding: 3px 10px; border-radius: 12px; font-size: 11px; font-weight: 600;
    background: rgba(124,92,252,0.12); color: var(--accent1);
    border: 1px solid rgba(124,92,252,0.15);
  }
  .tb-user {
    display: none; align-items: center; gap: 8px; padding: 4px 12px 4px 4px;
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 20px; font-size: 12px; font-weight: 500;
  }
  .tb-user.active { display: flex; }
  .tb-avatar {
    width: 28px; height: 28px; border-radius: 50%;
    background: var(--gradient); display: flex; align-items: center; justify-content: center;
    font-size: 12px; font-weight: 700; color: #fff;
  }
  .btn-logout {
    padding: 6px 14px; border: 1px solid var(--border); background: transparent;
    color: var(--text2); border-radius: 8px; cursor: pointer; font-size: 12px;
    font-family: inherit; transition: all 0.2s;
  }
  .btn-logout:hover { background: rgba(255,82,82,0.1); color: var(--red); border-color: rgba(255,82,82,0.2); }

  /* ===== CONTENT ===== */
  #content {
    flex: 1; overflow-y: auto; padding: 20px 24px;
  }

  /* ===== CARDS ===== */
  .card {
    background: var(--surface);
    backdrop-filter: blur(12px);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 20px 24px;
    transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
    transform: perspective(1000px) rotateX(0deg) rotateY(0deg);
  }
  .card:hover {
    border-color: rgba(124,92,252,0.15);
    box-shadow: 0 8px 40px rgba(0,0,0,0.3);
  }
  .card-3d {
    transform-style: preserve-3d;
    transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.3s;
  }
  .card-title {
    font-size: 15px; font-weight: 700; margin-bottom: 14px;
    display: flex; align-items: center; gap: 8px;
  }
  .card-title .icon { font-size: 18px; }

  /* ===== TABS ===== */
  .tab-content { display: none; }
  .tab-content.active { display: block; animation: fadeSlide 0.35s ease; }

  @keyframes fadeSlide {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
  }
  @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
  @keyframes floatIn {
    from { opacity: 0; transform: translateY(30px) scale(0.96); }
    to { opacity: 1; transform: translateY(0) scale(1); }
  }

  /* ===== GRID ===== */
  .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
  .grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 14px; }
  .grid-4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }
  @media (max-width: 900px) { .grid-2, .grid-3, .grid-4 { grid-template-columns: 1fr; } }
  @media (min-width: 901px) and (max-width: 1200px) { .grid-3, .grid-4 { grid-template-columns: 1fr 1fr; } }

  /* ===== INPUTS ===== */
  input, textarea, select {
    width: 100%; padding: 10px 14px; margin-bottom: 8px;
    background: rgba(255,255,255,0.04);
    border: 1px solid var(--border); border-radius: var(--radius-sm);
    color: var(--text); font-size: 13px; font-family: inherit;
    transition: border-color 0.2s, box-shadow 0.2s; outline: none;
  }
  input:focus, textarea:focus {
    border-color: var(--accent1);
    box-shadow: 0 0 16px rgba(124,92,252,0.1);
  }
  textarea { resize: vertical; min-height: 60px; }
  select { cursor: pointer; }

  /* ===== BUTTONS ===== */
  .btn {
    padding: 9px 18px; border: none; background: var(--gradient);
    color: #fff; border-radius: var(--radius-sm); font-size: 13px;
    font-weight: 600; cursor: pointer; font-family: inherit;
    transition: all 0.25s; display: inline-flex; align-items: center; gap: 6px;
  }
  .btn:hover { transform: translateY(-1px); box-shadow: 0 6px 24px rgba(124,92,252,0.25); }
  .btn:active { transform: translateY(0); }
  .btn-sm { padding: 6px 12px; font-size: 12px; }
  .btn-outline {
    background: transparent; border: 1px solid var(--border); color: var(--text2);
  }
  .btn-outline:hover { background: var(--surface-hover); color: var(--text); border-color: rgba(255,255,255,0.15); box-shadow: none; }
  .btn-success { background: linear-gradient(135deg, #00c853, #00e676); }
  .btn-danger { background: linear-gradient(135deg, #d50000, #ff5252); }
  .btn-warning { background: linear-gradient(135deg, #ff6d00, #ffab40); }
  .btn-group { display: flex; gap: 8px; flex-wrap: wrap; }

  /* ===== CHAT ===== */
  .chat-messages {
    height: 350px; overflow-y: auto; padding: 12px;
    background: rgba(0,0,0,0.2); border-radius: var(--radius-sm);
    margin-bottom: 12px; display: flex; flex-direction: column; gap: 8px;
  }
  .msg {
    padding: 10px 14px; border-radius: 12px; max-width: 85%;
    font-size: 13px; line-height: 1.5; animation: fadeIn 0.3s;
  }
  .msg.user { background: rgba(124,92,252,0.15); align-self: flex-end; border: 1px solid rgba(124,92,252,0.15); }
  .msg.assistant { background: rgba(255,255,255,0.05); align-self: flex-start; border: 1px solid var(--border); }
  .msg.system { background: rgba(0,212,200,0.08); align-self: center; text-align: center; font-size: 12px; color: var(--text2); border: 1px solid rgba(0,212,200,0.1); }
  .msg-label { font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; opacity: 0.6; }
  .chat-input-row { display: flex; gap: 8px; }
  .chat-input-row input { flex: 1; margin-bottom: 0; }

  /* ===== TOOLS (base44 style) ===== */
  .tool-grid {
    display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: 12px; margin-top: 12px;
  }
  .tool-card {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: var(--radius-sm); padding: 16px;
    cursor: pointer; transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
    transform: perspective(800px) rotateX(0deg);
  }
  .tool-card:hover {
    background: var(--surface-hover); border-color: rgba(124,92,252,0.2);
    transform: perspective(800px) rotateX(2deg) translateY(-2px);
    box-shadow: 0 8px 30px rgba(0,0,0,0.3);
  }
  .tool-card .t-icon { font-size: 24px; margin-bottom: 8px; }
  .tool-card .t-name { font-size: 13px; font-weight: 600; margin-bottom: 4px; }
  .tool-card .t-desc { font-size: 11px; color: var(--text3); line-height: 1.4; }
  .tool-card .t-cat {
    display: inline-block; margin-top: 8px; padding: 2px 8px;
    border-radius: 6px; font-size: 10px; font-weight: 600;
    background: rgba(124,92,252,0.1); color: var(--accent1);
  }
  .tool-search {
    position: relative; margin-bottom: 12px;
  }
  .tool-search input { padding-left: 36px; }
  .tool-search .search-icon {
    position: absolute; left: 12px; top: 50%; transform: translateY(-60%);
    color: var(--text3); font-size: 14px; pointer-events: none;
  }

  /* ===== ANDROID / POCKETSTRIKE PANEL ===== */
  .android-grid {
    display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
    gap: 10px; margin-bottom: 14px;
  }
  .android-btn {
    display: flex; flex-direction: column; align-items: center; gap: 6px;
    padding: 14px 8px; background: var(--surface);
    border: 1px solid var(--border); border-radius: var(--radius-sm);
    cursor: pointer; transition: all 0.25s; font-family: inherit;
    color: var(--text2); font-size: 11px;
  }
  .android-btn:hover {
    background: var(--surface-hover); border-color: var(--accent2);
    color: var(--text); transform: translateY(-2px);
    box-shadow: 0 4px 20px rgba(0,212,200,0.12);
  }
  .android-btn .a-icon { font-size: 22px; }
  .android-btn .a-label { font-weight: 500; }
  .android-terminal {
    background: rgba(0,0,0,0.4); border: 1px solid var(--border);
    border-radius: var(--radius-sm); padding: 12px;
    font-family: 'Courier New', monospace; font-size: 12px;
    min-height: 120px; max-height: 200px; overflow-y: auto;
    color: var(--accent2); line-height: 1.5;
  }
  .android-status {
    display: flex; align-items: center; gap: 8px; margin-bottom: 12px;
    padding: 8px 12px; background: var(--surface);
    border: 1px solid var(--border); border-radius: var(--radius-sm);
    font-size: 12px;
  }

  /* ===== STATS / QUICK STATS ===== */
  .stat-grid {
    display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    gap: 12px; margin-bottom: 16px;
  }
  .stat-card {
    padding: 16px 18px; background: var(--surface);
    border: 1px solid var(--border); border-radius: var(--radius-sm);
    transition: all 0.3s;
  }
  .stat-card:hover { border-color: rgba(124,92,252,0.15); }
  .stat-number { font-size: 24px; font-weight: 800; background: var(--gradient); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
  .stat-label { font-size: 11px; color: var(--text3); margin-top: 2px; font-weight: 500; }

  /* ===== OUTPUT ===== */
  .output {
    font-size: 13px; line-height: 1.5; color: var(--text2);
    white-space: pre-wrap; word-break: break-word;
  }

  /* ===== LOADING ===== */
  .loading { display: none; align-items: center; gap: 8px; padding: 8px 0; font-size: 12px; color: var(--text3); }
  .loading.active { display: flex; }
  .spinner {
    width: 16px; height: 16px; border: 2px solid var(--border);
    border-top: 2px solid var(--accent1); border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  /* ===== SECTION HEADER ===== */
  .section-title { font-size: 18px; font-weight: 700; margin-bottom: 4px; }
  .section-sub { font-size: 13px; color: var(--text3); margin-bottom: 16px; }

  /* ===== NOTES ===== */
  .note-item {
    padding: 8px 12px; background: var(--surface);
    border: 1px solid var(--border); border-radius: 8px;
    margin-bottom: 6px; cursor: pointer; font-size: 13px;
    transition: all 0.2s;
  }
  .note-item:hover { background: var(--surface-hover); border-color: var(--accent1); }

  /* ===== PROCESS LIST ===== */
  .proc-item { padding: 4px 0; font-size: 12px; color: var(--text2); border-bottom: 1px solid var(--border); }
  .proc-item:last-child { border: none; }

  /* ===== RESPONSIVE ===== */
  @media (max-width: 768px) {
    #sidebar { width: 56px; min-width: 56px; }
    #sidebar:hover { width: 56px; }
    .nav-item { padding: 8px; justify-content: center; }
    .nav-item .nav-label { display: none; }
    #sidebar:hover .nav-item .nav-label { display: none; }
    #content { padding: 12px; }
    #topbar { padding: 0 12px; gap: 8px; }
    .login-card { padding: 32px 20px; }
    .stat-grid { grid-template-columns: repeat(2, 1fr); }
    .tool-grid { grid-template-columns: 1fr; }
  }

  /* ===== GLOW EFFECTS ===== */
  .glow { position: relative; }
  .glow::after {
    content: ''; position: absolute; inset: -1px;
    border-radius: inherit; z-index: -1;
    background: var(--gradient); opacity: 0;
    filter: blur(16px); transition: opacity 0.3s;
  }
  .glow:hover::after { opacity: 0.3; }

  /* ===== TITLE BAR ===== */
  .welcome-section { margin-bottom: 20px; }
  .welcome-section h1 { font-size: 24px; font-weight: 800; margin-bottom: 4px; }
  .welcome-section p { color: var(--text2); font-size: 14px; }

  /* Dashboard home cards */
  .dash-card {
    position: relative; overflow: hidden;
  }
  .dash-card .dash-bg-icon {
    position: absolute; right: 12px; bottom: 12px;
    font-size: 48px; opacity: 0.06; pointer-events: none;
  }
</style>
</head>
<body>

<canvas id="particleCanvas"></canvas>

<!-- ===== LOGIN OVERLAY ===== -->
<div id="loginOverlay" class="active">
  <div class="login-card">
    <div class="login-logo">◆</div>
    <div class="login-sub">AI NEXUS</div>
    <h2>Welcome back</h2>
    <p>Sign in to access your agent dashboard</p>
    <input id="loginUser" placeholder="Username" autocomplete="username" spellcheck="false" autofocus>
    <input id="loginPass" type="password" placeholder="Password" autocomplete="current-password">
    <button class="btn" onclick="doLogin()">Sign In</button>
    <div class="login-error" id="loginError"></div>
  </div>
</div>

<!-- ===== APP ===== -->
<div id="app">
  <!-- SIDEBAR -->
  <aside id="sidebar">
    <div class="logo">◆</div>
    <div class="nav-items">
      <button class="nav-item active" data-tab="home"><span class="nav-icon">◈</span><span class="nav-label">Home</span></button>
      <button class="nav-item" data-tab="chat"><span class="nav-icon">💬</span><span class="nav-label">Chat</span></button>
      <button class="nav-item" data-tab="tools"><span class="nav-icon">⚡</span><span class="nav-label">Tools</span></button>
      <button class="nav-item" data-tab="android"><span class="nav-icon">📱</span><span class="nav-label">Android</span></button>
      <button class="nav-item" data-tab="weather"><span class="nav-icon">🌤</span><span class="nav-label">Weather</span></button>
      <button class="nav-item" data-tab="utilities"><span class="nav-icon">🧰</span><span class="nav-label">Utilities</span></button>
      <button class="nav-item" data-tab="files"><span class="nav-icon">📁</span><span class="nav-label">Files</span></button>
      <button class="nav-item" data-tab="web"><span class="nav-icon">🌐</span><span class="nav-label">Web</span></button>
      <button class="nav-item" data-tab="notes"><span class="nav-icon">📝</span><span class="nav-label">Notes</span></button>
      <button class="nav-item" data-tab="system"><span class="nav-icon">⚙️</span><span class="nav-label">System</span></button>
      <button class="nav-item" data-tab="self-develop"><span class="nav-icon">🧠</span><span class="nav-label">Develop</span></button>
    </div>
    <div class="nav-bottom">
      <button class="nav-item" onclick="doLogout()"><span class="nav-icon">🚪</span><span class="nav-label">Sign Out</span></button>
    </div>
  </aside>

  <!-- MAIN -->
  <div id="main">
    <!-- TOP BAR -->
    <header id="topbar">
      <div class="tb-left">
        <div class="tb-status">
          <span class="status-dot offline" id="statusDot"></span>
          <span id="statusText">Loading...</span>
        </div>
        <span class="tb-badge" id="toolsCount">-- tools</span>
        <span class="tb-badge" id="modelStatus">LLM: --</span>
      </div>
      <div class="tb-right">
        <div class="tb-user" id="tbUser">
          <div class="tb-avatar" id="userAvatar">A</div>
          <span id="userNameDisplay">user</span>
          <span style="color:var(--text3);font-size:11px" id="userRoleDisplay"></span>
        </div>
      </div>
    </header>

    <!-- CONTENT -->
    <div id="content">

      <!-- ===== HOME ===== -->
      <div class="tab-content active" id="tab-home">
        <div class="welcome-section">
          <h1>AI Nexus<span style="color:var(--accent2)">.</span></h1>
          <p>Your autonomous agent command center</p>
        </div>
        <div class="stat-grid">
          <div class="stat-card"><div class="stat-number" id="homeToolsCount">--</div><div class="stat-label">Tools Loaded</div></div>
          <div class="stat-card"><div class="stat-number" id="homeUptime">--</div><div class="stat-label">Uptime</div></div>
          <div class="stat-card"><div class="stat-number" id="homeMemory">--</div><div class="stat-label">Memory Items</div></div>
          <div class="stat-card"><div class="stat-number" id="homeAndroid">--</div><div class="stat-label">Android Status</div></div>
        </div>
        <div class="grid-2">
          <div class="card dash-card">
            <div class="card-title"><span class="icon">⚡</span> Quick Actions</div>
            <div class="btn-group">
              <button class="btn btn-sm" onclick="switchTab('chat')">💬 Open Chat</button>
              <button class="btn btn-sm btn-outline" onclick="switchTab('tools')">🔧 Browse Tools</button>
              <button class="btn btn-sm btn-outline" onclick="switchTab('android')">📱 Android</button>
              <button class="btn btn-sm btn-outline" onclick="healthReport()">🩺 Health Check</button>
            </div>
          </div>
          <div class="card dash-card">
            <div class="card-title"><span class="icon">🔄</span> System Status</div>
            <div id="homeSysInfo" style="font-size:13px;color:var(--text2);line-height:1.8">
              Loading system info...
            </div>
          </div>
        </div>
        <div class="card" style="margin-top:14px">
          <div class="card-title"><span class="icon">💡</span> Quick Command</div>
          <div style="display:flex;gap:8px">
            <input id="quickCmd" placeholder="Type a command..." onkeydown="if(event.key==='Enter') runQuickCmd()">
            <button class="btn btn-sm" onclick="runQuickCmd()">Run</button>
          </div>
          <div class="output" id="quickCmdOutput" style="margin-top:8px"></div>
        </div>
      </div>

      <!-- ===== CHAT ===== -->
      <div class="tab-content" id="tab-chat">
        <div class="card">
          <div class="card-title"><span class="icon">💬</span> AI Chat</div>
          <div class="chat-messages" id="chatMessages">
            <div class="msg system">Welcome! Send a message to start chatting.</div>
          </div>
          <div class="chat-input-row">
            <input id="chatInput" placeholder="Type your message..." onkeydown="if(event.key==='Enter') sendChat()">
            <button class="btn" onclick="sendChat()">Send</button>
            <button class="btn btn-outline" onclick="clearChat()">Clear</button>
          </div>
        </div>
      </div>

      <!-- ===== TOOLS (base44.com-style) ===== -->
      <div class="tab-content" id="tab-tools">
        <div class="welcome-section">
          <h1>Tools <span style="font-size:16px;color:var(--text2);font-weight:400">/ command palette</span></h1>
          <p>All registered agent tools — search, browse, and execute</p>
        </div>
        <div class="card">
          <div class="tool-search">
            <span class="search-icon">🔍</span>
            <input id="toolSearch" placeholder="Search tools by name or description..." oninput="renderTools()">
          </div>
          <div class="loading" id="toolsLoading"><div class="spinner"></div>Loading tools...</div>
          <div class="tool-grid" id="toolsContainer"></div>
        </div>
      </div>

      <!-- ===== ANDROID (PocketStrike-style) ===== -->
      <div class="tab-content" id="tab-android">
        <div class="welcome-section">
          <h1>📱 Android Control</h1>
          <p>PocketStrike-style device automation & management</p>
        </div>
        <div class="android-status" id="androidStatusBar">
          <span class="status-dot offline" id="androidDot"></span>
          <span id="androidStatusText">Checking ADB connection...</span>
        </div>
        <div class="android-grid" id="androidQuickActions">
          <button class="android-btn" onclick="androidShell('input tap 500 1000')"><span class="a-icon">👆</span><span class="a-label">Tap</span></button>
          <button class="android-btn" onclick="androidShell('input swipe 500 1000 500 500')"><span class="a-icon">⬆️</span><span class="a-label">Swipe Up</span></button>
          <button class="android-btn" onclick="androidShell('input keyevent 3')"><span class="a-icon">🏠</span><span class="a-label">Home</span></button>
          <button class="android-btn" onclick="androidShell('input keyevent 4')"><span class="a-icon">◀️</span><span class="a-label">Back</span></button>
          <button class="android-btn" onclick="androidShell('input keyevent 187')"><span class="a-icon">📋</span><span class="a-label">Recent</span></button>
          <button class="android-btn" onclick="androidShell('input keyevent 26')"><span class="a-icon">⏻</span><span class="a-label">Power</span></button>
          <button class="android-btn" onclick="androidShell('input keyevent 24')"><span class="a-icon">🔊</span><span class="a-label">Vol Up</span></button>
          <button class="android-btn" onclick="androidShell('input keyevent 25')"><span class="a-icon">🔉</span><span class="a-label">Vol Down</span></button>
          <button class="android-btn" onclick="androidShell('input keyevent 5')"><span class="a-icon">📞</span><span class="a-label">Call</span></button>
          <button class="android-btn" onclick="androidShell('screencap /sdcard/screen.png')"><span class="a-icon">📸</span><span class="a-label">Screenshot</span></button>
          <button class="android-btn" onclick="androidShell('dumpsys battery')"><span class="a-icon">🔋</span><span class="a-label">Battery</span></button>
          <button class="android-btn" onclick="androidShell('wm size')"><span class="a-icon">📐</span><span class="a-label">Display</span></button>
        </div>
        <div class="card">
          <div class="card-title"><span class="icon">⌨️</span> ADB Shell</div>
          <div style="display:flex;gap:8px">
            <input id="androidCmd" placeholder="adb shell command..." onkeydown="if(event.key==='Enter') androidShell(document.getElementById('androidCmd').value)">
            <button class="btn btn-sm" onclick="androidShell(document.getElementById('androidCmd').value)">Run</button>
            <button class="btn btn-sm btn-outline" onclick="document.getElementById('androidTerminal').textContent = 'Terminal cleared.'">Clear</button>
          </div>
          <div class="android-terminal" id="androidTerminal">Ready. Connect a device to begin.</div>
        </div>
      </div>

      <!-- ===== WEATHER ===== -->
      <div class="tab-content" id="tab-weather">
        <div class="card">
          <div class="card-title"><span class="icon">🌤️</span> Weather Forecast</div>
          <div style="display:flex;gap:8px;margin-bottom:10px">
            <input id="weatherCity" placeholder="City name (or 'auto')" value="auto">
            <button class="btn btn-sm" onclick="getWeather()">Get Weather</button>
            <button class="btn btn-sm btn-outline" onclick="getWeatherDetailed()">3-Day Forecast</button>
          </div>
          <div class="loading" id="weatherLoading"><div class="spinner"></div></div>
          <div class="output" id="weatherOutput">Enter a city to see weather.</div>
        </div>
      </div>

      <!-- ===== UTILITIES ===== -->
      <div class="tab-content" id="tab-utilities">
        <div class="grid-2">
          <div class="card">
            <div class="card-title"><span class="icon">🧮</span> Calculator</div>
            <input id="calcExpr" placeholder="e.g. 2 + 2 * 5">
            <button class="btn btn-sm" onclick="calcExec()">Calculate</button>
            <div class="output" id="calcOutput" style="margin-top:8px"></div>
          </div>
          <div class="card">
            <div class="card-title"><span class="icon">🔑</span> Password Generator</div>
            <div style="display:flex;gap:8px;align-items:center">
              <input id="pwLength" type="number" value="16" min="4" max="64" style="width:80px;flex-shrink:0">
              <button class="btn btn-sm" onclick="genPassword()">Generate</button>
            </div>
            <div class="output" id="pwOutput" style="margin-top:8px"></div>
          </div>
          <div class="card">
            <div class="card-title"><span class="icon">📱</span> QR Code</div>
            <input id="qrData" placeholder="Text or URL to encode">
            <button class="btn btn-sm" onclick="genQR()">Generate QR</button>
            <div id="qrOutput" style="margin-top:8px"></div>
          </div>
          <div class="card">
            <div class="card-title"><span class="icon">🌍</span> Translator</div>
            <input id="translateText" placeholder="Text to translate">
            <div style="display:flex;gap:8px">
              <input id="translateTarget" placeholder="Target language (e.g. hi)" value="hi" style="width:120px">
              <input id="translateSource" placeholder="Source (auto)" value="auto" style="width:120px">
            </div>
            <button class="btn btn-sm" onclick="doTranslate()">Translate</button>
            <div class="output" id="translateOutput" style="margin-top:8px"></div>
          </div>
          <div class="card">
            <div class="card-title"><span class="icon">🔐</span> Base64</div>
            <input id="b64Text" placeholder="Text to encode/decode">
            <div class="btn-group">
              <button class="btn btn-sm" onclick="doBase64(false)">Encode</button>
              <button class="btn btn-sm btn-outline" onclick="doBase64(true)">Decode</button>
            </div>
            <div class="output" id="b64Output" style="margin-top:8px"></div>
          </div>
          <div class="card">
            <div class="card-title"><span class="icon">📊</span> Text Analyzer</div>
            <textarea id="textCountInput" placeholder="Paste text to analyze..." style="min-height:60px"></textarea>
            <button class="btn btn-sm" onclick="doTextCount()">Analyze</button>
            <div class="output" id="textCountOutput" style="margin-top:8px"></div>
          </div>
        </div>
      </div>

      <!-- ===== FILES ===== -->
      <div class="tab-content" id="tab-files">
        <div class="grid-2">
          <div class="card">
            <div class="card-title"><span class="icon">📂</span> File Browser</div>
            <div style="display:flex;gap:8px">
              <input id="filePath" placeholder="Directory path" value=".">
              <button class="btn btn-sm" onclick="listFiles()">List</button>
            </div>
            <div class="output" id="fileListOutput" style="max-height:300px"></div>
          </div>
          <div class="card">
            <div class="card-title"><span class="icon">📄</span> Read / Write</div>
            <input id="fileReadPath" placeholder="File path to read">
            <button class="btn btn-sm" onclick="readFile()">Read</button>
            <div style="margin-top:8px">
              <input id="fileWritePath" placeholder="File path to write">
              <textarea id="fileWriteContent" placeholder="Content to write..." style="min-height:60px"></textarea>
              <button class="btn btn-sm" onclick="writeFile()">Write</button>
            </div>
          </div>
        </div>
      </div>

      <!-- ===== WEB ===== -->
      <div class="tab-content" id="tab-web">
        <div class="grid-2">
          <div class="card">
            <div class="card-title"><span class="icon">🔍</span> Web Search</div>
            <input id="webQuery" placeholder="Search query">
            <button class="btn btn-sm" onclick="webSearch()">Search</button>
            <div class="output" id="webSearchOutput" style="max-height:300px"></div>
          </div>
          <div class="card">
            <div class="card-title"><span class="icon">🕸️</span> Web Scrape</div>
            <input id="scrapeUrl" placeholder="URL to scrape">
            <button class="btn btn-sm" onclick="webScrape()">Scrape</button>
            <div class="output" id="scrapeOutput" style="max-height:300px"></div>
          </div>
        </div>
      </div>

      <!-- ===== NOTES ===== -->
      <div class="tab-content" id="tab-notes">
        <div class="grid-2">
          <div class="card">
            <div class="card-title"><span class="icon">✏️</span> New Note</div>
            <input id="noteTitle" placeholder="Note title">
            <textarea id="noteContent" placeholder="Note content..." style="min-height:100px"></textarea>
            <button class="btn btn-sm" onclick="addNote()">Save Note</button>
            <div class="output" id="noteSaveOutput" style="margin-top:8px"></div>
          </div>
          <div class="card">
            <div class="card-title"><span class="icon">📋</span> Saved Notes</div>
            <div class="btn-group" style="margin-bottom:8px">
              <button class="btn btn-sm" onclick="listNotes()">Refresh</button>
              <input id="noteGetTitle" placeholder="Open note..." style="width:auto;flex:1">
              <button class="btn btn-sm btn-outline" onclick="getNote()">Open</button>
            </div>
            <div id="notesListContainer"></div>
            <div class="output" id="noteViewOutput" style="margin-top:8px"></div>
          </div>
        </div>
      </div>

      <!-- ===== SYSTEM ===== -->
      <div class="tab-content" id="tab-system">
        <div class="grid-2">
          <div class="card">
            <div class="card-title"><span class="icon">💻</span> System Info</div>
            <button class="btn btn-sm" onclick="getSysInfo()">Refresh</button>
            <div class="output" id="sysInfoOutput" style="margin-top:8px"></div>
          </div>
          <div class="card">
            <div class="card-title"><span class="icon">⚡</span> Network</div>
            <div class="btn-group">
              <button class="btn btn-sm" onclick="getNetwork()">Refresh</button>
              <button class="btn btn-sm btn-outline" onclick="speedTest()">Speed Test</button>
            </div>
            <div class="output" id="networkOutput" style="margin-top:8px"></div>
          </div>
        </div>
        <div class="card" style="margin-top:14px">
          <div class="card-title"><span class="icon">⚙️</span> Processes</div>
          <input id="procFilter" placeholder="Filter processes..." oninput="getProcesses()">
          <div class="loading" id="procLoading"><div class="spinner"></div></div>
          <div id="procContainer" style="max-height:300px;overflow-y:auto"></div>
        </div>
      </div>

      <!-- ===== SELF-DEVELOP ===== -->
      <div class="tab-content" id="tab-self-develop">
        <div class="card" style="margin-bottom:14px">
          <div class="card-title"><span class="icon">🧠</span> Describe What to Build</div>
          <textarea id="buildPrompt" placeholder="Describe the feature you want to build in natural language..." style="min-height:100px"></textarea>
          <div class="btn-group">
            <button class="btn btn-sm" onclick="generateCode()">⚡ Generate Code</button>
            <button class="btn btn-sm btn-success" onclick="buildFeature()">🚀 Full Build</button>
            <button class="btn btn-sm btn-outline" onclick="clearBuild()">Clear</button>
          </div>
          <div class="loading" id="buildLoading"><div class="spinner"></div>Building...</div>
        </div>
        <div class="grid-2">
          <div class="card">
            <div class="card-title"><span class="icon">📄</span> Generated Code</div>
            <div class="output" id="codePreview" style="max-height:400px;font-family:monospace;font-size:12px">No code generated yet.</div>
          </div>
          <div class="card">
            <div class="card-title"><span class="icon">🎯</span> Actions</div>
            <div style="font-size:12px;color:var(--text3);margin-bottom:8px">Module: <span id="currentModule" style="color:var(--accent1)">—</span></div>
            <div class="btn-group" style="margin-bottom:12px">
              <button class="btn btn-sm" onclick="registerModule()">📦 Register</button>
              <button class="btn btn-sm btn-outline" onclick="gitCommit()">📝 Commit</button>
              <button class="btn btn-sm btn-outline" onclick="githubPR()">🔀 PR</button>
              <button class="btn btn-sm btn-outline" onclick="checkCodeQuality()">🔍 Quality</button>
            </div>
            <input id="gitCommitMsg" placeholder="Commit message" style="margin-bottom:4px">
            <input id="prTitle" placeholder="PR title" style="margin-bottom:4px">
            <input id="registerModuleName" placeholder="Module name to register" style="margin-bottom:4px">
            <div class="output" id="actionOutput" style="max-height:200px">Ready.</div>
          </div>
        </div>
        <div class="card" style="margin-top:14px">
          <div class="card-title"><span class="icon">📂</span> Generated Modules</div>
          <div class="btn-group" style="margin-bottom:8px">
            <button class="btn btn-sm" onclick="listGenerated()">🔄 Refresh</button>
            <input id="qualityFilePath" placeholder="Module file path for quality check" style="flex:1">
            <button class="btn btn-sm btn-outline" onclick="checkCodeQuality()">Check</button>
          </div>
          <div class="output" id="generatedModulesOutput" style="max-height:150px">Click Refresh to see generated modules.</div>
        </div>
        <div class="grid-2" style="margin-top:14px">
          <div class="card">
            <div class="card-title"><span class="icon">👤</span> Profile: Abhinav</div>
            <div class="btn-group">
              <button class="btn btn-sm" onclick="loadProfile()">🔄 Load</button>
              <button class="btn btn-sm btn-outline" onclick="listProfiles()">📋 List</button>
            </div>
            <div class="output" id="profileOutput" style="max-height:200px">Click Load Profile to see details.</div>
          </div>
          <div class="card">
            <div class="card-title"><span class="icon">🩺</span> Health & Self-Repair</div>
            <div class="btn-group">
              <button class="btn btn-sm" onclick="healthReport()">📊 Health Report</button>
              <button class="btn btn-sm btn-success" onclick="selfHeal()">🔧 Self-Heal</button>
            </div>
            <div class="output" id="healthOutput" style="max-height:200px">Run a health check to see system status.</div>
          </div>
        </div>
      </div>

    </div><!-- /content -->
  </div><!-- /main -->
</div><!-- /app -->

<script>
// ===== PARTICLE SYSTEM (Pure Canvas - no CDN needed) =====
(function() {
  const canvas = document.getElementById('particleCanvas');
  const ctx = canvas.getContext('2d');
  let particles = [];
  let mouse = { x: -1000, y: -1000 };
  let W, H;

  function resize() {
    W = canvas.width = window.innerWidth;
    H = canvas.height = window.innerHeight;
  }
  window.addEventListener('resize', resize);
  resize();

  class Particle {
    constructor() { this.reset(); }
    reset() {
      this.x = Math.random() * W;
      this.y = Math.random() * H;
      this.vx = (Math.random() - 0.5) * 0.5;
      this.vy = (Math.random() - 0.5) * 0.5;
      this.r = Math.random() * 2 + 0.5;
      this.alpha = Math.random() * 0.5 + 0.2;
    }
    update() {
      this.x += this.vx;
      this.y += this.vy;
      if (this.x < 0 || this.x > W) this.vx *= -1;
      if (this.y < 0 || this.y > H) this.vy *= -1;
    }
    draw() {
      ctx.beginPath();
      ctx.arc(this.x, this.y, this.r, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(124, 92, 252, ${this.alpha})`;
      ctx.fill();
    }
  }

  const count = Math.min(80, Math.floor(W * H / 20000));
  for (let i = 0; i < count; i++) particles.push(new Particle());

  function drawLines() {
    for (let i = 0; i < particles.length; i++) {
      for (let j = i + 1; j < particles.length; j++) {
        const dx = particles[i].x - particles[j].x;
        const dy = particles[i].y - particles[j].y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 150) {
          ctx.beginPath();
          ctx.moveTo(particles[i].x, particles[i].y);
          ctx.lineTo(particles[j].x, particles[j].y);
          ctx.strokeStyle = `rgba(124, 92, 252, ${(1 - dist / 150) * 0.12})`;
          ctx.lineWidth = 0.5;
          ctx.stroke();
        }
      }
    }
  }

  function animate() {
    ctx.clearRect(0, 0, W, H);
    particles.forEach(p => { p.update(); p.draw(); });
    drawLines();
    // Mouse connection
    particles.forEach(p => {
      const dx = p.x - mouse.x;
      const dy = p.y - mouse.y;
      const dist = Math.sqrt(dx * dx + dy * dy);
      if (dist < 120) {
        ctx.beginPath();
        ctx.moveTo(p.x, p.y);
        ctx.lineTo(mouse.x, mouse.y);
        ctx.strokeStyle = `rgba(0, 212, 200, ${(1 - dist / 120) * 0.15})`;
        ctx.lineWidth = 0.5;
        ctx.stroke();
      }
    });
    requestAnimationFrame(animate);
  }
  animate();

  document.addEventListener('mousemove', e => { mouse.x = e.clientX; mouse.y = e.clientY; });
  document.addEventListener('touchmove', e => {
    if (e.touches[0]) { mouse.x = e.touches[0].clientX; mouse.y = e.touches[0].clientY; }
  });
})();

// ===== 3D CARD EFFECT =====
document.addEventListener('mouseover', function(e) {
  const card = e.target.closest('.card');
  if (!card) return;
  const rect = card.getBoundingClientRect();
  const x = e.clientX - rect.left;
  const y = e.clientY - rect.top;
  const cx = rect.width / 2;
  const cy = rect.height / 2;
  const rotX = (y - cy) / cy * -4;
  const rotY = (x - cx) / cx * 4;
  card.style.transform = `perspective(1000px) rotateX(${rotX}deg) rotateY(${rotY}deg)`;
});
document.addEventListener('mouseout', function(e) {
  const card = e.target.closest('.card');
  if (!card) return;
  card.style.transform = 'perspective(1000px) rotateX(0deg) rotateY(0deg)';
});

// ===== TAB SYSTEM =====
document.querySelectorAll('.nav-item[data-tab]').forEach(btn => {
  btn.addEventListener('click', () => switchTab(btn.dataset.tab));
});

function switchTab(tab) {
  document.querySelectorAll('.nav-item').forEach(x => x.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(x => x.classList.remove('active'));
  const navBtn = document.querySelector(`.nav-item[data-tab="${tab}"]`);
  if (navBtn) navBtn.classList.add('active');
  const content = document.getElementById('tab-' + tab);
  if (content) content.classList.add('active');
}

// ===== API HELPER =====
async function api(method, url, body) {
  try {
    const token = localStorage.getItem('auth_token');
    const headers = {'Content-Type': 'application/json'};
    if (token) headers['Authorization'] = 'Bearer ' + token;
    const opts = { method, headers };
    if (body) opts.body = JSON.stringify(body);
    const r = await fetch(url, opts);
    if (r.status === 401) {
      localStorage.removeItem('auth_token');
      showLogin();
      return {error: 'Authentication required'};
    }
    const d = await r.json();
    return d;
  } catch(e) { return {error: e.message}; }
}

// ===== AUTH =====
function showLogin() {
  document.getElementById('loginOverlay').classList.add('active');
  document.getElementById('app').classList.remove('active');
  document.getElementById('tbUser').classList.remove('active');
}
function hideLogin() {
  document.getElementById('loginOverlay').classList.remove('active');
  document.getElementById('app').classList.add('active');
  document.getElementById('tbUser').classList.add('active');
}
async function doLogin() {
  const username = document.getElementById('loginUser').value.trim();
  const password = document.getElementById('loginPass').value;
  const errEl = document.getElementById('loginError');
  if (!username || !password) { errEl.textContent = 'Please enter username and password.'; return; }
  errEl.textContent = '';
  try {
    const r = await fetch('/api/auth/login?username=' + encodeURIComponent(username) + '&password=' + encodeURIComponent(password), {method:'POST'});
    const d = await r.json();
    if (d.success) {
      localStorage.setItem('auth_token', d.token);
      localStorage.setItem('auth_username', d.username);
      localStorage.setItem('auth_role', d.role || 'user');
      hideLogin();
      document.getElementById('userNameDisplay').textContent = d.username;
      document.getElementById('userRoleDisplay').textContent = d.role || 'user';
      document.getElementById('userAvatar').textContent = d.username.charAt(0).toUpperCase();
      document.getElementById('loginPass').value = '';
    } else {
      errEl.textContent = d.error || 'Login failed.';
    }
  } catch(e) { errEl.textContent = 'Connection error.'; }
}
async function doLogout() {
  const token = localStorage.getItem('auth_token');
  if (token) {
    await fetch('/api/auth/logout', {method:'POST', headers:{'Authorization':'Bearer '+token}});
  }
  localStorage.removeItem('auth_token');
  localStorage.removeItem('auth_username');
  localStorage.removeItem('auth_role');
  showLogin();
}
async function checkAuth() {
  const token = localStorage.getItem('auth_token');
  if (!token) { showLogin(); return; }
  try {
    const r = await fetch('/api/auth/verify', {headers:{'Authorization':'Bearer '+token}});
    const d = await r.json();
    if (d.success) {
      hideLogin();
      document.getElementById('userNameDisplay').textContent = d.username;
      document.getElementById('userRoleDisplay').textContent = d.role || 'user';
      document.getElementById('userAvatar').textContent = d.username.charAt(0).toUpperCase();
    } else {
      showLogin();
    }
  } catch(e) { showLogin(); }
}

// ===== STATUS POLLING =====
async function pollStatus() {
  const s = await api('GET', '/api/status');
  const dot = document.getElementById('statusDot');
  const txt = document.getElementById('statusText');
  if (s.running) {
    dot.className = 'status-dot online';
    txt.textContent = 'Online';
  } else {
    dot.className = 'status-dot offline';
    txt.textContent = 'Offline';
  }
  const tc = (s.tools_loaded || 0);
  document.getElementById('toolsCount').textContent = tc + ' tools';
  document.getElementById('homeToolsCount').textContent = tc;
  document.getElementById('homeUptime').textContent = s.uptime || '--';
  if (s.llm_running !== undefined) {
    document.getElementById('modelStatus').textContent = 'LLM: ' + (s.llm_running ? '✅ Running' : '❌ Off');
  }
}
setInterval(pollStatus, 5000);
pollStatus();

// ===== HOME =====
async function getHomeInfo() {
  const sys = await api('GET', '/api/system/info');
  if (sys && !sys.error) {
    const lines = [];
    if (sys.os) lines.push('OS: ' + sys.os);
    if (sys.cpu) lines.push('CPU: ' + sys.cpu);
    if (sys.memory) lines.push('Mem: ' + sys.memory);
    if (sys.python) lines.push('Python: ' + sys.python);
    document.getElementById('homeSysInfo').innerHTML = lines.join('<br>') || JSON.stringify(sys, null, 2);
  }
  const mem = await api('GET', '/api/memory/history');
  if (mem && mem.messages) document.getElementById('homeMemory').textContent = mem.messages.length + ' items';

  const and = await api('GET', '/api/android/devices');
  if (and && and.available) {
    document.getElementById('homeAndroid').textContent = (and.devices || []).length + ' devices';
  } else {
    document.getElementById('homeAndroid').textContent = 'Not connected';
  }
}
getHomeInfo();

async function runQuickCmd() {
  const cmd = document.getElementById('quickCmd').value.trim();
  if (!cmd) return;
  document.getElementById('quickCmdOutput').textContent = 'Running...';
  const r = await api('POST', '/api/command', {command: cmd});
  document.getElementById('quickCmdOutput').textContent = r.response || r.error || 'Done.';
}

// ===== CHAT =====
let chatHistory = [];
async function sendChat() {
  const input = document.getElementById('chatInput');
  const msg = input.value.trim();
  if (!msg) return;
  input.value = '';
  const container = document.getElementById('chatMessages');
  container.innerHTML += '<div class="msg user"><div class="msg-label">You</div>' + escapeHtml(msg) + '</div>';
  container.scrollTop = container.scrollHeight;
  chatHistory.push({role: 'user', content: msg});
  const resp = await api('POST', '/api/chat', {message: msg, history: chatHistory.slice(-10)});
  const reply = resp.response || resp.error || 'No response';
  container.innerHTML += '<div class="msg assistant"><div class="msg-label">AI</div>' + escapeHtml(reply) + '</div>';
  container.scrollTop = container.scrollHeight;
  chatHistory.push({role: 'assistant', content: reply});
}
function clearChat() {
  chatHistory = [];
  document.getElementById('chatMessages').innerHTML = '<div class="msg system">Chat cleared.</div>';
}

// ===== TOOLS (base44-style) =====
let allTools = [];
async function loadTools() {
  document.getElementById('toolsLoading').classList.add('active');
  const r = await api('GET', '/api/tools');
  allTools = r.tools || [];
  document.getElementById('toolsLoading').classList.remove('active');
  renderTools();
}
function renderTools() {
  const query = (document.getElementById('toolSearch').value || '').toLowerCase();
  const filtered = allTools.filter(t =>
    t.name.toLowerCase().includes(query) ||
    (t.description||'').toLowerCase().includes(query) ||
    (t.category||'').toLowerCase().includes(query)
  );
  const icons = ['⚡','🔧','📱','🌐','💻','🎯','🛠','📡','🔌','🧩','🤖','🎨'];
  document.getElementById('toolsContainer').innerHTML = filtered.map((t, i) =>
    '<div class="tool-card" onclick="callTool(\'' + t.name + '\')">' +
      '<div class="t-icon">' + icons[i % icons.length] + '</div>' +
      '<div class="t-name">' + t.name + '</div>' +
      '<div class="t-desc">' + escapeHtml(t.description || '') + '</div>' +
      '<span class="t-cat">' + (t.category || 'general') + '</span>' +
    '</div>'
  ).join('');
}
async function callTool(name) {
  const r = await api('POST', '/api/tool/' + name, {});
  alert(JSON.stringify(r, null, 2));
}
loadTools();

// ===== ANDROID (PocketStrike-style) =====
async function checkAndroid() {
  const r = await api('GET', '/api/android/devices');
  const dot = document.getElementById('androidDot');
  const txt = document.getElementById('androidStatusText');
  if (r && r.available && r.devices && r.devices.length > 0) {
    dot.className = 'status-dot online';
    txt.textContent = 'Connected: ' + r.devices.join(', ');
  } else if (r && r.available) {
    dot.className = 'status-dot offline';
    txt.textContent = 'ADB available but no devices connected';
  } else {
    dot.className = 'status-dot offline';
    txt.textContent = 'ADB not available';
  }
}
checkAndroid();

async function androidShell(cmd) {
  if (!cmd) return;
  const term = document.getElementById('androidTerminal');
  term.textContent = '$ ' + cmd + '\nRunning...';
  const r = await api('POST', '/api/android/shell', {command: cmd});
  term.textContent = '$ ' + cmd + '\n' + (r.output || r.error || 'No output');
}

// ===== WEATHER =====
async function getWeather() {
  const city = document.getElementById('weatherCity').value || 'auto';
  document.getElementById('weatherLoading').classList.add('active');
  const r = await api('POST', '/api/weather', {location: city});
  document.getElementById('weatherLoading').classList.remove('active');
  document.getElementById('weatherOutput').textContent = r.result || r.error || 'Error';
}
async function getWeatherDetailed() {
  const city = document.getElementById('weatherCity').value || 'auto';
  document.getElementById('weatherLoading').classList.add('active');
  const r = await api('POST', '/api/weather/detailed', {location: city});
  document.getElementById('weatherLoading').classList.remove('active');
  document.getElementById('weatherOutput').textContent = r.result || r.error || 'Error';
}

// ===== UTILITIES =====
async function calcExec() {
  const expr = document.getElementById('calcExpr').value;
  const r = await api('POST', '/api/calculate', {expression: expr});
  document.getElementById('calcOutput').textContent = r.result || r.error || 'Error';
}
async function genPassword() {
  const len = parseInt(document.getElementById('pwLength').value) || 16;
  const r = await api('POST', '/api/random/password', {length: len});
  document.getElementById('pwOutput').textContent = r.result || r.error || 'Error';
}
async function genQR() {
  const data = document.getElementById('qrData').value;
  const r = await api('POST', '/api/qr/generate', {data});
  document.getElementById('qrOutput').innerHTML = r.result ? '<img src="' + r.result + '" style="max-width:200px;border-radius:8px;margin-top:8px">' : (r.error || 'Error');
}
async function doTranslate() {
  const text = document.getElementById('translateText').value;
  const target = document.getElementById('translateTarget').value || 'hi';
  const source = document.getElementById('translateSource').value || 'auto';
  const r = await api('POST', '/api/translate', {text, target, source});
  document.getElementById('translateOutput').textContent = r.result || r.error || 'Error';
}
async function doBase64(decode) {
  const text = document.getElementById('b64Text').value;
  const r = await api('POST', '/api/text/base64', {text, decode});
  document.getElementById('b64Output').textContent = r.result || r.error || 'Error';
}
async function doTextCount() {
  const text = document.getElementById('textCountInput').value;
  const r = await api('POST', '/api/text/count', {text});
  document.getElementById('textCountOutput').textContent = r.result || r.error || 'Error';
}

// ===== FILES =====
async function listFiles() {
  const path = document.getElementById('filePath').value || '.';
  const r = await api('POST', '/api/file/list', {path, pattern: '*'});
  const listing = r.listing || [];
  document.getElementById('fileListOutput').textContent = listing.join('\n') || '(empty)';
}
async function readFile() {
  const path = document.getElementById('fileReadPath').value;
  if (!path) return;
  const r = await api('POST', '/api/file/read', {path});
  document.getElementById('fileListOutput').textContent = r.content || r.error || 'Error';
}
async function writeFile() {
  const path = document.getElementById('fileWritePath').value;
  const content = document.getElementById('fileWriteContent').value;
  if (!path) return;
  const r = await api('POST', '/api/file/write', {path, content});
  document.getElementById('fileListOutput').textContent = r.result || r.error || 'Error';
}

// ===== WEB =====
async function webSearch() {
  const q = document.getElementById('webQuery').value;
  if (!q) return;
  const r = await api('POST', '/api/web/search', {query: q, max_results: 5});
  const results = r.results || [];
  document.getElementById('webSearchOutput').textContent = results.map(x => '[' + (x.title||'') + '] ' + (x.url||'') + '\n' + (x.snippet||'')).join('\n\n') || 'No results';
}
async function webScrape() {
  const url = document.getElementById('scrapeUrl').value;
  if (!url) return;
  const r = await api('POST', '/api/web/scrape', {url});
  document.getElementById('scrapeOutput').textContent = (r.content || '').slice(0, 2000) || r.error || 'Error';
}

// ===== NOTES =====
async function addNote() {
  const title = document.getElementById('noteTitle').value;
  const content = document.getElementById('noteContent').value;
  if (!title) return;
  const r = await api('POST', '/api/notes/add', {title, content});
  document.getElementById('noteSaveOutput').textContent = r.result || r.error || 'Saved!';
  listNotes();
}
async function listNotes() {
  const r = await api('GET', '/api/notes/list');
  const notes = r.result || '';
  const lines = notes.split('\n').filter(l => l.trim());
  document.getElementById('notesListContainer').innerHTML = lines.map(l =>
    '<div class="note-item" onclick="document.getElementById(\'noteGetTitle\').value=\'' + escapeHtml(l.replace(/^[-*]\s*/,'')) + '\';getNote()">' +
      escapeHtml(l) +
    '</div>'
  ).join('');
}
async function getNote() {
  const title = document.getElementById('noteGetTitle').value;
  if (!title) return;
  const r = await api('POST', '/api/notes/get', {title});
  document.getElementById('noteViewOutput').textContent = r.result || r.error || 'Not found';
}
listNotes();

// ===== SYSTEM =====
async function getSysInfo() {
  const r = await api('GET', '/api/system/info');
  document.getElementById('sysInfoOutput').textContent = r.result || JSON.stringify(r, null, 2) || 'Error';
}
async function getNetwork() {
  const r = await api('GET', '/api/network');
  document.getElementById('networkOutput').textContent = r.result || r.error || 'Error';
}
async function speedTest() {
  document.getElementById('networkOutput').textContent = 'Running speed test...';
  const r = await api('GET', '/api/network/speedtest');
  document.getElementById('networkOutput').textContent = r.result || r.error || 'Error';
}
async function getProcesses() {
  document.getElementById('procLoading').classList.add('active');
  const filter = document.getElementById('procFilter').value || '';
  const r = await api('POST', '/api/system/processes', {filter});
  document.getElementById('procLoading').classList.remove('active');
  const lines = (r.result || '').split('\n').filter(l => l.trim());
  document.getElementById('procContainer').innerHTML = lines.slice(0, 100).map(l =>
    '<div class="proc-item">' + escapeHtml(l) + '</div>'
  ).join('');
}
getProcesses();
getSysInfo();

// ===== HELPER =====
function escapeHtml(s) {
  if (!s) return '';
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

// ===== SELF-DEVELOP =====
let lastGeneratedModule = '';

async function generateCode() {
  const prompt = document.getElementById('buildPrompt').value.trim();
  if (!prompt) { document.getElementById('codePreview').textContent = 'Please describe what you want to build first.'; return; }
  document.getElementById('buildLoading').classList.add('active');
  document.getElementById('codePreview').textContent = 'Generating...';
  const r = await api('POST', '/api/self/generate', {prompt});
  document.getElementById('buildLoading').classList.remove('active');
  if (r.success) {
    document.getElementById('codePreview').textContent = r.code || 'No code returned';
    document.getElementById('currentModule').textContent = r.module_name || '—';
    lastGeneratedModule = r.module_name || '';
    document.getElementById('registerModuleName').value = r.module_name || '';
    document.getElementById('actionOutput').textContent = 'Code generated: ' + r.filepath;
  } else {
    document.getElementById('codePreview').textContent = 'Error: ' + (r.error || 'Unknown error');
    document.getElementById('actionOutput').textContent = 'Generation failed';
  }
}

async function buildFeature() {
  const prompt = document.getElementById('buildPrompt').value.trim();
  if (!prompt) { document.getElementById('codePreview').textContent = 'Please describe what you want to build first.'; return; }
  document.getElementById('buildLoading').classList.add('active');
  document.getElementById('actionOutput').textContent = 'Running full build pipeline...';
  const r = await api('POST', '/api/self/build', {prompt, create_pr: false});
  document.getElementById('buildLoading').classList.remove('active');
  if (r.success) {
    document.getElementById('codePreview').textContent = 'Build complete!\n\nModule: ' + (r.module_name || '') + '\nFile: ' + (r.filepath || '');
    let steps = (r.steps || []).map(s => '  \u2022 ' + (s.step || '?') + ': ' + (s.success ? '\u2705' : '\u274c')).join('\n');
    document.getElementById('actionOutput').textContent = 'Build pipeline:\n' + steps;
    document.getElementById('currentModule').textContent = r.module_name || '—';
    lastGeneratedModule = r.module_name || '';
    document.getElementById('registerModuleName').value = r.module_name || '';
  } else {
    document.getElementById('actionOutput').textContent = 'Build failed: ' + (r.error || 'Unknown error');
  }
}

async function registerModule() {
  const name = document.getElementById('registerModuleName').value.trim() || lastGeneratedModule;
  if (!name) { document.getElementById('actionOutput').textContent = 'No module name.'; return; }
  document.getElementById('actionOutput').textContent = 'Registering ' + name + '...';
  const r = await api('POST', '/api/self/register', {module_name: name});
  const msg = r.success ? 'Registered successfully' : 'Registration failed: ' + (r.error || '');
  document.getElementById('actionOutput').textContent = msg + '\nFunctions: ' + JSON.stringify(r.registered_functions || []);
}

async function gitCommit() {
  const msg = document.getElementById('gitCommitMsg').value.trim() || 'Auto-commit from Web UI';
  document.getElementById('actionOutput').textContent = 'Committing...';
  const r = await api('POST', '/api/self/git-commit', {message: msg});
  if (r.success) {
    document.getElementById('actionOutput').textContent = 'Commit: ' + (r.commit_hash || '') + '\nMessage: ' + (r.message || '');
  } else {
    document.getElementById('actionOutput').textContent = 'Commit failed: ' + (r.error || r.output || '');
  }
}

async function githubPR() {
  const title = document.getElementById('prTitle').value.trim() || 'Auto-generated PR from Web UI';
  document.getElementById('actionOutput').textContent = 'Creating GitHub PR...';
  const r = await api('POST', '/api/self/github-pr', {title});
  if (r.success) {
    document.getElementById('actionOutput').textContent = 'PR created: ' + (r.pr_url || '') + '\nBranch: ' + (r.branch || '');
  } else {
    document.getElementById('actionOutput').textContent = 'PR failed: ' + (r.error || '');
  }
}

async function listGenerated() {
  const r = await api('GET', '/api/self/list-generated');
  const modules = r.modules || [];
  if (modules.length === 0) {
    document.getElementById('generatedModulesOutput').textContent = 'No generated modules found.';
    return;
  }
  document.getElementById('generatedModulesOutput').textContent = modules.map(m => '  \u2022 ' + m).join('\n');
}

async function checkCodeQuality() {
  const filepath = document.getElementById('qualityFilePath').value.trim() || document.getElementById('currentModule').textContent;
  if (!filepath || filepath === '—') {
    const r = await api('GET', '/api/self/list-generated');
    const modules = r.modules || [];
    if (modules.length === 0) {
      document.getElementById('actionOutput').textContent = 'No file specified and no generated modules found.';
      return;
    }
    document.getElementById('actionOutput').textContent = 'Checking latest module...';
    const fp = '/root/Desktop/agent/modules/' + modules[modules.length - 1] + '.py';
    const q = await api('POST', '/api/self/code-quality', {filepath: fp});
    document.getElementById('actionOutput').textContent = 'Quality check:\n' + (q.issues || []).map(i => '  ' + i.type + ': ' + i.msg).join('\n') || 'No issues found';
    return;
  }
  document.getElementById('actionOutput').textContent = 'Checking...';
  const q = await api('POST', '/api/self/code-quality', {filepath});
  document.getElementById('actionOutput').textContent = 'Quality check:\n' + (q.issues || []).map(i => '  ' + i.type + ': ' + (i.msg || '')).join('\n') || 'No issues found';
}

async function loadProfile() {
  const r = await api('GET', '/api/profile/current');
  document.getElementById('profileOutput').textContent = JSON.stringify(r, null, 2);
}
async function listProfiles() {
  const r = await api('GET', '/api/profile/list');
  const profiles = r.profiles || [];
  document.getElementById('profileOutput').textContent = 'Profiles:\n' + (profiles.length ? profiles.map(p => '  \u2022 ' + p).join('\n') : 'No profiles found');
}
async function healthReport() {
  document.getElementById('healthOutput').textContent = 'Running health checks...';
  const r = await api('GET', '/api/health');
  const report = r.report || r;
  if (Array.isArray(report)) {
    document.getElementById('healthOutput').textContent = report.map(h => {
      const status = h.ok || h.passed ? '\u2705' : '\u274c';
      return status + ' ' + (h.name || h.check || '?') + ': ' + (h.detail || h.value || h.status || '');
    }).join('\n');
  } else {
    document.getElementById('healthOutput').textContent = JSON.stringify(report, null, 2);
  }
}
async function selfHeal() {
  document.getElementById('healthOutput').textContent = 'Running self-heal...';
  const r = await api('POST', '/api/self/heal');
  const fixes = r.fixes || {};
  const lines = ['Self-Heal Results:'];
  for (const [key, val] of Object.entries(fixes)) {
    lines.push('  \u2022 ' + key + ': ' + (val ? 'Fixed' : 'No action needed'));
  }
  document.getElementById('healthOutput').textContent = lines.join('\n') || JSON.stringify(fixes, null, 2);
}
function clearBuild() {
  document.getElementById('buildPrompt').value = '';
  document.getElementById('codePreview').textContent = 'Cleared.';
  document.getElementById('actionOutput').textContent = 'Ready.';
  document.getElementById('currentModule').textContent = '—';
  lastGeneratedModule = '';
}

// ===== INIT =====
checkAuth();
</script>
</body>
</html>
"""


# ===========================================================================
# Routes
# ===========================================================================

@app.get("/")
def dashboard():
    return HTMLResponse(DASHBOARD_HTML)


# --- Status ---

@app.get("/api/status")
def get_status():
    return engine.status()


@app.get("/api/health")
def get_health():
    report = health.json_report()
    return report


@app.post("/api/self/heal")
def run_self_heal():
    fixes = healer.heal_all()
    return {"fixes": fixes}


# --- Self-Developer API ---

@app.post("/api/self/build")
def api_self_build(data: dict):
    prompt = data.get("prompt", "")
    module_name = data.get("module_name", None)
    create_pr = data.get("create_pr", False)
    if not prompt:
        return {"error": "No prompt provided"}
    result = build_from_prompt(prompt, module_name, create_pr)
    return result


@app.post("/api/self/generate")
def api_self_generate(data: dict):
    prompt = data.get("prompt", "")
    module_name = data.get("module_name", None)
    if not prompt:
        return {"error": "No prompt provided"}
    result = generate_module_from_prompt(prompt, module_name)
    return result


@app.post("/api/self/register")
def api_self_register(data: dict):
    module_name = data.get("module_name", "")
    if not module_name:
        return {"error": "No module name"}
    result = auto_register_module(module_name)
    return result


@app.post("/api/self/git-commit")
def api_self_git_commit(data: dict):
    message = data.get("message", "Auto-commit from web UI")
    files = data.get("files", None)
    result = create_git_commit(message, files)
    return result


@app.post("/api/self/github-pr")
def api_self_github_pr(data: dict):
    title = data.get("title", "Auto-generated PR")
    body = data.get("body", None)
    result = create_github_pr(title, body)
    return result


@app.get("/api/self/list-generated")
def api_self_list_generated():
    modules = list_generated_modules()
    return {"modules": modules}


@app.post("/api/self/code-quality")
def api_self_code_quality(data: dict):
    filepath = data.get("filepath", "")
    if not filepath:
        return {"error": "No filepath"}
    result = analyze_code_quality(filepath)
    return result


# --- Profile API ---

@app.post("/api/profile/save")
def api_profile_save(data: dict):
    name = data.get("name", "")
    profile_data = data.get("data", {})
    if not name:
        return {"error": "No profile name"}
    result = profile_manager.save_profile(name, profile_data)
    return {"result": result}


@app.post("/api/profile/load")
def api_profile_load(data: dict):
    name = data.get("name", "")
    if not name:
        return {"error": "No profile name"}
    result = profile_manager.load_profile(name)
    return {"profile": result}


@app.get("/api/profile/list")
def api_profile_list():
    profiles = profile_manager.list_profiles()
    return {"profiles": profiles}


@app.get("/api/profile/current")
def api_profile_current():
    """Get the current active profile (Abhinav)."""
    from core.config import config
    profile = config.get("profile", default={})
    name = profile.get("name", "default")
    data = profile_manager.load_profile(name.lower())
    return {"name": name, "profile": profile, "memory_data": data}


# --- Command ---

@app.post("/api/command")
def run_command(data: dict):
    command = data.get("command", "")
    if not command:
        return {"error": "No command provided"}
    result = engine.process_text(command)
    return {"response": result}


# --- Chat (with history) ---

@app.post("/api/chat")
def api_chat(data: dict):
    message = data.get("message", "")
    history = data.get("history", [])
    if not message:
        return {"error": "No message"}

    system = data.get("system", "You are a helpful AI assistant.")
    messages = [{"role": "system", "content": system}]
    messages.extend(history)
    messages.append({"role": "user", "content": message})

    try:
        response = chat(messages)
        content = ""
        if isinstance(response, dict):
            content = response.get("message", {}).get("content", "")
        else:
            content = str(response)
        return {"response": content}
    except Exception as e:
        return {"error": str(e)}


# --- Tools ---

@app.get("/api/tools")
def list_all_tools():
    return {"tools": registry.list_tools()}


@app.get("/api/actions")
def list_actions():
    return {"actions": engine.actions.list()}


@app.post("/api/tool/{tool_name}")
def call_tool(tool_name: str, data: dict = {}):
    return registry.call(tool_name, **data)


@app.post("/api/action/{action_name}")
def call_action(action_name: str, data: dict = {}):
    return engine.actions.call(action_name, **data)


# --- Screenshot ---

@app.get("/api/screenshot")
def take_screenshot():
    result = automation.screenshot()
    if "error" in result:
        return JSONResponse({"error": result["error"]}, status_code=500)
    path = result.get("path", "")
    if os.path.exists(path):
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return {"path": path, "base64": b64}
    return {"error": "Screenshot file not found"}


# --- Memory ---

@app.get("/api/memory/history")
def get_history(limit: int = 50):
    return {"messages": memory.get_history(limit=limit)}


@app.get("/api/memory/facts")
def get_facts(category: str = None):
    if category:
        return memory.recall_by_category(category)
    return {"facts": memory.search_facts("")}


@app.post("/api/memory/remember")
def remember_fact(data: dict):
    memory.remember(data.get("key"), data.get("value"), data.get("category", "general"))
    return {"success": True}


@app.post("/api/memory/forget")
def forget_fact(data: dict):
    memory.forget(data.get("key"))
    return {"success": True}


# --- Web Tools ---

@app.post("/api/web/search")
def api_web_search(data: dict):
    query = data.get("query", "")
    n = data.get("max_results", 5)
    if not query:
        return {"error": "No query"}
    return {"results": web_search(query, n)}


@app.post("/api/web/scrape")
def api_web_scrape(data: dict):
    url = data.get("url", "")
    if not url:
        return {"error": "No URL"}
    return {"content": web_scrape(url)}


@app.post("/api/web/fetch_json")
def api_web_fetch_json(data: dict):
    url = data.get("url", "")
    if not url:
        return {"error": "No URL"}
    return {"data": web_fetch_json(url)}


@app.post("/api/web/search_news")
def api_web_search_news(data: dict):
    query = data.get("query", "")
    n = data.get("max_results", 5)
    if not query:
        return {"error": "No query"}
    return {"results": web_search_news(query, n)}


# --- File Tools ---

@app.post("/api/file/read")
def api_file_read(data: dict):
    path = data.get("path", "")
    if not path:
        return {"error": "No path"}
    return {"content": file_read(path)}


@app.post("/api/file/write")
def api_file_write(data: dict):
    path = data.get("path", "")
    content = data.get("content", "")
    if not path:
        return {"error": "No path"}
    return {"result": file_write(path, content)}


@app.post("/api/file/edit")
def api_file_edit(data: dict):
    path = data.get("path", "")
    old = data.get("old_string", "")
    new = data.get("new_string", "")
    return {"result": file_edit(path, old, new)}


@app.post("/api/file/list")
def api_file_list(data: dict):
    path = data.get("path", ".")
    pattern = data.get("pattern", "*")
    return {"listing": file_list(path, pattern)}


# --- Code Tools ---

@app.post("/api/code/python")
def api_run_python(data: dict):
    code = data.get("code", "")
    if not code:
        return {"error": "No code"}
    return {"output": run_python(code)}


@app.post("/api/code/shell")
def api_run_shell(data: dict):
    cmd = data.get("command", "")
    timeout = data.get("timeout", 30)
    if not cmd:
        return {"error": "No command"}
    return {"output": run_shell(cmd, timeout)}


# --- Android ---

@app.get("/api/android/devices")
def api_android_devices():
    return {"devices": android.devices() if android.available else [],
            "available": android.available}


@app.post("/api/android/shell")
def api_android_shell(data: dict):
    command = data.get("command", "")
    if not command:
        return {"error": "No command"}
    result = android.shell(command) if hasattr(android, 'shell') else {"error": "Not available"}
    return {"output": result.get("stdout", "")}


# --- LLM ---

@app.get("/api/llm/models")
def api_llm_models():
    return {"models": list_models(), "running": is_running()}


@app.post("/api/llm/pull")
def api_llm_pull(data: dict):
    model = data.get("model", "")
    if not model:
        return {"error": "No model name"}
    result = pull_model(model)
    return {"result": result}


@app.get("/api/system/info")
def api_system_info():
    return sys_info_dict()


# ===========================================================================
# UTILITY API ENDPOINTS
# ===========================================================================

# --- Weather ---

@app.post("/api/weather")
def api_weather(data: dict):
    loc = data.get("location", "auto")
    return {"result": weather_get(loc)}


@app.post("/api/weather/detailed")
def api_weather_detailed(data: dict):
    loc = data.get("location", "auto")
    return {"result": weather_detailed(loc)}


# --- Calculator ---

@app.post("/api/calculate")
def api_calculate(data: dict):
    expr = data.get("expression", "")
    return {"result": calculate(expr)}


# --- System Info ---

@app.get("/api/system/info/detailed")
def api_system_info_detailed():
    return sys_info_dict()


# --- Processes ---

@app.post("/api/system/processes")
def api_process_list(data: dict):
    filt = data.get("filter", "")
    return {"result": process_list(filt)}


@app.post("/api/system/processes/kill")
def api_process_kill_endpoint(data: dict):
    pid = data.get("pid", 0)
    return {"result": process_kill(pid)}


# --- Network ---

@app.get("/api/network")
def api_network():
    return {"result": network_info()}


@app.get("/api/network/speedtest")
def api_network_speedtest():
    return {"result": network_speed_test()}


# --- Random Generators ---

@app.post("/api/random/password")
def api_random_password(data: dict):
    length = data.get("length", 16)
    return {"result": random_password(length)}


@app.post("/api/random/number")
def api_random_number(data: dict):
    min_val = data.get("min", 0)
    max_val = data.get("max", 100)
    return {"result": random_number(min_val, max_val)}


@app.get("/api/random/uuid")
def api_random_uuid():
    return {"result": random_uuid()}


# --- Translation ---

@app.post("/api/translate")
def api_translate(data: dict):
    text = data.get("text", "")
    target = data.get("target", "en")
    source = data.get("source", "auto")
    return {"result": translate_text(text, target, source)}


# --- Notes ---

@app.post("/api/notes/add")
def api_notes_add(data: dict):
    title = data.get("title", "")
    content = data.get("content", "")
    return {"result": note_add(title, content)}


@app.post("/api/notes/get")
def api_notes_get(data: dict):
    title = data.get("title", "")
    return {"result": note_get(title)}


@app.get("/api/notes/list")
def api_notes_list():
    return {"result": note_list()}


# --- QR Code ---

@app.post("/api/qr/generate")
def api_qr_generate(data: dict):
    qr_data = data.get("data", "")
    return {"result": qr_generate(qr_data)}


# --- URL Shortener ---

@app.post("/api/url/shorten")
def api_url_shorten(data: dict):
    url = data.get("url", "")
    return {"result": url_shorten(url)}


# --- Text Utilities ---

@app.post("/api/text/count")
def api_text_count(data: dict):
    text = data.get("text", "")
    return {"result": text_count(text)}


@app.post("/api/text/base64")
def api_text_base64(data: dict):
    text = data.get("text", "")
    decode = data.get("decode", False)
    return {"result": encode_base64(text, decode)}


# ===========================================================================
# Auth API Endpoints (unauthenticated)
# ===========================================================================

@app.post("/api/auth/login")
async def api_login(username: str, password: str):
    """Simple login — accepts any username, password matches config or 'admin'."""
    admin_pass = config.get("web", "admin_password", default="admin")
    if password == admin_pass:
        role = "admin" if username == "admin" else "user"
        token = create_session(username, role)
        return {"success": True, "token": token, "username": username, "role": role}
    return JSONResponse({"success": False, "error": "Invalid credentials"}, status_code=401)

@app.get("/api/auth/verify")
async def api_verify(request: Request):
    """Verify a token."""
    session = require_auth(request)
    if session:
        return {"success": True, "username": session["username"], "role": session["role"]}
    return JSONResponse({"success": False, "error": "Invalid token"}, status_code=401)

@app.post("/api/auth/logout")
async def api_logout(request: Request):
    """Logout — invalidate token."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        _sessions.pop(token, None)
    return {"success": True}


# ===========================================================================
# WebSocket Chat
# ===========================================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    history = []
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            user_text = msg.get("message", "")
            if not user_text:
                continue
            history.append({"role": "user", "content": user_text})
            system = msg.get("system", "You are a helpful AI assistant.")
            messages = [{"role": "system", "content": system}]
            messages.extend(history[-10:])
            try:
                response = chat(messages)
                content = ""
                if isinstance(response, dict):
                    content = response.get("message", {}).get("content", "")
                else:
                    content = str(response)
                history.append({"role": "assistant", "content": content})
                await websocket.send_text(json.dumps({"response": content}))
            except Exception as e:
                await websocket.send_text(json.dumps({"error": str(e)}))
    except WebSocketDisconnect:
        pass
    except Exception:
        pass


# ===========================================================================
# Background Runner (used by main.py)
# ===========================================================================

def run_in_background(host="0.0.0.0", port=8765):
    """Run the web server in a background thread."""
    import threading as _t
    t = _t.Thread(target=uvicorn.run, args=(app,), kwargs={
        "host": host, "port": port, "log_level": "info"
    }, daemon=True)
    t.start()
    print(f"[Web] Server started on {host}:{port}")
    return t


# ===========================================================================
# Entry
# ===========================================================================

if __name__ == "__main__":
    port = config.get("web_port", 8765)
    host = config.get("web_host", "0.0.0.0")
    uvicorn.run(app, host=host, port=port, log_level="info")
