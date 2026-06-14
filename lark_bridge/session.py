"""Session store — mirrors session/store.ts. Per-chat sessions persisted to JSON."""

import json, os, logging, time
from typing import Dict, Optional
from .config import config as cfg

logger = logging.getLogger("lark_bridge.session")

class Session:
    def __init__(self, scope_id, chat_type="p2p", cwd="~", permission_mode="bypassPermissions",
                 is_running=False, last_active=0, created_at=0, message_count=0):
        self.scope_id = scope_id; self.chat_type = chat_type; self.cwd = cwd
        self.permission_mode = permission_mode; self.is_running = is_running
        self.last_active = last_active or time.time()
        self.created_at = created_at or time.time()
        self.message_count = message_count

class SessionStore:
    def __init__(self, path=None):
        self.path = path or os.path.join(cfg.config_dir, "sessions.json")
        self._s: Dict[str, Session] = {}
        self._load()

    def _load(self):
        try:
            with open(self.path) as f:
                for k, v in json.load(f).items():
                    self._s[k] = Session(k, **{kk: vv for kk, vv in v.items() if kk != "scope_id"})
        except (FileNotFoundError, json.JSONDecodeError): pass

    def _save(self):
        cfg.ensure_dirs()
        t = self.path + ".tmp"
        with open(t, "w") as f:
            json.dump({k: v.__dict__ for k, v in self._s.items()}, f, indent=2)
        os.replace(t, self.path)

    def get(self, scope_id):
        if scope_id not in self._s:
            self._s[scope_id] = Session(scope_id)
            self._save()
        return self._s[scope_id]

    def update(self, scope_id, **kw):
        s = self.get(scope_id)
        for k, v in kw.items():
            if hasattr(s, k): setattr(s, k, v)
        s.last_active = time.time()
        self._save()

    def reset(self, scope_id):
        self._s.pop(scope_id, None); self._save()

sessions = SessionStore()
