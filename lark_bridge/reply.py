"""Reply formatting — text → Feishu post (rich text) with code blocks."""

import json, logging
from .claude_adapter import AgentEvent
from .feishu_client import send_reply

logger = logging.getLogger("lark_bridge.reply")

class RunState:
    def __init__(self):
        self.blocks = []
        self.reasoning = ""
        self.footer = "running"
        self.terminal = "running"

    def reduce(self, evt: AgentEvent):
        if evt.type == "text":
            self.blocks.append(evt.delta)
            self.footer = "streaming"
        elif evt.type == "thinking":
            self.reasoning += evt.delta
        elif evt.type == "tool_use":
            self.footer = "tool_running"
        elif evt.type == "done":
            self.terminal = evt.termination_reason
            self.footer = evt.termination_reason
        elif evt.type == "error":
            self.terminal = "failed"

def render_text(state: RunState) -> str:
    return "".join(state.blocks)

def text_to_post(title: str, body: str) -> str:
    lines = body.split("\n")
    paragraphs = []
    in_code, code_buf, code_lang = False, [], ""
    for line in lines:
        if line.startswith("```"):
            if in_code:
                paragraphs.append([{"tag":"code_block","language":code_lang,"text":"\n".join(code_buf)}])
                code_buf, in_code, code_lang = [], False, ""
            else:
                code_lang = line[3:].strip().lower() or "plaintext"
                in_code = True
            continue
        if in_code:
            code_buf.append(line)
            continue
        if line.strip():
            paragraphs.append([{"tag":"text","text":line}])
    if in_code:
        paragraphs.append([{"tag":"code_block","language":code_lang,"text":"\n".join(code_buf)}])
    return json.dumps({"zh_cn":{"title":title[:60],"content":paragraphs}})

def send_text_reply(msg_id: str, state: RunState) -> bool:
    body = render_text(state)
    if not body.strip():
        return False
    title = body.split("\n")[0][:60] or "reply"
    content = text_to_post(title, body)
    try:
        r = send_reply(msg_id, content, "post")
        logger.info(f"reply sent: {msg_id[-12:]} code={r.get('code','?')}")
        return r.get("code") == 0
    except Exception as e:
        logger.error(f"reply failed: {e}")
        return False