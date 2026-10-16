# internal/engine/loop.py
# 第 3 章：引入"慢思考"(Thinking Phase)：先剥夺工具让模型规划，再开放工具让它行动。

import logging

from internal.provider.interface import LLMProvider
from internal.schema.message import (
    Message,
    ROLE_SYSTEM,
    ROLE_USER,
)
from internal.tools.registry import Registry

log = logging.getLogger(__name__)

# 防止模型陷入无休止的工具调用，超过最大轮次强制结束
MAX_TURNS = 8


class AgentEngine:
    def __init__(
        self,
        provider: LLMProvider,
        registry: Registry,
        work_dir: str,
        enable_thinking: bool,
    ):
        self.provider = provider
        self.registry = registry
        self.work_dir = work_dir
        self.enable_thinking = enable_thinking

    def run(self, user_prompt: str) -> None:
        log.info("[Engine] 引擎启动，锁定工作区: %s", self.work_dir)
        log.info("[Engine] 慢思考模式 (Thinking Phase): %s", self.enable_thinking)

        context_history: list[Message] = [
            Message(
                role=ROLE_SYSTEM,
                content=(
                    "You are py-tiny-claw, an expert coding assistant. "
                    "You have full access to tools in the workspace."
                ),
            ),
            Message(
                role=ROLE_USER,
                content=user_prompt,
            ),
        ]

        turn_count = 0

        while True:
            turn_count += 1
            log.info("\n========== [Turn %d] 开始 ==========", turn_count)

            if turn_count > MAX_TURNS:
                log.warning("[Engine] 超过最大轮次 %d，强制结束", MAX_TURNS)
                break

            available_tools = self.registry.get_available_tools()

            # ================= Phase 1: Thinking =================
            if self.enable_thinking:
                log.info("[Engine][Phase 1] 剥夺工具访问权，强制进入慢思考与规划阶段...")
                think_resp = self.provider.generate(context_history, None)
                if think_resp.content != "":
                    print(f"🧠 [内部思考 Trace]: {think_resp.content}")
                    context_history.append(think_resp)

            # ================= Phase 2: Action =================
            log.info("[Engine][Phase 2] 恢复工具挂载，等待模型采取行动...")
            action_resp = self.provider.generate(context_history, available_tools)
            context_history.append(action_resp)

            if action_resp.content != "":
                print(f"🤖 [对外回复]: {action_resp.content}")

            # 模型没有调用工具，说明任务完成
            if len(action_resp.tool_calls) == 0:
                log.info("[Engine] 模型未请求调用工具，任务宣告完成。")
                break

            log.info("[Engine] 模型请求调用 %d 个工具...", len(action_resp.tool_calls))

            # ================= Act + Observe =================
            for tool_call in action_resp.tool_calls:
                log.info(
                    "  -> 🛠️ 执行工具: %s, 参数: %s",
                    tool_call.name,
                    tool_call.arguments,
                )

                result = self.registry.execute(tool_call)

                if result.is_error:
                    log.info("  -> ❌ 工具执行报错: %s", result.output)
                else:
                    log.info("  -> ✅ 工具执行成功 (返回 %d 字节)", len(result.output))

                # 工具执行结果以 user 消息的形式回填上下文，
                # 携带 tool_call_id，Provider 会把它翻译成协议要求的 tool 角色消息
                context_history.append(
                    Message(
                        role=ROLE_USER,
                        content=result.output,
                        tool_call_id=result.tool_call_id,
                    )
                )

        log.info("[Engine] 引擎结束，共执行 %d 轮", turn_count)