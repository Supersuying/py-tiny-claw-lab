# internal/tools/bash.py
# 第 6 课：终极执行原语 bash —— YOLO 哲学 + 四个 Harness 逻辑边界。
import json
import subprocess

from internal.schema.message import ToolDefinition
from internal.tools.registry import BaseTool


class BashTool(BaseTool):
    def __init__(self, work_dir: str):
        self.work_dir = work_dir

    def name(self) -> str:
        return "bash"

    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self.name(),
            description=(
                "在当前工作区执行任意的 bash 命令。支持链式命令(如 &&)。"
                "返回标准输出(stdout)和标准错误(stderr)。"
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "要执行的 bash 命令",
                    },
                },
                "required": ["command"],
            },
        )

    def execute(self, args: str) -> str:
        try:
            input_args = json.loads(args)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"参数解析失败: {e}") from e

        # bash 工具的 4 个 Harness 逻辑边界
        # 边界 1 工作区约束 + 边界 2 超时控制：
        # 用 ["bash", "-c", 命令] 在工作区内执行，timeout=30 防止引擎被挂死
        try:
            proc = subprocess.run(
                ["bash", "-c", input_args.get("command", "")],
                cwd=self.work_dir,
                capture_output=True,
                text=True,
                # Windows 中文系统默认按 GBK 解码，而 bash 输出是 UTF-8，
                # 必须显式指定 encoding，否则中文输出会触发 UnicodeDecodeError
                encoding="utf-8",
                timeout=30,
            )
        except subprocess.TimeoutExpired as e:
            # 超时也把已经产出的部分输出回传给模型
            partial = (e.stdout or "") + (e.stderr or "")
            return partial + "\n[警告: 命令执行超时(30s)，已被系统强制终止。]"

        output = (proc.stdout or "") + (proc.stderr or "")

        # 边界 3 自纠错回传：非零退出码不抛异常，把错误原样交给模型自行修正
        if proc.returncode != 0:
            return f"执行报错: exit status {proc.returncode}\n输出:\n{output}"

        # 输出为空时给出明确提示
        if output == "":
            return "命令执行成功，无终端输出。"

        # 边界 4 输出截断：超过 8000 字符只保留前 8000，守住 Context 生命线
        MAX_LEN = 8000
        if len(output) > MAX_LEN:
            return (
                output[:MAX_LEN]
                + f"\n\n...[终端输出过长，已截断至前 {MAX_LEN} 字节]..."
            )
        return output