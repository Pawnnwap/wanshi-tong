from core.base import Module, _DATE_RULES_ZH, _DATE_RULES_EN, _FORMAT_ZH, _FORMAT_EN


class PoliticalNewsModule(Module):
    name = "political_news"
    title = "【头条政经新闻】"
    model = ""

    prompt_zh = f"""
你是一位资深的政经新闻分析师。请搜索2026年6月5日或6月6日发布的国内国际头条政经新闻。

## 可用工具（优先级从高到低）
1. **newsmcp get_news**（首选）: 直接获取实时结构化新闻
   - 参数示例: topics="politics,economy", geo="china,global", hours=48
2. **websearch**: 用关键词搜索补充细节
3. **rss-news fetch_news**: 从RSS订阅源获取新闻

## 日期红线（必须遵守）
{_DATE_RULES_ZH}
- 如果找不到符合条件的新闻，请注明"未找到6月5日-6月6日的政经新闻"

渠道：新华网、人民网、央视新闻、财新网、第一财经、Reuters、Bloomberg、AP News、BBC、FT
类别：政策发布、领导讲话、经济数据、国际关系、重大政治事件

{_FORMAT_ZH}"""

    prompt_en = f"""
You are a senior political and economic news analyst. Search for top political and economic news published on June 5 or June 6, 2026.

## Available Tools (priority order)
1. **newsmcp get_news** (preferred): Get real-time structured news directly
   - Example params: topics="politics,economy", geo="china,global", hours=48
2. **websearch**: Supplement with keyword searches
3. **rss-news fetch_news**: Get news from RSS feed subscriptions

## Date Red Lines (MUST follow)
{_DATE_RULES_EN}
- If no qualifying news found, state: "No political/economic news found for June 5-6, 2026"

Sources: Xinhua, People's Daily, CCTV, Caixin, Yicai, Reuters, Bloomberg, AP News, BBC, FT
Categories: policy announcements, leadership speeches, economic data, international relations, major political events

{_FORMAT_EN}"""
