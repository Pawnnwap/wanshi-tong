from core.base import Module


class PoliticalNewsModule(Module):
    name = "political_news"
    title = "【头条政经新闻】"
    model = ""
    prompt_zh = """搜索{yesterday_cn}或{today_cn}发布的国内外头条政经新闻。

要求：
- 只收录发布日期为{yesterday_cn}或{today_cn}的新闻；更早、未来或日期不明的直接丢弃。
- 优先使用结构化新闻工具，其次 websearch/RSS 交叉核对来源与日期。
- 覆盖政策发布、领导讲话、经济数据、国际关系、重大政治事件。
- 优先来源：新华网、人民网、央视新闻、财新、第一财经、Reuters、Bloomberg、AP、BBC、FT。

输出中文。每条格式：**[标题]** | 1句摘要 | 来源 | **YYYY年M月D日**
如无合格新闻，输出：未找到{yesterday_short_cn}-{today_short_cn}的政经新闻
当前日期：{today_cn}"""
    prompt_en = """Search for top political/economic news published on {yesterday_en} or {today_en}.

Rules:
- Include only items published on {yesterday_en} or {today_en}; discard older, future, or undated items.
- Prefer structured news tools, then websearch/RSS to verify source and date.
- Cover policy announcements, leadership speeches, economic data, international relations, and major political events.
- Prefer sources: Xinhua, People's Daily, CCTV, Caixin, Yicai, Reuters, Bloomberg, AP, BBC, FT.

Output in English. Format each item: **[Title]** | one-sentence summary | Source | **Month D, YYYY**
If none qualify, output: No political/economic news found for {month_en} {yesterday_day}-{today_day}, {year}
Current date: {today_en}"""
