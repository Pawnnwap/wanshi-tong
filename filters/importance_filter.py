from core.base import Filter, ModuleResult
from core.opencode_client import run_opencode


class ImportanceFilter(Filter):
    name = "importance_filter"
    model = ""

    STRUCTURED_MODULES = {
        "asset_prices": (
            "整理资产价格数据：合并中英文结果，去重，保留可核验的价格、涨跌幅和日期；"
            "不要按新闻重要性丢弃市场价格。\n"
            "必须尽量覆盖：上证、深证、创业板、恒生、恒生科技、道指、纳指、标普500、"
            "日经225、DAX、FTSE100、CAC40、DXY、USDCNY、EURUSD、USDJPY、GBPUSD、"
            "黄金、布伦特、WTI、铜、BTC、ETH。\n"
            "输出中文表格，格式：名称 | 价格 | 涨跌幅 | 日期 | 来源。\n"
            "只使用输入中已有或可核验的信息；缺失项写“未取得”，禁止编造。"
        ),
        "macro_data": (
            "整理宏观数据：合并中英文结果，去重，保留最新可核验数据；"
            "不要按新闻重要性丢弃宏观指标。\n"
            "必须尽量覆盖：中国GDP、CPI/PPI、PMI、社融、外储、人民币汇率、失业率；"
            "美国GDP、CPI、失业率、联邦基金利率、ISM PMI；欧盟GDP、CPI、欧央行利率；"
            "日本GDP、CPI、日央行利率；布伦特/WTI。\n"
            "输出中文表格，格式：指标名称 | 最新值 | 数据日期（精确到日）| 来源。\n"
            "旧数据可保留并标注“旧数据”；缺失项写“未取得”，禁止编造发布日期。"
        ),
    }

    def filter(self, module_result: ModuleResult) -> ModuleResult:
        if module_result.error or not module_result.content.strip():
            return module_result

        if module_result.name in self.STRUCTURED_MODULES:
            prompt = (
                self.STRUCTURED_MODULES[module_result.name]
                + "\n\n原始数据：\n"
                + module_result.content
            )
        else:
            prompt = (
                "筛选高重要性新闻：只保留对全球/区域经济、政策或市场有显著影响的条目；"
                "局部、重复、低影响或日期不明的丢弃。\n"
                "输出中文，每条格式：**[标题]** | 摘要 | 来源 | **日期**。\n"
                "若无保留项，输出：本次搜索未发现重大新闻\n\n"
                f"新闻列表：\n{module_result.content}"
            )

        filtered_content = run_opencode(
            prompt,
            model=self.model,
            timeout_s=300,
            task_name=f"filter_{module_result.name}",
        )
        return ModuleResult(
            name=module_result.name,
            title=module_result.title,
            content=filtered_content,
            model=module_result.model,
        )
