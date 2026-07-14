from modules.news import NewsModule


class TechNewsModule(NewsModule):
    name = "tech_news"
    title = "【科技新闻】"
    search_scope_zh = "全球科技"
    search_scope_en = "global technology"
    coverage_zh = "AI/大模型、半导体、新能源车、航天、科技巨头动态"
    coverage_en = "AI/LLM, semiconductors, EVs/new energy, space tech, and big tech company moves"
    empty_label_zh = "科技"
    empty_label_en = "tech"
