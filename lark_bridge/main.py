"""Main entry point — WS/poll dispatch, message handling, Claude run."""

import json, logging, sys, threading, time, os
from typing import Dict

from .feishu_client import connect_ws, parse_message, send_reply, get_tenant_token, _req as api_req
from .claude_adapter import ClaudeAdapter
from .session import sessions
from .commands import dispatch as handle_command
from .reply import RunState, send_text_reply
from .config import config as cfg

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("lark_bridge")

_running: Dict[str, bool] = {}

def interrupt_run(chat_id: str):
    _running[chat_id] = False

def handle_message(msg: dict, adapter: ClaudeAdapter):
    msg_id = msg["message_id"]
    chat_id = msg["chat_id"]
    text = msg.get("text", "").strip()
    sender = msg.get("sender_name", "user")
    if not text:
        return
    logger.info(f"<<< {sender}: {text[:80]}")
    if handle_command(msg, interrupt_run):
        return
    session = sessions.get(chat_id)
    session.message_count += 1
    session.is_running = True
    _running[chat_id] = True
    sessions._save()
    prompt = adapter.build_prompt(text, chat_id, sender, msg.get("sender_id", ""))
    state = RunState()
    cwd = os.path.expanduser(session.cwd) if session.cwd != "~" else os.path.expanduser("~")
    try:
        for evt in adapter.run(prompt, cwd=cwd, permission_mode=session.permission_mode):
            if not _running.get(chat_id, True):
                break
            state.reduce(evt)
    except Exception as e:
        logger.error(f"Claude: {e}")
        state.terminal = "failed"
    if state.terminal == "normal" and state.blocks:
        send_text_reply(msg_id, state)
    elif state.terminal == "failed":
        send_reply(msg_id, json.dumps({"zh_cn":{"title":"error","content":[[{"tag":"text","text":"Claude error"}]]}}), "post")
    session.is_running = False
    _running.pop(chat_id, None)
    sessions._save()

KNOWN_CHAT = "oc_10967462b13aa3fb8648e1571871859c"

def poll_loop(adapter: ClaudeAdapter):
    chat_id = KNOWN_CHAT
    seen = set()
    try:
        token = get_tenant_token()
        r = api_req("GET", f"/im/v1/messages?container_id_type=chat&container_id={chat_id}&page_size=1&sort_type=ByCreateTimeDesc", None, token)
        for m in r.get("data",{}).get("items",[]):
            seen.add(m["message_id"])
    except Exception as e:
        logger.error(f"seed: {e}")
    logger.info(f"[poll] Seeded {len(seen)} msgs, chat={chat_id[-12:]}")
    while True:
        try:
            token = get_tenant_token()
            r = api_req("GET", f"/im/v1/messages?container_id_type=chat&container_id={chat_id}&page_size=5&sort_type=ByCreateTimeDesc", None, token)
            new_msgs = []
            for m in r.get("data",{}).get("items",[]):
                if m["message_id"] in seen:
                    break
                new_msgs.append(m)
            if new_msgs:
                seen.update(m["message_id"] for m in new_msgs)
                for m in reversed(new_msgs):
                    try:
                        txt = json.loads(m.get("body",{}).get("content","{}")).get("text","")
                    except Exception:
                        continue
                    if txt.strip():
                        handle_message({"message_id":m["message_id"],"chat_id":chat_id,"chat_type":"p2p",
                            "sender_id":m.get("sender",{}).get("id",""),"sender_name":"user","text":txt}, adapter)
        except Exception as e:
            logger.error(f"poll: {e}")
        time.sleep(3)

def ws_loop(adapter: ClaudeAdapter):
    try:
        import websocket
    except ImportError:
        logger.warning("websocket-client not available, using HTTP polling")
        poll_loop(adapter)
        return
    ws_url = connect_ws()
    ws = websocket.WebSocketApp(ws_url,
        on_open=lambda ws: logger.info("[WS] connected"),
        on_error=lambda ws, err: logger.error(f"[WS] err: {err}"),
        on_close=lambda ws, code, msg: logger.info(f"[WS] closed: {code}"))
    def on_message(ws, raw):
        msg = parse_message(raw)
        if msg:
            threading.Thread(target=handle_message, args=(msg, adapter), daemon=True).start()
    ws.on_message = on_message
    threading.Thread(target=lambda: [time.sleep(30), ws.send(json.dumps({"type":"ping"}))], daemon=True).start()
    ws.run_forever(ping_interval=30, ping_timeout=10)

def main():
    print(f"lark_bridge v0.1.0 | Bot: {cfg.app.bot_name}")
    cfg.ensure_dirs()
    if cfg.prefs.default_cwd == "~":
        cfg.prefs.default_cwd = os.path.expanduser("~")
    ws_loop(ClaudeAdapter())

if __name__ == "__main__":
    main()