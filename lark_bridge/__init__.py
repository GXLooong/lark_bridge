"""
lark_bridge — Python port of lark-channel-bridge core logic.
Skips card streaming (known-broken on Windows) and exec-provider (Go os.Stat issue).
"""
__version__ = "0.1.0"