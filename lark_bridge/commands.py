"""Slash commands — mirrors commands/index.ts. /help /status /new /config /stop /cd /resume"""

import json, logging, os, time
from .feishu_client import send_reply
from .session import sessions
from .config import config as cfg

logger = logging.getLogger("lark_bridge.commands")

def _card(msg_id, title, lines):
    content = json.dumps({"zh_cn":{"title":title,"content":[[{"tag":"text","text":l}] for l in lines]}})
    send_reply(msg_id, content, "post")

def cmd_help(msg_id, chat_id):
    _card(msg_id, "help", [
        "**lark_bridge commands**",
        "",
        "`/help` — show this help",
        "`/status` — session status",
        "`/new` or `/reset` — clear session",
        "`/cd <path>` — change working dir",
        "`/stop` — stop current run",
        "`/config` — show config",
        "",
        "Reply modes: text (default), markdown, card",
        "Text mode: waits for Claude, sends as rich text",
    ])

def cmd_status(msg_id, chat_id):
    s = sessions.get(chat_id)
    _card(msg_id, "status", [
        f"Chat: {chat_id[:20]}...",
        f"Type: {s.chat_type}, CWD: {s.cwd}",
        f"Messages: {s.message_count}, Running: {s.is_running}",
        f"Mode: {s.permission_mode}",
        f"Last: {time.strftime('%H:%M:%S', time.localtime(s.last_active)) if s.last_active else 'N/A'}",
    ])

def cmd_new(msg_id, chat_id):
    sessions.reset(chat_id)
    _card(msg_id, "reset", ["Session cleared. Next message starts a fresh Claude session."])

def cmd_config_card(msg_id, chat_id):
    _card(msg_id, "config", [
        f"App: {cfg.app.app_id[:16]}...",
        f"Tenant: {cfg.app.tenant}",
        f"Reply mode: {cfg.prefs.reply_mode}",
        f"Permission: {cfg.prefs.permission_mode}",
        f"Show tools: {cfg.prefs.show_tool_calls}",
        f"Max concurrent: {cfg.prefs.max_concurrent_runs}",
        f"CWD: {cfg.prefs.default_cwd}",
    ])

def cmd_stop(msg_id, chat_id, interrupt=None):
    if interrupt: interrupt(chat_id)
    _card(msg_id, "stop", ["Stop requested. Current run will terminate."])

def cmd_cd(msg_id, chat_id, path):
    p = os.path.expanduser(path)
    if os.path.isdir(p):
        sessions.update(chat_id, cwd=p)
        _card(msg_id, "cd", [f"Working directory: {p}"])
    else:
        _card(msg_id, "cd", [f"Not found: {p}"])

def dispatch(msg, interrupt_callback=None) -> bool:
    text = msg.get("text", "").strip()
    if not text.startswith("/"): return False
    mid, cid = msg["message_id"], msg["chat_id"]
    parts = text.split(maxsplit=1)
    cmd = parts[0].lower(); arg = parts[1] if len(parts) > 1 else ""
    logger.info(f"cmd: {cmd} {arg[:40]}")
    if cmd in ("/help","/h"): cmd_help(mid, cid)
    elif cmd in ("/status","/st"): cmd_status(mid, cid)
    elif cmd in ("/new","/reset"): cmd_new(mid, cid)
    elif cmd == "/config": cmd_config_card(mid, cid)
    elif cmd == "/stop": cmd_stop(mid, cid, interrupt_callback)
    elif cmd == "/cd": cmd_cd(mid, cid, arg)
    else: _card(mid, "unknown", [f"Unknown: {cmd}. Try /help"])
    return True
