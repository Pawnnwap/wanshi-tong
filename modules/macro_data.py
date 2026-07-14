from core.base import Module


class MacroDataModule(Module):
    name = "macro_data"
    title = "【宏观最新数据与指标】"
    model = ""
    prompt_zh = """快速整理截至{today_cn}可核验的核心宏观数据。

要求：
- 优先金融/宏观数据工具；只在缺关键日期时 websearch。
- 最多18行；找不到就写“未取得”，不要反复搜索。
- 禁止编造发布日期；月度/季度指标写发布日或标注“旧数据”。
- 覆盖：中国GDP、CPI/PPI、PMI、社融、外储、人民币汇率、失业率；美国GDP、CPI、失业率、联邦基金利率、ISM PMI；欧盟GDP、CPI、欧央行利率；日本GDP、CPI、日央行利率；布伦特/WTI。

输出中文。格式：指标名称 | 最新值 | 数据日期（精确到日）| 来源
当前日期：{today_cn}"""
    prompt_en = """Quickly compile core macro data verifiable as of {today_en}.

Rules:
- Prefer financial/macro data tools; use websearch only for missing key publication dates.
- Return at most 18 rows; if unavailable quickly, write "not found" and move on.
- Never fabricate publication dates; mark older releases as "(old data)".
- Cover: China GDP, CPI/PPI, PMI, TSF, forex reserves, RMB rate, unemployment; US GDP, CPI, unemployment, Fed funds, ISM PMI; EU GDP, CPI, ECB rate; Japan GDP, CPI, BOJ rate; Brent/WTI.

Output in English. Format: Indicator | Latest Value | Data Date (exact day) | Source
Current date: {today_en}"""

    def get_tasks(self, date_templates: dict | None = None) -> list[dict]:
        tasks = super().get_tasks(date_templates)
        for task in tasks:
            task["timeout_s"] = 300
            task["max_attempts"] = 1
        return tasks
