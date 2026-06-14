# lark_bridge

Python port of lark-channel-bridge core logic. Bridges Feishu/Lark messenger with local Claude Code CLI.

## Features (mirrored from lark-channel-bridge)

- **WebSocket** (when `websocket-client` available) or **HTTP polling** fallback
- **Text reply mode** — collects Claude output, sends as Feishu `post` format (code blocks supported)
- **Session management** — per-chat sessions persisted to `~/.lark_bridge/sessions.json`
- **Slash commands**: `/help`, `/status`, `/new`, `/config`, `/stop`, `/cd`
- **Claude adapter** — spawns `claude -p --output-format stream-json`, parses AgentEvents

## What's deliberately skipped

- `card` / `markdown` reply mode (card streaming broken on Windows due to `@larksuite/channel` SDK bug — `cardid is invalid` error 230099)
- `exec` provider for lark-cli (Go binary `os.Stat` returns 0666 on Windows regardless of ACL)

## Quick Start

```bash
# Clone
cd lark_bridge

# Run (no dependencies needed for polling mode)
PYTHONPATH=. python -m lark_bridge

# Or with WebSocket support (optional)
pip install websocket-client
```

## Configuration

Edit `lark_bridge/config.py`:
- `APP_ID` / `APP_SECRET` — your Feishu app credentials
- `TENANT` — `"feishu"` (China) or `"lark"` (global)
- `BridgePrefs.reply_mode` — `"text"` (default)

## Architecture

```
lark_bridge/
  __init__.py          # Package init
  __main__.py          # python -m lark_bridge entry
  main.py              # Main loop, WS/poll dispatch
  config.py            # App config & preferences
  feishu_client.py     # Feishu API (HTTP + WS + token)
  claude_adapter.py    # Claude spawn + stream-json parser
  session.py           # Per-chat session store
  commands.py          # Slash commands (/help, /status, etc.)
  reply.py             # Reply formatting (text→post)
```

## License

MIT
