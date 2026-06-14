# lark_bridge

Python port of [lark-channel-bridge](https://github.com/zarazhangrui/lark-coding-agent-bridge) core logic. Bridges Feishu/Lark messenger with local Claude Code CLI.

## Implemented Features

| Feature | Status |
|---|---|
| HTTP polling mode (receives Feishu messages, no external deps) | ✅ |
| WebSocket mode (requires `websocket-client`) | ✅ optional |
| Claude Code integration (`--output-format stream-json` + `--resume`) | ✅ |
| Text reply mode (Feishu `post` format with code blocks) | ✅ |
| Session persistence (JSON, per-chat) | ✅ |
| Conversation context continuity (`session_id` → `--resume`) | ✅ |
| Slash commands: `/help`, `/status`, `/new`, `/config`, `/stop`, `/cd` | ✅ |

## What's NOT implemented (deliberately skipped)

- `card` / `markdown` reply modes — broken on Windows due to `@larksuite/channel` SDK bug (Error 230099: `cardid is invalid`)
- Codex adapter — Claude only
- Multi-profile, daemon management, document comments, advanced access control

## Quick Start

```bash
cd lark_bridge
PYTHONPATH=. python -m lark_bridge
```

Prerequisites:
- Python 3.9+
- Claude Code CLI installed (`claude` on PATH)
- Feishu app with `im:message` permission
- Edit `lark_bridge/config.py` to set `APP_ID` and `APP_SECRET`

Optional: `pip install websocket-client` for WebSocket mode (falls back to HTTP polling otherwise).

## Architecture

```
lark_bridge/
├── main.py              # Entry point — WS/poll dispatch, message handler
├── config.py            # AppConfig, BridgePrefs, lark-cli keychain helpers
├── feishu_client.py     # Token cache, WS connect, message parse, reply API
├── claude_adapter.py    # Claude spawn, stream-json parser, translate_event
├── session.py           # SessionStore — per-chat sessions (JSON, session_id)
├── commands.py          # Slash commands (/help /status /new /config /stop /cd)
├── reply.py             # RunState + reduce(), text→post renderer
└── __main__.py          # python -m lark_bridge entry
```

## License

MIT
