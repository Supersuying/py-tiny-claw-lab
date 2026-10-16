# internal/tools/list_files.py
# 扩展工具（不在四大原语之内）：列出工作区内的文件和目录。
import json

from internal.schema.message import ToolDefinition
from internal.tools.registry import BaseTool


class ListFilesTool(BaseTool):
    """列出工作区内指定目录的内容。"""

    def __init__(self, work_dir: str):
        self.work_dir = work_dir

    def name(self) -> str:
        return "list_files"

    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self.name(),
            description="列出工作区内指定目录中的文件和文件夹",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "相对于工作区的目录路径，默认是当前目录",
                    }
                },
                "required": [],
            },
        )

    def execute(self, args: str) -> str:
        try:
            input_args = json.loads(args or "{}")
        except json.JSONDecodeError as e:
            raise RuntimeError(f"参数解析失败: {e}") from e

        import os

        relative_path = input_args.get("path", ".")
        work_dir = os.path.abspath(self.work_dir)
        target = os.path.abspath(os.path.join(work_dir, relative_path))

        # 禁止访问工作区之外的位置
        if target != work_dir and not target.startswith(work_dir + os.sep):
            raise ValueError("不允许访问工作区之外的目录")

        if not os.path.exists(target):
            raise FileNotFoundError(f"目录不存在: {relative_path}")

        if not os.path.isdir(target):
            raise NotADirectoryError(f"目标不是目录: {relative_path}")

        entries = []
        for name in sorted(os.listdir(target), key=lambda n: n.lower()):
            item_path = os.path.join(target, name)
            item_type = "DIR" if os.path.isdir(item_path) else "FILE"
            entries.append(f"[{item_type}] {name}")

        if not entries:
            return "目录为空"

        return "\n".join(entries)