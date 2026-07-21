from dataclasses import replace

from core.base import Filter, ModuleResult
from core.opencode_client import run_opencode


class ImportanceFilter(Filter):
    name = "importance_filter"
    model = ""

    STRUCTURED_MODULES: dict[str, str] = {}

    @classmethod
    def _build_prompt(cls, module_result: ModuleResult) -> str:
        if instructions := cls.STRUCTURED_MODULES.get(module_result.name):
            return f"{instructions}\n\n原始数据：\n{module_result.content}"
        return (
            "筛选高重要性新闻：只保留对全球/区域经济、政策或市场有显著影响的条目；"
            "局部、重复、低影响或日期不明的丢弃。\n"
            "输出中文，每条格式：**[标题]** | 摘要 | 来源 | **日期**。\n"
            "若无保留项，输出：本次搜索未发现重大新闻\n\n"
            f"新闻列表：\n{module_result.content}"
        )

    def filter(self, module_result: ModuleResult) -> ModuleResult:
        if (
            module_result.authoritative
            or module_result.error
            or not module_result.content.strip()
        ):
            return module_result

        filtered_content = run_opencode(
            self._build_prompt(module_result),
            model=self.model,
            idle_timeout_s=300,
            task_name=f"filter_{module_result.name}",
        )
        return replace(module_result, content=filtered_content)
