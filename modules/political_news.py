from modules.news import NewsModule


class PoliticalNewsModule(NewsModule):
    name = "political_news"
    title = "【头条政经新闻】"
    search_scope_zh = "国内外头条政经"
    search_scope_en = "top political/economic"
    coverage_zh = "政策发布、领导讲话、经济数据、国际关系、重大政治事件"
    coverage_en = "policy announcements, leadership speeches, economic data, international relations, and major political events"
    sources_zh = "新华网、人民网、央视新闻、财新、第一财经、Reuters、Bloomberg、AP、BBC、FT"
    sources_en = "Xinhua, People's Daily, CCTV, Caixin, Yicai, Reuters, Bloomberg, AP, BBC, FT"
    empty_label_zh = "政经"
    empty_label_en = "political/economic"
