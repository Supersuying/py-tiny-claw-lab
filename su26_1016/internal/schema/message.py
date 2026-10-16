# internal/schema/message.py
# 定义引擎内部流转的统一消息格式。

from dataclasses import dataclass, field


ROLE_SYSTEM = "system"
ROLE_USER = "user"
ROLE_ASSISTANT = "assistant"
ROLE_TOOL = "tool"


@dataclass
class ToolCall:
    """模型发起的一次工具调用请求。"""

    id: str = ""
    name: str = ""
    arguments: str = ""


@dataclass
class Message:
    """一条上下文消息。"""

    role: str = ""
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str = ""


@dataclass
class ToolResult:
    """一次工具执行的结果。"""

    tool_call_id: str = ""
    output: str = ""
    is_error: bool = False


@dataclass
class ToolDefinition:
    """暴露给模型的工具定义。"""

    name: str = ""
    description: str = ""
    input_schema: dict | None = None