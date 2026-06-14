"""Main entry — mirrors cli/index.ts run command. WS/poll → message → Claude → reply."""

import json, logging, sys, threading, time, os
from typing import Dict
from .feishu_client import get_tenant_token, connect_ws, parse_message, send_reply, get_messages, _api, CHAT_ID
from .claude_adapter import ClaudeAdapter
from .session import sessions
from .commands import dispatch as handle_command
from .reply import RunState, send_text_reply
from .config import config as cfg

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("lark_bridge")

_running: Dict[str, bool] = {}

def interrupt_run(chat_id): _running[chat_id] = False

def handle_message(msg, adapter):
    mid, cid = msg["message_id"], msg["chat_id"]
    text = msg.get("text", "").strip()
    if not text: return
    logger.info(f"<<< {msg.get('sender_name','?')}: {text[:80]}")

    # Commands
    if handle_command(msg, interrupt_run): return

    # Session
    s = sessions.get(cid)
    s.message_count += 1; s.is_running = True; _running[cid] = True
    sessions._save()

    # Claude
    prompt = adapter.build_prompt(text, cid, msg.get("sender_name","?"), msg.get("sender_id",""))
    state = RunState()
    cwd = os.path.expanduser(s.cwd) if s.cwd != "~" else os.path.expanduser("~")
    try:
        for evt in adapter.run(prompt, cwd=cwd, permission_mode=s.permission_mode):
            if not _running.get(cid, True): break
            state.reduce(evt)
    except Exception as e:
        logger.error(f"claude: {e}"); state.terminal = "failed"

    # Reply
    if state.terminal == "normal" and state.blocks:
        send_text_reply(mid, state)
    elif state.terminal == "failed":
        send_reply(mid, json.dumps({"zh_cn":{"title":"error","content":[[{"tag":"text","text":"Claude error"}]]}}), "post")

    s.is_running = False; _running.pop(cid, None); sessions._save()

# ── Polling loop (no deps) ──────────────────────────────────────

def poll_loop(adapter):
    seen = set()
    try:
        r = get_messages(1)
        for m in r.get("data",{}).get("items",[]): seen.add(m["message_id"])
    except Exception as e: logger.error(f"seed: {e}")
    logger.info(f"[poll] {len(seen)} msgs seeded, chat={CHAT_ID[-12:]}")

    while True:
        try:
            r = get_messages(5)
            items = r.get("data",{}).get("items",[]) if isinstance(r, dict) else []
            new = []
            for m in items:
                if m["message_id"] in seen: break
                new.append(m)
            if new:
                seen.update(m["message_id"] for m in new)
                for m in reversed(new):
                    try: txt = json.loads(m.get("body",{}).get("content","{}")).get("text","")
                    except: continue
                    if txt.strip():
                        handle_message({"message_id":m["message_id"],"chat_id":CHAT_ID,
                            "chat_type":"p2p","sender_id":m.get("sender",{}).get("id",""),
                            "sender_name":"user","text":txt}, adapter)
        except Exception as e: logger.error(f"poll: {e}")
        time.sleep(3)

# ── WS loop ─────────────────────────────────────────────────────

def ws_loop(adapter):
    try: import websocket
    except ImportError:
        logger.warning("websocket-client not available, using polling")
        poll_loop(adapter); return

    url = connect_ws()
    if not url:
        logger.error("No WS URL, using polling")
        poll_loop(adapter); return

    ws = websocket.WebSocketApp(url,
        on_open=lambda ws: logger.info("[WS] connected"),
        on_error=lambda ws, e: logger.error(f"[WS] {e}"),
        on_close=lambda ws, c, m: logger.info(f"[WS] closed {c}"))

    def on_msg(ws, raw):
        msg = parse_message(raw)
        if msg: threading.Thread(target=handle_message, args=(msg, adapter), daemon=True).start()
    ws.on_message = on_msg

    # Heartbeat
    def hb():
        while True:
            time.sleep(30)
            try: ws.send(json.dumps({"type":"ping"}))
            except: break
    threading.Thread(target=hb, daemon=True).start()
    ws.run_forever(ping_interval=30, ping_timeout=10)

# ── Entry ───────────────────────────────────────────────────────

def main():
    print(f"lark_bridge v0.2.0 | Bot: {cfg.app.bot_name} | Mode: {cfg.prefs.reply_mode}")
    cfg.ensure_dirs()
    if cfg.prefs.default_cwd == "~": cfg.prefs.default_cwd = os.path.expanduser("~")
    ws_loop(ClaudeAdapter())

if __name__ == "__main__":
    main()
