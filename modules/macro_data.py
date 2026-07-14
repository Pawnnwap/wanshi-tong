from modules.catalog import MACRO_ITEMS_EN, MACRO_ITEMS_ZH
from modules.structured_data import StructuredDataModule


class MacroDataModule(StructuredDataModule):
    name = "macro_data"
    title = "【宏观最新数据与指标】"
    task_idle_timeout_s = 600
    task_max_attempts = 1
    request_zh = "快速整理截至{today_cn}可核验的核心宏观数据。"
    request_en = "Quickly compile core macro data verifiable as of {today_en}."
    rules_zh = (
        "只做一次金融/宏观数据工具查询，不要逐项 websearch。",
        "最多18行；找不到就写“未取得”，不要反复搜索。",
        "禁止编造发布日期；月度/季度指标写发布日或标注“旧数据”。",
        f"覆盖：{MACRO_ITEMS_ZH}。",
    )
    rules_en = (
        "Make one financial/macro data tool query; do not web-search indicators one by one.",
        'Return at most 18 rows; if unavailable quickly, write "not found" and move on.',
        'Never fabricate publication dates; mark older releases as "(old data)".',
        f"Cover: {MACRO_ITEMS_EN}.",
    )
    output_zh = "输出中文。格式：指标名称 | 最新值 | 数据日期（精确到日）| 来源"
    output_en = "Output in English. Format: Indicator | Latest Value | Data Date (exact day) | Source"
