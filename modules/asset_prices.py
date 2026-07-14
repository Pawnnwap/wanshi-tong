from modules.catalog import ASSET_ITEMS_EN, ASSET_ITEMS_ZH
from modules.structured_data import StructuredDataModule


class AssetPricesModule(StructuredDataModule):
    name = "asset_prices"
    title = "【资产与股指价格及涨跌】"
    request_zh = "获取{yesterday_cn}收盘或{today_cn}盘中的全球资产价格。"
    request_en = "Get global asset prices from {yesterday_en} close or {today_en} intraday."
    rules_zh = (
        "优先用金融数据工具；必要时 websearch 核对价格、涨跌幅和日期。",
        "只收录{yesterday_cn}或{today_cn}的数据；更早或日期不明的丢弃；禁止编造。",
        f"覆盖至少20项：{ASSET_ITEMS_ZH}。",
    )
    rules_en = (
        "Prefer financial data tools; use websearch only to verify price, change %, and date.",
        "Include only {yesterday_en} or {today_en} data; discard older/undated data; never fabricate.",
        f"Cover at least 20 items: {ASSET_ITEMS_EN}.",
    )
    output_zh = "输出中文。格式：名称 | 价格 | 涨跌幅 | 日期"
    output_en = "Output in English. Format: Name | Price | Change % | Date"
