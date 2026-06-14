"""Claude Code adapter — spawns claude, reads stream-json, yields AgentEvents."""

import json, subprocess, logging, os
from typing import Generator
from dataclasses import dataclass, field

logger = logging.getLogger("lark_bridge.claude")

CLAUDE_BINARY = "claude.cmd" if os.name == "nt" else "claude"

SYSTEM_PROMPT = """# lark-channel-bridge (Python port)

You are running inside lark-channel-bridge: bridging Feishu user messages to local Claude CLI.

## Reply format
Output your response directly as text. The bridge captures your text and sends it back to Feishu.
**Do not** use lark-cli to send messages — the bridge handles message delivery automatically.

## bridge_context
Each user message has a <bridge_context> block with chatId, senderName, etc.

## Formatting
Output text directly. Markdown formatting is supported.
"""

@dataclass
class AgentEvent:
    type: str
    delta: str = ""
    id: str = ""
    name: str = ""
    input: dict = field(default_factory=dict)
    output: str = ""
    termination_reason: str = "normal"

def translate_event(raw: dict) -> Generator[AgentEvent, None, None]:
    evt_type = raw.get("type", "")
    if evt_type == "system":
        yield AgentEvent(type="system")
        return
    if evt_type == "assistant":
        for block in raw.get("message", {}).get("content", []):
            btype = block.get("type", "")
            if btype == "text":
                t = block.get("text", "")
                if t: yield AgentEvent(type="text", delta=t)
            elif btype == "thinking":
                t = block.get("thinking", "")
                if t: yield AgentEvent(type="thinking", delta=t)
            elif btype == "tool_use":
                yield AgentEvent(type="tool_use", id=block.get("id",""),
                    name=block.get("name",""), input=block.get("input",{}))
        return
    if evt_type == "user":
        for block in raw.get("message", {}).get("content", []):
            if block.get("type") == "tool_result":
                output = block.get("content", "")
                if not isinstance(output, str): output = json.dumps(output)
                yield AgentEvent(type="tool_result", id=block.get("tool_use_id",""), output=output)
        return
    if evt_type == "result":
        yield AgentEvent(type="done", termination_reason=raw.get("subtype","normal"))

class ClaudeAdapter:
    def __init__(self, binary: str = CLAUDE_BINARY):
        self.binary = binary

    def build_prompt(self, user_text: str, chat_id: str, sender_name: str, sender_id: str) -> str:
        ctx = json.dumps({"chatId":chat_id,"chatType":"p2p","senderId":sender_id,
                          "senderName":sender_name,"senderType":"user"})
        return f"<bridge_context>\n{ctx}\n</bridge_context>\n\n{user_text}"

    def run(self, prompt: str, cwd: str = None,
            permission_mode: str = "bypassPermissions") -> Generator[AgentEvent, None, None]:
        args = [self.binary, "-p", prompt, "--output-format", "stream-json",
                "--verbose", "--permission-mode", permission_mode,
                "--append-system-prompt", SYSTEM_PROMPT]
        work_dir = cwd or os.path.expanduser("~")
        proc = subprocess.Popen(args, cwd=work_dir, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, encoding="utf-8")
        logger.info(f"claude pid={proc.pid} cwd={work_dir}")
        line_count = 0
        try:
            for line in proc.stdout:
                line = line.strip()
                if not line: continue
                line_count += 1
                try:
                    yield from translate_event(json.loads(line))
                except json.JSONDecodeError:
                    pass
        finally:
            code = proc.wait()
            logger.info(f"claude exit: pid={proc.pid} code={code} lines={line_count}")