# internal/tools/registry.py
# 第 6 课：Registry 工具注册中心 —— 负责工具的注册、描述暴露与路由执行。
import logging
from abc import ABC, abstractmethod

from internal.schema.message import ToolCall, ToolDefinition, ToolResult

log = logging.getLogger(__name__)


class BaseTool(ABC):
    """所有工具必须实现的基础接口。"""

    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def definition(self) -> ToolDefinition:
        ...

    @abstractmethod
    def execute(self, args: str) -> str:
        """args 为原始 JSON 字符串，由工具自行解析；执行失败时抛出异常。"""
        ...


class Registry(ABC):
    """工具注册中心接口。"""

    @abstractmethod
    def register(self, tool: BaseTool):
        ...

    @abstractmethod
    def get_available_tools(self) -> list[ToolDefinition]:
        ...

    @abstractmethod
    def execute(self, call: ToolCall) -> ToolResult:
        ...


class RegistryImpl(Registry):
    """Registry 的默认实现：内部用一个 dict 存储 名称 -> 工具实例 的映射。"""

    def __init__(self):
        self.tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool):
        # 职责 1：动态挂载（Register）
        # 1. 通过 tool.name() 获取工具名称
        # 2. 如果名称已存在，打印警告："[Warning] 工具 'xxx' 已经被注册，将被覆盖。"
        # 3. 将工具存入 self.tools
        # 4. 打印日志："[Registry] 成功挂载工具: xxx"
        name = tool.name()
        if name in self.tools:
            log.warning("[Warning] 工具 '%s' 已经被注册，将被覆盖。", name)
        self.tools[name] = tool
        log.info("[Registry] 成功挂载工具: %s", name)

    def get_available_tools(self) -> list[ToolDefinition]:
        # 职责 2：描述暴露（Expose Schema）
        # 返回所有已挂载工具的 definition() 组成的列表
        return [tool.definition() for tool in self.tools.values()]

    def execute(self, call: ToolCall) -> ToolResult:
        # 职责 3：路由分发与执行（Dispatch & Execute）
        # 1. 根据 call.name 查找工具；找不到时返回 is_error=True 的 ToolResult，
        #    output 为 "Error: 系统中不存在名为 'xxx' 的工具。"
        # 2. 调用 tool.execute(call.arguments)
        # 3. 用 try/except 兜底：工具抛出的任何异常都转换为 is_error=True 的 ToolResult，
        #    output 为 "Error executing 工具名: 异常信息"，不能让引擎崩溃
        # 4. 执行成功时返回 is_error=False 的 ToolResult
        # 5. 所有 ToolResult 都必须带上正确的 tool_call_id
        tool = self.tools.get(call.name)
        if tool is None:
            return ToolResult(
                tool_call_id=call.id,
                output=f"Error: 系统中不存在名为 '{call.name}' 的工具。",
                is_error=True,
            )

        try:
            output = tool.execute(call.arguments)
        except Exception as exc:
            return ToolResult(
                tool_call_id=call.id,
                output=f"Error executing {call.name}: {exc}",
                is_error=True,
            )

        return ToolResult(
            tool_call_id=call.id,
            output=output,
            is_error=False,
        )


def new_registry() -> Registry:
    """构造函数。"""
    return RegistryImpl()