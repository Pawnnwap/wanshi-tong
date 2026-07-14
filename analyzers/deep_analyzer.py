import re
from datetime import date, timedelta

from core.base import Analyzer, ModuleResult
from core.opencode_client import run_opencode


class DeepAnalyzer(Analyzer):
    name = "deep_analyzer"
    model = ""
    idle_timeout_s = 600
    REQUIRED_SECTIONS = ("核心主题", "传导链", "一致与背离", "风险与机会", "综合判断")
    TASK_NAMES = ("deep_analysis", "deep_analysis_retry", "deep_analysis_final_retry")

    @classmethod
    def _missing_sections(cls, text: str) -> list[str]:
        return [
            section
            for section in cls.REQUIRED_SECTIONS
            if len(cls._section_body(text, section)) < 6
        ]

    @classmethod
    def _quality_issues(cls, text: str) -> list[str]:
        issues = cls._missing_sections(text)
        if cls._alignment_section_is_weak(text) and "一致与背离" not in issues:
            issues.append("一致与背离")
        return issues

    @staticmethod
    def _section_body(text: str, section: str) -> str:
        match = re.search(rf"【{re.escape(section)}】", text)
        if not match:
            return ""
        remainder = text[match.end():]
        next_match = re.search(r"\n#{1,3}\s*\d+[.、]?\s*【", remainder)
        body = remainder[:next_match.start()] if next_match else remainder
        return re.sub(r"^[^\n]*", "", body, count=1).strip()

    @classmethod
    def _alignment_section_is_weak(cls, text: str) -> bool:
        section_body = cls._section_body(text, "一致与背离")
        consistency = cls._subsection_body(section_body, r"一致信号", r"(背离|张力|矛盾)")
        divergence = cls._subsection_body(section_body, r"(背离|张力|矛盾)", r"一致信号")
        return any(
            cls._subsection_is_empty(body) or cls._subsection_item_count(body) < 2
            for body in (consistency, divergence)
        )

    @staticmethod
    def _subsection_body(section_body: str, start_pattern: str, stop_pattern: str) -> str:
        heading = rf"(^|\n)#+\s*.*{start_pattern}.*\n|(^|\n).{{0,8}}{start_pattern}.{{0,8}}[:：]"
        start = re.search(heading, section_body)
        if not start:
            return ""
        body = section_body[start.end():]
        stop = re.search(
            rf"(^|\n)#+\s*.*{stop_pattern}.*\n|(^|\n).{{0,8}}{stop_pattern}.{{0,8}}[:：]",
            body,
        )
        return body[:stop.start()] if stop else body

    @staticmethod
    def _subsection_is_empty(body: str) -> bool:
        body = re.sub(r"```.*?```", "", body, flags=re.S)
        body = re.sub(r"^[\s>*#\-+0-9.、()（）]+", "", body, flags=re.M)
        return len(re.sub(r"\s+", "", body)) < 10

    @staticmethod
    def _subsection_item_count(body: str) -> int:
        numbered = re.findall(r"(?m)^\s*(?:[-*]\s+|\d+[.、)]\s*|[（(]\d+[）)]\s*)\S+", body)
        if numbered:
            return len(numbered)
        return len([
            paragraph
            for paragraph in re.split(r"\n\s*\n", body.strip())
            if len(re.sub(r"\s+", "", paragraph)) >= 10
        ])

    def analyze(self, module_results: list[ModuleResult]) -> str:
        source = self._format_source(module_results)
        prompt = self._initial_prompt(source)
        result = ""

        for attempt, task_name in enumerate(self.TASK_NAMES):
            result = run_opencode(
                prompt,
                model=self.model,
                idle_timeout_s=self.idle_timeout_s,
                task_name=task_name,
            )
            issues = self._quality_issues(result)
            if not issues or attempt == len(self.TASK_NAMES) - 1:
                return result
            prompt = self._retry_prompt(source, result, issues, final=attempt == 1)
        return result

    @staticmethod
    def _format_source(module_results: list[ModuleResult]) -> str:
        sections = []
        for result in module_results:
            content = f"[{result.error}]" if result.error else result.content
            sections.append(f"===== {result.title} =====\n{content}\n")
        return "\n\n".join(sections)

    @staticmethod
    def _date_window() -> str:
        today = date.today()
        yesterday = today - timedelta(days=1)
        return f"{yesterday:%Y年%m月%d日}-{today:%Y年%m月%d日}"

    def _initial_prompt(self, source: str) -> str:
        return f"""基于下列五大板块信息，写一份中文宏观战略分析。

结构：
1. 【核心主题】贯穿多个板块的主线
2. 【传导链】政策/经济/科技/社会/市场之间的因果关系
3. 【一致与背离】相互印证或冲突的信号；必须分成“一致信号”和“背离/张力”，各用（1）（2）列出至少2条
4. 【风险与机会】系统性风险与结构性机会
5. 【综合判断】未来1-3个月展望

要求：
- 仅基于输入信息；不要补充输入中没有的事实、数字或机构表态。
- 引用具体事件或数据时必须带来源和日期；日期不明的材料只可作为低置信背景。
- 只在必要时用 websearch 核验{self._date_window()}内的关键数据。
- 每个小标题下必须有实质内容；如果证据不足，直接写“输入证据不足”，不要留下空项目符号。
- 【一致与背离】要像投研交叉验证：比较宏观数据、资产价格、政策新闻、科技产业、社会风险之间是否相互印证；“一致信号”和“背离/张力”都必须有至少2条编号判断，指出矛盾、时间错位或风险定价不足，并说明后续观察信号。
- 800-1500字，专业但易懂，避免套话。

===== 信息汇总 =====

{source}

===== 请开始分析 ====="""

    def _retry_prompt(
        self,
        source: str,
        previous: str,
        issues: list[str],
        final: bool,
    ) -> str:
        issue_text = ", ".join(issues)
        if final:
            instructions = """请只重写一份完整的五节中文分析，尤其修正【一致与背离】：
- 必须有小标题“**一致信号：**”和“**背离/张力：**”。
- 两个小标题下都必须从（1）（2）开始，各至少两条，不要跳号。
- 每条都要比较至少两个板块，例如宏观数据 vs 资产价格、政策新闻 vs 科技产业、社会风险 vs 市场定价。
- 每条都要带来源和日期；证据不足时写清不足原因，但仍要成条。"""
            opening = f"上一次重写后仍不合格，问题部分：{issue_text}。"
        else:
            instructions = """请基于同一份输入重写完整中文分析，包含并填充五节：【核心主题】、【传导链】、【一致与背离】、【风险与机会】、【综合判断】。

每节至少一句实质判断；【一致与背离】必须同时包含“一致信号”和“背离/张力”，各用（1）（2）列出至少2条，并说明后续观察信号。证据不足时写清原因，不要留下空标题、空项目符号或跳号编号。"""
            opening = f"上一次宏观战略分析输出不完整，问题部分：{issue_text}。"

        return f"""{opening}

{instructions}

===== 原始输入 =====

{source}

===== 上次输出（仅供避免重复错误）=====

{previous}

===== 请重写完整分析 ====="""
