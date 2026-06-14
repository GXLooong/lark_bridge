"""Configuration & credentials."""

import os
from dataclasses import dataclass, field
from typing import Optional

# Override these with your own Feishu app credentials
APP_ID = "cli_xxx"
APP_SECRET = "xxx"
TENANT = "feishu"

@dataclass
class AppConfig:
    app_id: str = APP_ID
    app_secret: str = APP_SECRET
    tenant: str = TENANT
    bot_open_id: Optional[str] = None
    bot_name: str = "Claude"

@dataclass
class BridgePrefs:
    reply_mode: str = "text"
    show_tool_calls: bool = True
    max_concurrent_runs: int = 5
    default_cwd: str = "~"
    permission_mode: str = "bypassPermissions"

@dataclass
class BridgeConfig:
    app: AppConfig = field(default_factory=AppConfig)
    prefs: BridgePrefs = field(default_factory=BridgePrefs)
    config_dir: str = field(default_factory=lambda: os.path.expanduser("~/.lark_bridge"))

    def ensure_dirs(self):
        os.makedirs(self.config_dir, exist_ok=True)

config = BridgeConfig()