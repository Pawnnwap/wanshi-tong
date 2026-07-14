from core.base import Module


class TechNewsModule(Module):
    name = "tech_news"
    title = "【科技新闻】"
    model = ""
    prompt_zh = """搜索{yesterday_cn}或{today_cn}发布的全球科技新闻。

要求：
- 只收录发布日期为{yesterday_cn}或{today_cn}的新闻；更早、未来或日期不明的直接丢弃。
- 优先使用结构化新闻工具，其次 websearch/RSS 交叉核对来源与日期。
- 覆盖 AI/大模型、半导体、新能源车、航天、科技巨头动态。

输出中文。每条格式：**[标题]** | 1句摘要 | 来源 | **YYYY年M月D日**
如无合格新闻，输出：未找到{yesterday_short_cn}-{today_short_cn}的科技新闻
当前日期：{today_cn}"""
    prompt_en = """Search for global technology news published on {yesterday_en} or {today_en}.

Rules:
- Include only items published on {yesterday_en} or {today_en}; discard older, future, or undated items.
- Prefer structured news tools, then websearch/RSS to verify source and date.
- Cover AI/LLM, semiconductors, EVs/new energy, space tech, and big tech company moves.

Output in English. Format each item: **[Title]** | one-sentence summary | Source | **Month D, YYYY**
If none qualify, output: No tech news found for {month_en} {yesterday_day}-{today_day}, {year}
Current date: {today_en}"""
