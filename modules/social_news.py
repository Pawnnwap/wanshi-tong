from modules.news import NewsModule


class SocialNewsModule(NewsModule):
    name = "social_news"
    title = "【头条社会新闻】"
    search_scope_zh = "国内外头条社会"
    search_scope_en = "top social"
    coverage_zh = "民生、教育医疗、环保气候、突发事件、人口养老、文体娱乐"
    coverage_en = "livelihood, education/healthcare, environment/climate, breaking news, demographics/aging, and culture/entertainment"
    sources_zh = "澎湃、新京报、南方周末、新浪、腾讯新闻、CNN、Guardian、NYT、NPR、Al Jazeera"
    sources_en = "The Paper, Beijing News, Southern Weekly, Sina/Tencent News, CNN, Guardian, NYT, NPR, Al Jazeera"
    empty_label_zh = "社会"
    empty_label_en = "social"
