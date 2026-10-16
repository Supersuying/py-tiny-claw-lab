# internal/provider/openai.py
# OpenAI 兼容协议的 Provider 实现，DeepSeek 复用同一套协议。

import os

import openai

from internal.provider.interface import LLMProvider
from internal.schema.message import (
    Message,
    ToolCall,
    ROLE_ASSISTANT,
    ROLE_SYSTEM,
    ROLE_USER,
)


class OpenAIProvider(LLMProvider):
    def __init__(self, client: openai.OpenAI, model: str):
        self.client = client
        self.model = model

    def generate(self, msgs: list[Message], available_tools=None) -> Message:
        # 第 1 步：内部 Message -> OpenAI 消息格式
        openai_msgs = []

        for msg in msgs:
            if msg.role == ROLE_SYSTEM:
                openai_msgs.append({"role": "system", "content": msg.content})

            elif msg.role == ROLE_USER:
                if msg.tool_call_id != "":
                    # 工具执行结果在 OpenAI 协议中是独立的 "tool" 角色消息
                    openai_msgs.append({
                        "role": "tool",
                        "content": msg.content,
                        "tool_call_id": msg.tool_call_id,
                    })
                else:
                    openai_msgs.append({"role": "user", "content": msg.content})

            elif msg.role == ROLE_ASSISTANT:
                ast_param: dict = {"role": "assistant"}

                if msg.content != "":
                    ast_param["content"] = msg.content

                if len(msg.tool_calls) > 0:
                    tool_calls = []
                    for tc in msg.tool_calls:
                        tool_calls.append({
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                # OpenAI 协议中 arguments 本身就是 JSON 字符串
                                "arguments": tc.arguments,
                            },
                        })
                    ast_param["tool_calls"] = tool_calls

                openai_msgs.append(ast_param)

        # 第 2 步：ToolDefinition -> OpenAI tools 格式
        openai_tools = []
        for tool_def in available_tools or []:
            params_schema = tool_def.input_schema if isinstance(tool_def.input_schema, dict) else {}
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": tool_def.name,
                    "description": tool_def.description,
                    "parameters": params_schema,
                },
            })

        params = {
            "model": self.model,
            "messages": openai_msgs,
        }
        if openai_tools:
            params["tools"] = openai_tools
            params["tool_choice"] = "auto"

        ##########################  调用大模型执行  ###############################
        try:
            resp = self.client.chat.completions.create(**params)
        except Exception as e:
            raise RuntimeError(f"OpenAI 兼容 API 请求失败: {e}") from e

        if len(resp.choices) == 0:
            raise RuntimeError("API 返回了空的 Choices")

        # 第 3 步：模型响应 -> 内部 Message
        choice = resp.choices[0].message
        result_msg = Message(
            role=ROLE_ASSISTANT,
            content=choice.content or "",
        )

        for tc in choice.tool_calls or []:
            if tc.type == "function":
                result_msg.tool_calls.append(ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=tc.function.arguments,
                ))

        return result_msg


def new_deepseek_provider(model: str) -> OpenAIProvider:
    """DeepSeek 官方 API。

    DeepSeek 走的同样是 OpenAI Chat Completions 兼容协议，
    所以上面那套消息与工具翻译逻辑可以原样复用，只需换 Base URL 与密钥。
    可用模型：deepseek-v4-flash（快、便宜）、deepseek-v4-pro（更强）。
    """
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError(
            "请设置 DEEPSEEK_API_KEY 环境变量"
            "（也可以写进项目根目录的 .env 文件，会被自动加载）"
        )
    base_url = "https://api.deepseek.com/v1"
    return OpenAIProvider(
        client=openai.OpenAI(api_key=api_key, base_url=base_url),
        model=model,
    )