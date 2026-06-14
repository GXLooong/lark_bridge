"""Feishu client: token, WS connect, message parse, send via lark-cli or API."""

import json, time, logging, threading
from urllib.request import Request, urlopen
from .config import config as cfg, lark_cli

logger = logging.getLogger("lark_bridge.feishu")
BASE = "https://open.feishu.cn/open-apis"

def _api(method, path, body=None, token=None):
    url = BASE + path
    data = json.dumps(body).encode() if body else None
    req = Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token: req.add_header("Authorization", f"Bearer {token}")
    with urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())

_token = {"v": None, "exp": 0}

def get_tenant_token():
    now = time.time()
    if _token["v"] and now < _token["exp"]:
        return _token["v"]
    r = _api("POST", "/auth/v3/tenant_access_token/internal",
             {"app_id": cfg.app.app_id, "app_secret": cfg.app.app_secret})
    _token["v"] = r["tenant_access_token"]
    _token["exp"] = now + r.get("expire", 3600) - 60
    return _token["v"]

def send_reply(msg_id, content_str, msg_type="post"):
    """Reply via Feishu API directly."""
    token = get_tenant_token()
    body = {"content": content_str, "msg_type": msg_type}
    return _api("POST", f"/im/v1/messages/{msg_id}/reply", body, token)

def send_text_via_lark(text: str, chat_id: str) -> bool:
    """Send a plain text message via lark-cli (uses keychain)."""
    try:
        lark_cli("im", "+messages-send", "--chat-id", chat_id, "--text", text, timeout=20)
        return True
    except Exception as e:
        logger.error(f"lark-cli send: {e}")
        return False

def connect_ws():
    token = get_tenant_token()
    r = _api("POST", "/ws/v1/connect", {}, token)
    return r.get("data", {}).get("url", "")

def parse_message(raw):
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError:
        return None
    if data.get("type") == "message" and "data" in data:
        inner = data["data"]
        if inner.get("event_type") == "im.message.receive_v1":
            msg = inner.get("message", {})
            if msg.get("message_type") != "text":
                return None
            return {
                "message_id": msg.get("message_id"),
                "chat_id": inner.get("chat_id", ""),
                "chat_type": inner.get("chat_type", "p2p"),
                "sender_id": (inner.get("sender", {}).get("sender_id", {}) or {}).get("open_id", ""),
                "sender_name": (inner.get("sender", {}) or {}).get("sender_name", ""),
                "text": json.loads(msg.get("content", "{}")).get("text", ""),
            }
    return None

CHAT_ID = "oc_10967462b13aa3fb8648e1571871859c"

def get_messages(page_size=5):
    """Get recent messages from the P2P chat."""
    token = get_tenant_token()
    path = f"/im/v1/messages?container_id_type=chat&container_id={CHAT_ID}&page_size={page_size}&sort_type=ByCreateTimeDesc"
    return _api("GET", path, None, token)
