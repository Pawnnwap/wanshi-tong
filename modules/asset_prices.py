from core.base import Module


class AssetPricesModule(Module):
    name = "asset_prices"
    title = "【资产与股指价格及涨跌】"
    model = ""
    prompt_zh = """获取{yesterday_cn}收盘或{today_cn}盘中的全球资产价格。

要求：
- 优先用金融数据工具；必要时 websearch 核对价格、涨跌幅和日期。
- 只收录{yesterday_cn}或{today_cn}的数据；更早或日期不明的丢弃；禁止编造。
- 覆盖至少20项：上证、深证、创业板、恒生、恒生科技、道指、纳指、标普500、日经225、DAX、FTSE100、CAC40、DXY、USDCNY、EURUSD、USDJPY、GBPUSD、黄金、布伦特、WTI、铜、BTC、ETH。

输出中文。格式：名称 | 价格 | 涨跌幅 | 日期
当前日期：{today_cn}"""
    prompt_en = """Get global asset prices from {yesterday_en} close or {today_en} intraday.

Rules:
- Prefer financial data tools; use websearch only to verify price, change %, and date.
- Include only {yesterday_en} or {today_en} data; discard older/undated data; never fabricate.
- Cover at least 20 items: Shanghai, Shenzhen, ChiNext, Hang Seng, Hang Seng Tech, Dow, Nasdaq, S&P 500, Nikkei 225, DAX, FTSE 100, CAC 40, DXY, USDCNY, EURUSD, USDJPY, GBPUSD, gold, Brent, WTI, copper, BTC, ETH.

Output in English. Format: Name | Price | Change % | Date
Current date: {today_en}"""
