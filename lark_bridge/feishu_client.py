"""Feishu API client + WebSocket event stream."""

import json, time, logging
from urllib.request import Request, urlopen
from urllib.error import URLError
from .config import config as cfg

logger = logging.getLogger("lark_bridge.feishu")
BASE = "https://open.feishu.cn/open-apis"

def _req(method, path, body=None, token=None):
    url = BASE + path
    data = json.dumps(body).encode() if body else None
    req = Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())

_token_cache = {"token": None, "expires_at": 0}

def get_tenant_token():
    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires_at"]:
        return _token_cache["token"]
    r = _req("POST", "/auth/v3/tenant_access_token/internal",
             {"app_id": cfg.app.app_id, "app_secret": cfg.app.app_secret})
    _token_cache["token"] = r["tenant_access_token"]
    _token_cache["expires_at"] = now + r.get("expire", 3600) - 60
    return _token_cache["token"]

def send_reply(msg_id: str, content_str: str, msg_type: str = "post"):
    token = get_tenant_token()
    body = {"content": content_str, "msg_type": msg_type}
    return _req("POST", f"/im/v1/messages/{msg_id}/reply", body, token)

def connect_ws():
    token = get_tenant_token()
    r = _req("POST", "/ws/v1/connect", {}, token)
    ws_url = r.get("data", {}).get("url", "")
    if not ws_url:
        raise RuntimeError(f"Failed to get WS URL: {r}")
    return ws_url

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