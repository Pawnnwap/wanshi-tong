from core.base import Module, _DATE_RULES_ZH, _DATE_RULES_EN, _FORMAT_ZH, _FORMAT_EN

_ASSET_TOOLS_ZH = """
## 可用工具（优先级从高到低）
1. **financial MCP**（首选）: 直接获取实时金融数据
   - get_stock_quote: 获取股票实时报价（如 ticker="000001.SS" 为上证指数）
   - get_crypto_price: 获取加密货币价格（如 coin="bitcoin"）
   - get_forex_rate: 获取汇率（如 pair="USDCNY"）
   - get_price_history: 获取历史价格
2. **websearch**: 用关键词搜索补充细节
3. **newsmcp get_news**: 搜索财经新闻获取市场动态"""

_ASSET_TOOLS_EN = """
## Available Tools (priority order)
1. **financial MCP** (preferred): Get real-time financial data directly
   - get_stock_quote: Get stock quotes (e.g. ticker="000001.SS" for Shanghai Composite)
   - get_crypto_price: Get crypto prices (e.g. coin="bitcoin")
   - get_forex_rate: Get forex rates (e.g. pair="USDCNY")
   - get_price_history: Get historical prices
2. **websearch**: Supplement with keyword searches
3. **newsmcp get_news**: Search financial news for market dynamics"""


class AssetPricesModule(Module):
    name = "asset_prices"
    title = "【资产与股指价格及涨跌】"
    model = ""

    prompt_zh = f"""
你是一位金融市场分析师。请获取2026年6月5日或6月6日的最新全球资产价格数据。

{_ASSET_TOOLS_ZH}

## 日期红线（必须遵守）
{_DATE_RULES_ZH}
- 无法确认日期的数据不要收录

覆盖：
股指：上证(000001.SS)、深证(399001.SZ)、创业板(399006.SZ)、恒生(^HSI)、恒生科技(^HSTECH)、道琼斯(^DJI)、纳斯达克(^IXIC)、标普500(^GSPC)、日经225(^N225)、德国DAX(^GDAXI)、英国富时100(^FTSE)、法国CAC40(^FCHI)
外汇：DXY、USDCNY、EURUSD、USDJPY、GBPUSD
商品：黄金(GC=F)、布伦特(BZ=F)、WTI(CL=F)、铜(HG=F)、BTC、ETH

格式：名称 | 价格 | 涨跌幅 | 日期
至少20条。
当前日期：2026年6月6日"""

    prompt_en = f"""
You are a financial market analyst. Get the latest global asset price data for June 5 or June 6, 2026.

{_ASSET_TOOLS_EN}

## Date Red Lines (MUST follow)
{_DATE_RULES_EN}
- Do not include data if you cannot confirm the date

Coverage:
Indices: Shanghai(000001.SS), Shenzhen(399001.SZ), ChiNext(399006.SZ), Hang Seng(^HSI), Hang Seng Tech(^HSTECH), Dow Jones(^DJI), NASDAQ(^IXIC), S&P 500(^GSPC), Nikkei 225(^N225), DAX(^GDAXI), FTSE 100(^FTSE), CAC 40(^FCHI)
Forex: DXY, USDCNY, EURUSD, USDJPY, GBPUSD
Commodities: Gold(GC=F), Brent(BZ=F), WTI(CL=F), Copper(HG=F), BTC, ETH

Format: Name | Price | Change % | Date
At least 20 items.
Current date: June 6, 2026"""
