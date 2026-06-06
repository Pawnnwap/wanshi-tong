from core.base import Module, _DATE_RULES_ZH, _DATE_RULES_EN, _FORMAT_ZH, _FORMAT_EN


class SocialNewsModule(Module):
    name = "social_news"
    title = "【头条社会新闻】"
    model = ""

    prompt_zh = f"""
你是一位资深的社会新闻编辑。请搜索2026年6月5日或6月6日发布的国内国际头条社会新闻。

## 可用工具（优先级从高到低）
1. **newsmcp get_news**（首选）: 直接获取实时结构化新闻
   - 参数示例: topics="society,health,education", geo="china,global", hours=48
2. **websearch**: 用关键词搜索补充细节
3. **rss-news fetch_news**: 从RSS订阅源获取新闻

## 日期红线（必须遵守）
{_DATE_RULES_ZH}
- 如果找不到符合条件的新闻，请注明"未找到6月5日-6月6日的社会新闻"

渠道：澎湃新闻、新京报、南方周末、新浪新闻、腾讯新闻、CNN、Guardian、NYT、NPR、Al Jazeera
类别：民生话题、教育医疗、环保气候、突发事件、人口养老、文体娱乐

{_FORMAT_ZH}"""

    prompt_en = f"""
You are a senior social news editor. Search for top social news published on June 5 or June 6, 2026.

## Available Tools (priority order)
1. **newsmcp get_news** (preferred): Get real-time structured news directly
   - Example params: topics="society,health,education", geo="china,global", hours=48
2. **websearch**: Supplement with keyword searches
3. **rss-news fetch_news**: Get news from RSS feed subscriptions

## Date Red Lines (MUST follow)
{_DATE_RULES_EN}
- If no qualifying news found, state: "No social news found for June 5-6, 2026"

Sources: The Paper, Beijing News, Southern Weekly, Sina News, Tencent News, CNN, Guardian, NYT, NPR, Al Jazeera
Categories: livelihood topics, education/healthcare, environment/climate, breaking news, demographics/aging, culture/entertainment

{_FORMAT_EN}"""
