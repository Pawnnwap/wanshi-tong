from datetime import datetime, timedelta
import re

from core.base import Analyzer, ModuleResult
from core.opencode_client import run_opencode


class DeepAnalyzer(Analyzer):
    name = "deep_analyzer"
    model = ""
    REQUIRED_SECTIONS = ("核心主题", "传导链", "一致与背离", "风险与机会", "综合判断")

    @classmethod
    def _missing_sections(cls, text: str) -> list[str]:
        missing = []
        for section in cls.REQUIRED_SECTIONS:
            match = re.search(rf"【{re.escape(section)}】", text)
            if not match:
                missing.append(section)
                continue
            next_match = re.search(r"\n#{1,3}\s*\d+[.、]?\s*【", text[match.end():])
            section_body = text[match.end():match.end() + next_match.start()] if next_match else text[match.end():]
            section_body = re.sub(r"^[^\n]*", "", section_body, count=1).strip()
            if len(section_body) < 6:
                missing.append(section)
        return missing

    @staticmethod
    def _alignment_section_is_weak(text: str) -> bool:
        match = re.search(r"【一致与背离】", text)
        if not match:
            return True
        next_match = re.search(r"\n#{1,3}\s*\d+[.、]?\s*【", text[match.end():])
        section_body = text[match.end():match.end() + next_match.start()] if next_match else text[match.end():]
        consistency_body = DeepAnalyzer._subsection_body(
            section_body,
            r"一致信号",
            r"(背离|张力|矛盾)",
        )
        divergence_body = DeepAnalyzer._subsection_body(
            section_body,
            r"(背离|张力|矛盾)",
            r"一致信号",
        )
        return (
            DeepAnalyzer._subsection_is_empty(consistency_body)
            or DeepAnalyzer._subsection_is_empty(divergence_body)
            or DeepAnalyzer._subsection_item_count(consistency_body) < 2
            or DeepAnalyzer._subsection_item_count(divergence_body) < 2
        )

    @staticmethod
    def _subsection_body(section_body: str, start_pattern: str, stop_pattern: str) -> str:
        start = re.search(rf"(^|\n)#+\s*.*{start_pattern}.*\n|(^|\n).{{0,8}}{start_pattern}.{{0,8}}[:：]", section_body)
        if not start:
            return ""
        body = section_body[start.end():]
        stop = re.search(rf"(^|\n)#+\s*.*{stop_pattern}.*\n|(^|\n).{{0,8}}{stop_pattern}.{{0,8}}[:：]", body)
        return body[:stop.start()] if stop else body

    @staticmethod
    def _subsection_is_empty(body: str) -> bool:
        body = re.sub(r"```.*?```", "", body, flags=re.S)
        body = re.sub(r"^[\s>*#\-+0-9.、()（）]+", "", body, flags=re.M)
        compact = re.sub(r"\s+", "", body)
        return len(compact) < 10

    @staticmethod
    def _subsection_item_count(body: str) -> int:
        numbered = re.findall(r"(?m)^\s*(?:[-*]\s+|\d+[.、)]\s*|[（(]\d+[）)]\s*)\S+", body)
        if numbered:
            return len(numbered)
        paragraphs = [p for p in re.split(r"\n\s*\n", body.strip()) if len(re.sub(r"\s+", "", p)) >= 10]
        return len(paragraphs)

    def analyze(self, module_results: list[ModuleResult]) -> str:
        sections = []
        for mr in module_results:
            if mr.error:
                sections.append(f"===== {mr.title} =====\n[{mr.error}]\n")
            else:
                sections.append(f"===== {mr.title} =====\n{mr.content}\n")
        body = "\n\n".join(sections)
        today = datetime.now()
        yesterday = today - timedelta(days=1)
        date_window = f"{yesterday.strftime('%Y年%m月%d日')}-{today.strftime('%Y年%m月%d日')}"

        prompt = f"""基于下列五大板块信息，写一份中文宏观战略分析。

结构：
1. 【核心主题】贯穿多个板块的主线
2. 【传导链】政策/经济/科技/社会/市场之间的因果关系
3. 【一致与背离】相互印证或冲突的信号；必须分成“一致信号”和“背离/张力”，各用（1）（2）列出至少2条
4. 【风险与机会】系统性风险与结构性机会
5. 【综合判断】未来1-3个月展望

要求：
- 仅基于输入信息；不要补充输入中没有的事实、数字或机构表态。
- 引用具体事件或数据时必须带来源和日期；日期不明的材料只可作为低置信背景。
- 只在必要时用 websearch 核验{date_window}内的关键数据。
- 每个小标题下必须有实质内容；如果证据不足，直接写“输入证据不足”，不要留下空项目符号。
- 【一致与背离】要像投研交叉验证：比较宏观数据、资产价格、政策新闻、科技产业、社会风险之间是否相互印证；“一致信号”和“背离/张力”都必须有至少2条编号判断，指出矛盾、时间错位或风险定价不足，并说明后续观察信号。
- 800-1500字，专业但易懂，避免套话。

===== 信息汇总 =====

{body}

===== 请开始分析 ====="""
        result = run_opencode(prompt, model=self.model, timeout_s=600, task_name="deep_analysis")
        missing_sections = self._missing_sections(result)
        if self._alignment_section_is_weak(result) and "一致与背离" not in missing_sections:
            missing_sections.append("一致与背离")

        if not missing_sections:
            return result

        retry_prompt = f"""上一次宏观战略分析输出不完整，缺少或留空这些部分：{', '.join(missing_sections)}。

请基于同一份输入重写完整中文分析。必须包含并填充这五节：
1. 【核心主题】
2. 【传导链】
3. 【一致与背离】
4. 【风险与机会】
5. 【综合判断】

每节至少一句实质判断；【一致与背离】必须同时包含“一致信号”和“背离/张力”，各用（1）（2）列出至少2条，并说明后续观察信号。证据不足时写清楚“输入证据不足”的原因。不要留下空标题、空项目符号或跳号编号。

===== 原始输入 =====

{body}

===== 不完整输出（仅供避免重复错误）=====

{result}

===== 请重写完整分析 ====="""
        retry_result = run_opencode(
            retry_prompt,
            model=self.model,
            timeout_s=600,
            task_name="deep_analysis_retry",
        )
        retry_missing_sections = self._missing_sections(retry_result)
        if self._alignment_section_is_weak(retry_result) and "一致与背离" not in retry_missing_sections:
            retry_missing_sections.append("一致与背离")
        if not retry_missing_sections:
            return retry_result

        final_prompt = f"""上一次重写后仍不合格，问题部分：{', '.join(retry_missing_sections)}。

请只重写一份完整的五节中文分析，尤其修正【一致与背离】：
- 必须有小标题“**一致信号：**”和“**背离/张力：**”。
- 两个小标题下都必须正好从（1）（2）开始，各至少两条，不要跳号。
- 每条都要比较至少两个板块，例如宏观数据 vs 资产价格、政策新闻 vs 科技产业、社会风险 vs 市场定价。
- 每条都要带来源和日期；证据不足时写清不足原因，但仍要成条。

===== 原始输入 =====

{body}

===== 仍不合格的输出（避免重复错误）=====

{retry_result}

===== 请输出完整合格分析 ====="""
        return run_opencode(
            final_prompt,
            model=self.model,
            timeout_s=600,
            task_name="deep_analysis_final_retry",
        )
