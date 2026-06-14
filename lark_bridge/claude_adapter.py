"""Claude adapter — mirrors adapter.ts + stream-json.ts."""

import json, subprocess, logging, os
from dataclasses import dataclass, field
from typing import Generator

logger = logging.getLogger("lark_bridge.claude")

CLAUDE = "claude.cmd" if os.name == "nt" else "claude"

SYSTEM_PROMPT = """# lark-channel-bridge (Python port)

You are running inside lark-channel-bridge: bridging Feishu/Lark user messages to local Claude CLI.

## Reply format
Output your response directly as text. The bridge captures your text and sends it back to Feishu.
**Do not** use lark-cli to send messages — the bridge handles message delivery automatically.

## bridge_context
Each user message starts with a <bridge_context> block containing JSON with:
- chatId, chatType, senderId, senderName
- The block is for your context only — do not copy or render it in your reply.

## Formatting
Use markdown freely. Code blocks, lists, tables all render correctly in Feishu.
"""

@dataclass
class AgentEvent:
    type: str  # text, thinking, tool_use, tool_result, system, done, error
    delta: str = ""
    id: str = ""; name: str = ""
    input: dict = field(default_factory=dict)
    output: str = ""
    termination_reason: str = "normal"

def translate_event(raw: dict) -> Generator[AgentEvent, None, None]:
    t = raw.get("type", "")
    if t == "system":
        yield AgentEvent(type="system"); return
    if t == "assistant":
        for b in raw.get("message", {}).get("content", []):
            bt = b.get("type", "")
            if bt == "text" and b.get("text"):
                yield AgentEvent(type="text", delta=b["text"])
            elif bt == "thinking" and b.get("thinking"):
                yield AgentEvent(type="thinking", delta=b["thinking"])
            elif bt == "tool_use":
                yield AgentEvent(type="tool_use", id=b.get("id",""), name=b.get("name",""), input=b.get("input",{}))
        return
    if t == "user":
        for b in raw.get("message", {}).get("content", []):
            if b.get("type") == "tool_result":
                out = b.get("content","")
                if not isinstance(out, str): out = json.dumps(out)
                yield AgentEvent(type="tool_result", id=b.get("tool_use_id",""), output=out)
        return
    if t == "result":
        yield AgentEvent(type="done", termination_reason=raw.get("subtype","normal"))

class ClaudeAdapter:
    def __init__(self): self.binary = CLAUDE

    def build_prompt(self, text, chat_id, sender_name, sender_id):
        ctx = json.dumps({"chatId":chat_id,"chatType":"p2p","senderId":sender_id,
                          "senderName":sender_name,"senderType":"user"})
        return f"<bridge_context>\n{ctx}\n</bridge_context>\n\n{text}"

    def run(self, prompt, cwd=None, permission_mode="bypassPermissions") -> Generator[AgentEvent, None, None]:
        args = [self.binary, "-p", prompt, "--output-format", "stream-json",
                "--verbose", "--permission-mode", permission_mode,
                "--append-system-prompt", SYSTEM_PROMPT]
        work_dir = cwd or os.path.expanduser("~")
        proc = subprocess.Popen(args, cwd=work_dir, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, encoding="utf-8")
        logger.info(f"claude pid={proc.pid}")
        n = 0
        try:
            for line in proc.stdout:
                line = line.strip()
                if not line: continue
                n += 1
                try: yield from translate_event(json.loads(line))
                except json.JSONDecodeError: pass
        finally:
            code = proc.wait()
            logger.info(f"claude exit pid={proc.pid} code={code} lines={n}")
