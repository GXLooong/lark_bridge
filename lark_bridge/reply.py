"""Reply — mirrors card/run-state.ts reduce() + text-renderer.ts + post format."""

import json, logging
from .claude_adapter import AgentEvent
from .feishu_client import send_reply

logger = logging.getLogger("lark_bridge.reply")

class RunState:
    """Accumulated agent output. Mirrors RunState + reduce()."""
    def __init__(self):
        self.blocks = []       # text blocks
        self.reasoning = ""    # thinking content
        self.tool_count = 0
        self.footer = "running"
        self.terminal = "running"  # running | normal | failed | interrupted

    def reduce(self, evt: AgentEvent):
        if evt.type == "text":
            self.blocks.append(evt.delta)
            self.footer = "streaming"
        elif evt.type == "thinking":
            self.reasoning += evt.delta
        elif evt.type == "tool_use":
            self.tool_count += 1
            self.footer = "tool_running"
        elif evt.type == "tool_result":
            self.footer = "tool_running"
        elif evt.type == "done":
            self.terminal = "normal"
            self.footer = evt.termination_reason
        elif evt.type == "error":
            self.terminal = "failed"

def render_text(state: RunState) -> str:
    return "".join(state.blocks)

def text_to_post_cards(title: str, body: str) -> str:
    """Convert text to Feishu post format with code block support."""
    paragraphs = []
    in_code, buf, lang = False, [], ""
    for line in body.split("\n"):
        if line.startswith("```"):
            if in_code:
                paragraphs.append([{"tag":"code_block","language":lang,"text":"\n".join(buf)}])
                buf, in_code, lang = [], False, ""
            else:
                lang = line[3:].strip().lower() or "plaintext"
                in_code = True
            continue
        if in_code:
            buf.append(line); continue
        if line.strip():
            paragraphs.append([{"tag":"text","text":line}])
    if in_code:
        paragraphs.append([{"tag":"code_block","language":lang,"text":"\n".join(buf)}])
    return json.dumps({"zh_cn":{"title":title[:60],"content":paragraphs}})

def send_text_reply(msg_id: str, state: RunState) -> bool:
    body = render_text(state)
    if not body.strip():
        logger.warning(f"empty body for {msg_id[-12:]}")
        return False
    title = body.split("\n")[0][:60] or "reply"
    content = text_to_post_cards(title, body)
    try:
        r = send_reply(msg_id, content, "post")
        logger.info(f"reply {msg_id[-12:]} code={r.get('code','?')}")
        return r.get("code") == 0
    except Exception as e:
        logger.error(f"reply failed: {e}")
        return False
