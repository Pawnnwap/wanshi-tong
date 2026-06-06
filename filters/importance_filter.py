from core.base import Filter, ModuleResult
from core.opencode_client import run_opencode


class ImportanceFilter(Filter):
    name = "importance_filter"
    model = ""

    def filter(self, module_result: ModuleResult) -> ModuleResult:
        if module_result.error or not module_result.content.strip():
            return module_result

        prompt = (
            "你是一位新闻编辑，负责筛选高重要性新闻。\n\n"
            "请对以下新闻列表进行重要性评估和过滤。\n\n"
            "## 过滤标准\n"
            "- 只保留对全球经济、政策、市场有重大影响的新闻\n"
            "- 评分维度：影响范围（全球/区域/局部）、影响深度（结构性/周期性/事件性）、时效性\n"
            "- 评分 >= 7 的新闻保留，低于 7 分的丢弃\n\n"
            "## 输出要求\n"
            "- 用中文输出保留的新闻\n"
            "- 每条格式：**[标题]** | 摘要 | 来源 | **日期**\n"
            "- 如果全部不达标，输出\"本次搜索未发现重大新闻\"\n\n"
            "## 新闻列表\n\n"
            f"{module_result.content}"
        )

        filtered_content = run_opencode(
            prompt,
            model=self.model,
            timeout_s=300,
            task_name=f"filter_{module_result.name}",
        )
        return ModuleResult(
            name=module_result.name,
            title=module_result.title,
            content=filtered_content,
            model=module_result.model,
        )
