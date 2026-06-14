"""Session management — per-chat sessions persisted to JSON."""

import json, os, logging, time
from dataclasses import dataclass
from typing import Dict, Optional
from .config import config as cfg

logger = logging.getLogger("lark_bridge.session")

@dataclass
class Session:
    scope_id: str
    chat_type: str = "p2p"
    cwd: str = "~"
    permission_mode: str = "bypassPermissions"
    is_running: bool = False
    last_active: float = 0.0
    created_at: float = 0.0
    message_count: int = 0

    def touch(self):
        self.last_active = time.time()

class SessionStore:
    def __init__(self, path: Optional[str] = None):
        self.path = path or os.path.join(cfg.config_dir, "sessions.json")
        self._sessions: Dict[str, Session] = {}
        self._load()

    def _load(self):
        try:
            with open(self.path, "r") as f:
                for k, v in json.load(f).items():
                    self._sessions[k] = Session(**v)
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    def _save(self):
        cfg.ensure_dirs()
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump({k: v.__dict__ for k, v in self._sessions.items()}, f, indent=2)
        os.replace(tmp, self.path)

    def get(self, scope_id: str) -> Session:
        if scope_id not in self._sessions:
            self._sessions[scope_id] = Session(scope_id=scope_id, created_at=time.time(), last_active=time.time())
            self._save()
        return self._sessions[scope_id]

    def update(self, scope_id: str, **kwargs):
        s = self.get(scope_id)
        for k, v in kwargs.items():
            if hasattr(s, k): setattr(s, k, v)
        s.touch()
        self._save()

    def reset(self, scope_id: str):
        self._sessions.pop(scope_id, None)
        self._save()

sessions = SessionStore()