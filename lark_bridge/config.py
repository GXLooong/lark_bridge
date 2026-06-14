"""Config: mirrors AppConfig + AppPreferences + BridgeConfig from schema.ts"""

import os, json, subprocess
from dataclasses import dataclass, field
from typing import Optional

APP_ID = "cli_aaa72c3bb938dbfc"
APP_SECRET = "NdjMOyPqxPIiZTD0q3GErdgny5BiIASd"
TENANT = "feishu"
LARK_CLI = "lark-cli"  # rely on PATH

@dataclass
class AppConfig:
    app_id: str = APP_ID
    app_secret: str = APP_SECRET
    tenant: str = TENANT
    bot_open_id: Optional[str] = None
    bot_name: str = "Claude_002"

@dataclass
class BridgePrefs:
    reply_mode: str = "text"       # "text"|"markdown"|"card"
    show_tool_calls: bool = True
    max_concurrent_runs: int = 5
    run_idle_timeout_minutes: int = 0
    require_mention_in_group: bool = True
    permission_mode: str = "bypassPermissions"
    default_cwd: str = "~"
    agent_stop_grace_ms: int = 5000

@dataclass
class BridgeConfig:
    app: AppConfig = field(default_factory=AppConfig)
    prefs: BridgePrefs = field(default_factory=BridgePrefs)
    config_dir: str = field(default_factory=lambda: os.path.expanduser("~/.lark_bridge"))
    sessions_path: str = ""
    def __post_init__(self):
        self.sessions_path = os.path.join(self.config_dir, "sessions.json")
    def ensure_dirs(self):
        os.makedirs(self.config_dir, exist_ok=True)

config = BridgeConfig()

# ── lark-cli helpers (subprocess, keychain auth) ────────────────

def lark_cli(*args, timeout=30) -> dict:
    """Run lark-cli with JSON output. Uses keychain auth (already configured)."""
    cmd = [LARK_CLI, "--format", "json"] + list(args)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0 and r.stderr:
        raise RuntimeError(f"lark-cli failed: {r.stderr[:200]}")
    try:
        return json.loads(r.stdout) if r.stdout.strip() else {}
    except json.JSONDecodeError:
        return {"raw": r.stdout}

def send_message(chat_id: str, text: str, msg_type: str = "text") -> dict:
    """Send message via lark-cli. Uses post format for rich text."""
    if msg_type == "post":
        return lark_cli("im", "+messages-send", "--chat-id", chat_id,
                        "--content", text, "--msg-type", "post")
    else:
        return lark_cli("im", "+messages-send", "--chat-id", chat_id,
                        "--text", text)
