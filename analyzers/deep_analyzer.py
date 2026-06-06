from datetime import datetime
from core.base import Analyzer, ModuleResult
from core.opencode_client import run_opencode


class DeepAnalyzer(Analyzer):
    name = "deep_analyzer"
    model = ""

    def analyze(self, module_results: list[ModuleResult]) -> str:
        sections = []
        for mr in module_results:
            if mr.error:
                sections.append(f"===== {mr.title} =====\n[{mr.error}]\n")
            else:
                sections.append(f"===== {mr.title} =====\n{mr.content}\n")
        body = "\n\n".join(sections)
        date_str = datetime.now().strftime('%Y年%m月%d日')

        prompt = f"""你是一位宏观战略分析师，擅长跨领域、跨市场的深度关联分析。
请基于提供的五大板块信息，撰写一份深度分析报告。

分析框架：
1. 【核心主题识别】——找出贯穿多个板块的核心主题和主线逻辑
2. 【传导链分析】——分析政策→经济→科技→社会→市场之间的因果传导关系
3. 【一致性/背离分析】——哪些信号相互印证，哪些信号出现背离
4. 【风险与机会】——识别潜在的系统性风险和结构性机会
5. 【综合判断与展望】——给出前瞻性判断

## 强制指令
- 仅基于本次提供的五大板块信息进行分析
- 所有引用必须标注信息来源和具体日期
- 使用 websearch 仅用于对关键数据进行交叉验证（仅验证6月5日-6月6日范围的数据）

要求：中文，专业但易懂，逻辑严密，800-1500字。

===== 信息汇总 =====

{body}

===== 请开始分析 ====="""
        return run_opencode(prompt, model=self.model, timeout_s=600)
