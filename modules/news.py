from typing import Mapping

from core.base import Module


class NewsModule(Module):
    """Shared bilingual prompt policy for date-sensitive news collectors."""

    search_scope_zh = ""
    search_scope_en = ""
    coverage_zh = ""
    coverage_en = ""
    sources_zh = ""
    sources_en = ""
    empty_label_zh = ""
    empty_label_en = ""

    def get_prompt_templates(self) -> Mapping[str, str]:
        source_rule_zh = f"\n- 优先来源：{self.sources_zh}。" if self.sources_zh else ""
        source_rule_en = f"\n- Prefer sources: {self.sources_en}." if self.sources_en else ""
        return {
            "zh": (
                f"搜索{{yesterday_cn}}或{{today_cn}}发布的{self.search_scope_zh}新闻。\n\n"
                "要求：\n"
                "- 只收录发布日期为{yesterday_cn}或{today_cn}的新闻；更早、未来或日期不明的直接丢弃。\n"
                "- 优先使用结构化新闻工具，其次 websearch/RSS 交叉核对来源与日期。\n"
                f"- 覆盖{self.coverage_zh}。"
                f"{source_rule_zh}\n\n"
                "输出中文。每条格式：**[标题]** | 1句摘要 | 来源 | **YYYY年M月D日**\n"
                f"如无合格新闻，输出：未找到{{yesterday_short_cn}}-{{today_short_cn}}的{self.empty_label_zh}新闻\n"
                "当前日期：{today_cn}"
            ),
            "en": (
                f"Search for {self.search_scope_en} news published on {{yesterday_en}} or {{today_en}}.\n\n"
                "Rules:\n"
                "- Include only items published on {yesterday_en} or {today_en}; discard older, future, or undated items.\n"
                "- Prefer structured news tools, then websearch/RSS to verify source and date.\n"
                f"- Cover {self.coverage_en}."
                f"{source_rule_en}\n\n"
                "Output in English. Format each item: **[Title]** | one-sentence summary | Source | **Month D, YYYY**\n"
                f"If none qualify, output: No {self.empty_label_en} news found for "
                "{month_en} {yesterday_day}-{today_day}, {year}\n"
                "Current date: {today_en}"
            ),
        }
