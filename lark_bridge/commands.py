"""Slash commands: /help, /status, /new, /config, /stop, /cd"""

import json, logging, os, time
from .feishu_client import send_reply
from .session import sessions
from .config import config as cfg

logger = logging.getLogger("lark_bridge.commands")

def _send_card(msg_id: str, title: str, lines: list):
    content = json.dumps({"zh_cn":{"title":title,"content":[
        [{"tag":"text","text":l}] for l in lines
    ]}})
    send_reply(msg_id, content, "post")

def cmd_help(msg_id, chat_id):
    _send_card(msg_id, "help", [
        "**lark_bridge commands**",
        "",
        "`/help` — show this help",
        "`/status` — show session status",
        "`/new` or `/reset` — clear session",
        "`/cd <path>` — change working directory",
        "`/stop` — stop current run",
        "`/config` — show config",
        "",
        "Reply mode: text (waits for Claude, sends as rich text)",
    ])

def cmd_status(msg_id, chat_id):
    s = sessions.get(chat_id)
    _send_card(msg_id, "status", [
        f"Chat: {chat_id[:20]}...",
        f"Type: {s.chat_type}",
        f"CWD: {s.cwd}",
        f"Messages: {s.message_count}",
        f"Running: {s.is_running}",
        f"Mode: {s.permission_mode}",
        f"Last: {time.strftime('%H:%M:%S', time.localtime(s.last_active)) if s.last_active else 'N/A'}",
    ])

def cmd_new(msg_id, chat_id):
    sessions.reset(chat_id)
    _send_card(msg_id, "reset", ["Session cleared."])

def cmd_config(msg_id, chat_id):
    _send_card(msg_id, "config", [
        f"App: {cfg.app.app_id[:16]}...",
        f"Tenant: {cfg.app.tenant}",
        f"Reply mode: {cfg.prefs.reply_mode}",
        f"Permission: {cfg.prefs.permission_mode}",
        f"Max concurrent: {cfg.prefs.max_concurrent_runs}",
        f"CWD: {cfg.prefs.default_cwd}",
    ])

def cmd_stop(msg_id, chat_id, interrupt=None):
    if interrupt: interrupt(chat_id)
    _send_card(msg_id, "stop", ["Stop requested."])

def cmd_cd(msg_id, chat_id, path):
    expanded = os.path.expanduser(path)
    if os.path.isdir(expanded):
        sessions.update(chat_id, cwd=expanded)
        _send_card(msg_id, "cd", [f"Changed to: {expanded}"])
    else:
        _send_card(msg_id, "cd", [f"Not found: {expanded}"])

def dispatch(msg: dict, interrupt_callback=None) -> bool:
    text = msg.get("text", "").strip()
    if not text.startswith("/"):
        return False
    msg_id = msg["message_id"]
    chat_id = msg["chat_id"]
    parts = text.split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""
    logger.info(f"cmd: {cmd} arg={arg[:40]}")
    if cmd in ("/help", "/h"): cmd_help(msg_id, chat_id)
    elif cmd in ("/status", "/st"): cmd_status(msg_id, chat_id)
    elif cmd in ("/new", "/reset"): cmd_new(msg_id, chat_id)
    elif cmd == "/config": cmd_config(msg_id, chat_id)
    elif cmd == "/stop": cmd_stop(msg_id, chat_id, interrupt_callback)
    elif cmd == "/cd": cmd_cd(msg_id, chat_id, arg)
    else: _send_card(msg_id, "unknown", [f"Unknown: {cmd}. Try /help"])
    return True