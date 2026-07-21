"""Robust, non-agentic market data collection (mainland-China accessible).

This module replaces the previous agentic (LLM + MCP tool) approach to asset
prices, which failed unreliably. Everything here is deterministic Python.

Each asset has an ordered list of `Source`s spanning *different hosts* -- Tencent
(gu.qq.com), Sina, East Money, CFETS, Binance public-data mirror, Gate.io --
tried until one returns data, so no single provider (notably East Money, which
rate-limits aggressively) is a single point of failure. From the resulting daily
history we derive interpretable relative metrics: absolute change, daily change %,
and where the latest close sits inside its own 20-day / 60-day / 1-year
distribution, so the downstream analyzer can reason about position and extremes,
not just raw numbers.

Every source is reachable from mainland China; none is yfinance (blocked there).
The Dollar Index (DXY) has no public historical source reachable from China, so
it is computed from the six CFETS spot component pairs via the ICE formula.
"""

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Callable, Optional, Sequence

import requests

from core.timed_thread import run_with_timeout

# akshare is imported lazily inside the fetchers so component discovery stays
# fast and does not require the network just to import this file.


CALENDAR_YEAR_DAYS = 365
RETRY_ATTEMPTS = 3
RETRY_BACKOFF_S = 1.2
REQUEST_SPACING_S = 0.7  # gentle spacing between calls to avoid endpoint throttling
STALE_DAYS = 12  # reject data older than this (guards against frozen endpoints;
#                  wide enough to tolerate long holidays like Chinese New Year)
MIN_PERCENTILE_POINTS = 10  # need at least this many points for a 1y percentile
HTTP_TIMEOUT_S = 15
SOCKET_TIMEOUT_S = 20  # global cap so a stalled host cannot hang the whole run
THREAD_TIMEOUT_S = 60  # per-asset wall-clock cap to guard against DNS hangs
_UA = {"User-Agent": "Mozilla/5.0 (compatible; wanshi-tong/1.0)"}
BINANCE_KLINES_URL = "https://data-api.binance.vision/api/v3/klines"
GATEIO_CANDLES_URL = "https://api.gateio.ws/api/v4/spot/candlesticks"
TENCENT_KLINE_URL = "https://proxy.finance.qq.com/ifzqgtimg/appstock/app/newfqkline/get"
# ICE US Dollar Index (DXY) coefficients. No public DXY history endpoint is
# reachable from mainland China, so we synthesize the spot value from its six
# CFETS-quoted component pairs via the official ICE weighted geometric formula.
_DXY_CONSTANT = 50.14348112
# Exponent sign follows USD's role in each pair: negative when USD is the quote
# currency (EUR/USD, GBP/USD -- a higher rate means a weaker USD), positive when
# USD is the base currency (USD/JPY, USD/CAD, USD/SEK, USD/CHF -- a higher rate
# means a stronger USD). Absolute weights sum to 1.0.
_DXY_WEIGHTS = {
    "EUR/USD": -0.576,
    "USD/JPY": 0.136,
    "GBP/USD": -0.119,
    "USD/CAD": 0.091,
    "USD/SEK": 0.042,
    "USD/CHF": 0.036,
}


@dataclass(frozen=True)
class Source:
    """One place to fetch an asset from. `kind` selects the endpoint/host."""

    kind: str
    symbol: str


@dataclass(frozen=True)
class Asset:
    key: str
    zh: str
    en: str
    sources: tuple[Source, ...]  # tried in order until one returns data
    unit: str = ""  # optional short unit hint, e.g. "USD/oz"


def S(kind: str, symbol: str) -> Source:
    return Source(kind, symbol)


# Each asset lists sources across *different hosts* so no single provider (in
# particular East Money, which rate-limits aggressively) is a single point of
# failure. Order = priority; the first source that returns data wins.
#   Hosts: tencent = qq.com, em = eastmoney.com, sina = *.sina.com.cn,
#          cfets = chinamoney.com.cn, binance = data-api.binance.vision,
#          gateio = api.gateio.ws.
# China / HK / US indices and forex are fetched with NO Sina involvement
# (Tencent + East Money + CFETS). Europe/Japan indices and commodities have no
# third China-accessible source in akshare, so Sina is unavoidable there; East
# Money is their fallback (or primary, for commodities via the EM alternative).
# DXY is synthesized from CFETS spot component pairs (no direct source in China).
# Ordering of ASSETS also defines the row order in the rendered table.
ASSETS: tuple[Asset, ...] = (
    # --- China A-share indices: Tencent primary, East Money fallback ---
    Asset("sse", "上证指数", "Shanghai Composite",
          (S("tencent", "sh000001"), S("index_em", "上证指数"))),
    Asset("szse", "深证成指", "Shenzhen Component",
          (S("tencent", "sz399001"), S("index_em", "深证成指"))),
    Asset("chinext", "创业板指", "ChiNext",
          (S("tencent", "sz399006"), S("index_em", "创业板指"))),
    # --- Hong Kong: Tencent primary, East Money fallback (no Sina) ---
    Asset("hsi", "恒生指数", "Hang Seng",
          (S("tencent", "hkHSI"), S("index_em", "恒生指数"))),
    Asset("hstech", "恒生科技", "Hang Seng Tech",
          (S("tencent", "hkHSTECH"), S("index_hk_em", "HSTECH"))),
    # --- United States: Tencent primary, East Money fallback (no Sina) ---
    Asset("dow", "道琼斯", "Dow Jones",
          (S("tencent", "usDJI"), S("index_em", "道琼斯"))),
    Asset("nasdaq", "纳斯达克", "Nasdaq",
          (S("tencent", "usIXIC"), S("index_em", "纳斯达克"))),
    Asset("sp500", "标普500", "S&P 500",
          (S("tencent", "usINX"), S("index_em", "标普500"))),
    # --- Europe / Japan: Sina primary, East Money fallback ---
    #     (Tencent has no EU/JP indices; Sina and EM are the only options.)
    Asset("nikkei", "日经225", "Nikkei 225",
          (S("index_global_sina", "日经225指数"), S("index_em", "日经225"))),
    Asset("dax", "德国DAX", "DAX",
          (S("index_global_sina", "德国DAX 30种股价指数"), S("index_em", "德国DAX30"))),
    Asset("ftse", "英国富时100", "FTSE 100",
          (S("index_global_sina", "英国富时100指数"), S("index_em", "英国富时100"))),
    Asset("cac", "法国CAC40", "CAC 40",
          (S("index_global_sina", "法CAC40指数"), S("index_em", "法国CAC40"))),
    # --- Dollar index: synthesized from CFETS spot component pairs via ICE
    #     formula. No public DXY history endpoint is reachable from China. ---
    Asset("dxy", "美元指数", "Dollar Index (DXY)",
          (S("cfets_dxy", ""),)),
    # --- Forex: East Money history; CFETS spot as last resort (no Sina) ---
    Asset("usdcny", "美元人民币", "USD/CNY",
          (S("forex_em", "USDCNYC"), S("cfets_spot", "USD/CNY"))),
    Asset("eurusd", "欧元美元", "EUR/USD",
          (S("forex_em", "EURUSD"), S("cfets_spot", "EUR/USD"))),
    Asset("usdjpy", "美元日元", "USD/JPY",
          (S("forex_em", "USDJPY"), S("cfets_spot", "USD/JPY"))),
    Asset("gbpusd", "英镑美元", "GBP/USD",
          (S("forex_em", "GBPUSD"), S("cfets_spot", "GBP/USD"))),
    # --- Commodities: Sina foreign-futures daily K-line ---
    #     (Tencent has no international commodities; EM is the only alternative.)
    Asset("gold", "黄金", "Gold (COMEX)", (S("foreign_futures", "GC"),), "USD/oz"),
    Asset("brent", "布伦特原油", "Brent Crude", (S("foreign_futures", "OIL"),), "USD/bbl"),
    Asset("wti", "WTI原油", "WTI Crude", (S("foreign_futures", "CL"),), "USD/bbl"),
    Asset("copper", "铜", "Copper (COMEX)", (S("foreign_futures", "HG"),), "USD/lb"),
    # --- Crypto: Binance public-data mirror (primary) + Gate.io (fallback).
    #     api.binance.com is IP-blocked in China, but data-api.binance.vision is
    #     a separate public data-only mirror reachable from the mainland. ---
    Asset("btc", "比特币", "Bitcoin",
          (S("binance", "BTCUSDT"), S("gateio", "BTC_USDT"))),
    Asset("eth", "以太坊", "Ethereum",
          (S("binance", "ETHUSDT"), S("gateio", "ETH_USDT"))),
)


@dataclass
class Metrics:
    asset: Asset
    last: Optional[float] = None
    last_date: Optional[date] = None
    prev: Optional[float] = None
    change: Optional[float] = None
    change_pct: Optional[float] = None
    pct_20d: Optional[float] = None
    pct_60d: Optional[float] = None
    pct_1y: Optional[float] = None
    low_1y: Optional[float] = None
    high_1y: Optional[float] = None
    points_1y: int = 0
    error: Optional[str] = None


# --------------------------------------------------------------------------- #
# Fetching
# --------------------------------------------------------------------------- #

# Column layouts differ across endpoints: East Money history labels the daily
# close "最新价", the HK endpoint uses "latest", others use "收盘"/"close".
_DATE_COLS = ("日期", "date", "时间", "datetime")
_CLOSE_COLS = ("收盘", "收盘价", "close", "最新价", "latest", "最新", "最近报价")


def _retry(fn: Callable, label: str, attempts: int = RETRY_ATTEMPTS):
    """Call fn with retries; endpoints intermittently drop connections."""
    last_exc: Optional[Exception] = None
    for attempt in range(attempts):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 -- endpoints raise many error types
            last_exc = exc
            if attempt < attempts - 1:
                time.sleep(RETRY_BACKOFF_S * (attempt + 1))
    raise RuntimeError(f"{label}: {attempts} attempt(s) failed: {last_exc}")


def _pick_column(df, candidates: tuple[str, ...]) -> Optional[str]:
    for name in candidates:
        if name in df.columns:
            return name
    return None


def _to_series(df, date_col: Optional[str] = None, close_col: Optional[str] = None,
               scale: float = 1.0) -> list[tuple[date, float]]:
    """Normalize an OHLC dataframe into ascending [(date, close)] pairs."""
    import pandas as pd

    date_col = date_col or _pick_column(df, _DATE_COLS)
    close_col = close_col or _pick_column(df, _CLOSE_COLS)
    if date_col is None or close_col is None:
        raise ValueError(f"unexpected columns: {list(df.columns)}")

    frame = df[[date_col, close_col]].copy()
    frame[date_col] = pd.to_datetime(frame[date_col], errors="coerce")
    frame[close_col] = pd.to_numeric(frame[close_col], errors="coerce")
    frame = frame.dropna()
    frame = frame.sort_values(date_col)
    return [
        (row.date(), float(close) * scale)
        for row, close in zip(frame[date_col], frame[close_col])
    ]


def _fetch_history(asset: Asset) -> list[tuple[date, float]]:
    """Try each source in order; return the first that yields data.

    Sources deliberately span different hosts, so a single provider outage
    (typically East Money throttling) is survived by falling back to another.
    """
    errors = []
    # Fewer retries per source when alternatives exist -- fail over faster.
    per_source_attempts = 2 if len(asset.sources) > 1 else RETRY_ATTEMPTS
    for source in asset.sources:
        try:
            series = _retry(
                lambda s=source: _fetch_source(s),
                f"{asset.key}/{source.kind}",
                attempts=per_source_attempts,
            )
            if series:
                return series
            errors.append(f"{source.kind}: empty")
        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc)[:80])
    raise RuntimeError("; ".join(errors))


# Source dispatch. Direct-HTTP kinds map to a fetcher taking the symbol; akshare
# kinds map to the akshare function name whose dataframe is normalized by
# _to_series. Adding a source is a one-line entry in the matching table.
_DIRECT_FETCHERS: dict[str, Callable[[str], list[tuple[date, float]]]] = {
    "binance": lambda symbol: _fetch_binance(symbol),
    "gateio": lambda symbol: _fetch_gateio(symbol),
    "tencent": lambda symbol: _fetch_tencent_kline(symbol),
    "cfets_spot": lambda symbol: _fetch_cfets_spot(symbol),
    "cfets_dxy": lambda symbol: _fetch_cfets_dxy(),
}
_AKSHARE_FUNCS: dict[str, str] = {
    "index_hk_em": "stock_hk_index_daily_em",
    "index_global_sina": "index_global_hist_sina",
    "index_em": "index_global_hist_em",  # East Money global-index endpoint
    "index_global": "index_global_hist_em",
    "forex_em": "forex_hist_em",
    "foreign_futures": "futures_foreign_hist",
}


def _fetch_source(source: Source) -> list[tuple[date, float]]:
    """Fetch one (kind, symbol) into ascending [(date, close)]."""
    kind, symbol = source.kind, source.symbol
    if kind in _DIRECT_FETCHERS:
        return _DIRECT_FETCHERS[kind](symbol)
    if kind in _AKSHARE_FUNCS:
        import akshare as ak

        return _to_series(getattr(ak, _AKSHARE_FUNCS[kind])(symbol=symbol))
    raise ValueError(f"unknown source kind: {kind}")


def _fetch_tencent_kline(symbol: str) -> list[tuple[date, float]]:
    """Daily close history from Tencent's kline API (China + HK + US symbols).

    One request; symbols carry a market prefix: sh/sz (A-shares), hk (HK), us
    (US). Independent of both Sina and East Money.
    """
    start = (date.today() - timedelta(days=CALENDAR_YEAR_DAYS + 120)).isoformat()
    end = date.today().isoformat()
    params = {
        "_var": "kline_dayqfq",
        "param": f"{symbol},day,{start},{end},800,qfq",
        "r": "0.8",
    }
    response = requests.get(TENCENT_KLINE_URL, params=params, headers=_UA, timeout=HTTP_TIMEOUT_S)
    response.raise_for_status()
    text = response.text
    payload = json.loads(text.split("=", 1)[1] if text.startswith("kline_dayqfq=") else text)
    node = payload.get("data", {}).get(symbol, {})
    candles = node.get("day") or node.get("qfqday") or []
    # Each candle: [date, open, close, high, low, ...]; close is index 2.
    series = [
        (datetime.strptime(row[0], "%Y-%m-%d").date(), float(row[2]))
        for row in candles
        if len(row) >= 3
    ]
    return sorted(series)


def _cfets_mids(pairs: Sequence[str]) -> dict[str, float]:
    """Look up the mid price of each requested pair across CFETS's two spot
    tables (chinamoney.com.cn). Pairs not quoted are simply absent from the result."""
    import akshare as ak

    mids: dict[str, float] = {}
    for fetch in (ak.fx_spot_quote, ak.fx_pair_quote):
        if all(pair in mids for pair in pairs):
            break
        try:
            df = fetch()
        except Exception:  # noqa: BLE001 -- try the other CFETS table
            continue
        for pair in pairs:
            if pair in mids:
                continue
            match = df[df["货币对"] == pair]
            if not match.empty:
                row = match.iloc[0]
                mids[pair] = (float(row["买报价"]) + float(row["卖报价"])) / 2.0
    return mids


def _fetch_cfets_spot(pair: str) -> list[tuple[date, float]]:
    """CFETS spot rate -- a single point (no history), used as a last resort.
    Covers CNY pairs and major crosses."""
    mids = _cfets_mids([pair])
    if pair not in mids:
        raise RuntimeError(f"cfets: {pair} not quoted")
    return [(date.today(), mids[pair])]


def _fetch_binance(symbol: str) -> list[tuple[date, float]]:
    """Daily close history from the Binance public-data mirror.

    `data-api.binance.vision` is a public data-only mirror that is reachable
    from mainland China, unlike `api.binance.com` (IP-blocked there). Returns
    klines as `[openTime, open, high, low, close, volume, closeTime, ...]`.
    """
    response = requests.get(
        BINANCE_KLINES_URL,
        params={"symbol": symbol, "interval": "1d", "limit": 500},
        headers=_UA,
        timeout=HTTP_TIMEOUT_S,
    )
    response.raise_for_status()
    candles = response.json()
    # Each candle: [openTime(ms), open, high, low, close, volume, closeTime, ...];
    # close is index 4. Binance daily klines use UTC open time.
    series = [
        (datetime.utcfromtimestamp(int(candle[0]) / 1000).date(), float(candle[4]))
        for candle in candles
    ]
    return sorted(series)


def _fetch_gateio(symbol: str) -> list[tuple[date, float]]:
    """Daily close history from Gate.io's public candlestick API.

    `api.gateio.ws` is reachable from mainland China. Returns candlesticks as
    `[[timestamp(s), vol_quote, open, high, low, close, vol_base, complete], ...]`.
    """
    response = requests.get(
        GATEIO_CANDLES_URL,
        params={"currency_pair": symbol, "interval": "1d", "limit": 500},
        headers=_UA,
        timeout=HTTP_TIMEOUT_S,
    )
    response.raise_for_status()
    candles = response.json()
    # Each candle: [timestamp(s), quote_vol, close, high, low, open, base_vol,
    # closed]; close is index 2 (NOT 5 -- Gate.io orders close/high/low/open).
    # Gate.io daily candles use UTC seconds.
    series = [
        (datetime.utcfromtimestamp(int(candle[0])).date(), float(candle[2]))
        for candle in candles
    ]
    return sorted(series)


def _fetch_cfets_dxy() -> list[tuple[date, float]]:
    """Synthesize the Dollar Index (DXY) from CFETS spot component pairs.

    No public DXY history endpoint is reachable from mainland China. CFETS
    (chinamoney.com.cn) quotes all six ICE-formula component pairs live, so we
    derive the spot DXY via the standard ICE weighted geometric mean:

        DXY = 50.14348112 * EURUSD^-0.576 * USDJPY^0.136 * GBPUSD^-0.119
                                * USDCAD^0.091 * USDSEK^0.042 * USDCHF^0.036

    Returns a single (date.today(), dxy) point, so percentile metrics will be
    blank (like other spot-only fallbacks) but the latest value and date populate.
    """
    mids = _cfets_mids(list(_DXY_WEIGHTS))
    missing = [p for p in _DXY_WEIGHTS if p not in mids]
    if missing:
        raise RuntimeError(f"cfets_dxy: missing {missing}")

    dxy = _DXY_CONSTANT
    for pair, weight in _DXY_WEIGHTS.items():
        dxy *= mids[pair] ** weight
    return [(date.today(), dxy)]


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #

def _percentile_rank(values: list[float], current: float) -> float:
    """Share of observations (%) at or below `current`. 100 = top of range."""
    if not values:
        return float("nan")
    below = sum(1 for v in values if v <= current)
    return below / len(values) * 100.0


def _metrics_from_series(asset: Asset, series: list[tuple[date, float]]) -> Metrics:
    if not series:
        return Metrics(asset=asset, error="no data")

    last_date, last = series[-1]
    if (date.today() - last_date).days > STALE_DAYS:
        # Refuse to present stale data as current (e.g. a frozen endpoint).
        return Metrics(asset=asset, error=f"stale data (last {last_date.isoformat()})")

    metrics = Metrics(asset=asset, last=last, last_date=last_date, points_1y=len(series))

    if len(series) >= 2:
        prev = series[-2][1]
        metrics.prev = prev
        metrics.change = last - prev
        if prev:
            metrics.change_pct = (last - prev) / prev * 100.0

    closes = [close for _, close in series]
    if len(closes) >= 20:
        metrics.pct_20d = _percentile_rank(closes[-20:], last)
    if len(closes) >= 60:
        metrics.pct_60d = _percentile_rank(closes[-60:], last)

    cutoff = last_date - timedelta(days=CALENDAR_YEAR_DAYS)
    one_year = [close for day, close in series if day >= cutoff]
    metrics.points_1y = len(one_year)
    if len(one_year) >= MIN_PERCENTILE_POINTS:
        # A percentile over just a handful of points is noise (and trivially
        # 100% for a single spot-only fallback), so require a real window.
        metrics.pct_1y = _percentile_rank(one_year, last)
        metrics.low_1y = min(one_year)
        metrics.high_1y = max(one_year)
    return metrics


def collect_metrics(log: Optional[Callable[[str], None]] = None) -> list[Metrics]:
    """Fetch every asset and compute metrics. Never raises: failures become rows
    carrying an error, so one dead endpoint cannot sink the whole report."""
    results: list[Metrics] = []

    # akshare's internal requests calls pass no timeout, so a host that accepts
    # the connection but never responds would hang the whole run. A global
    # socket timeout bounds every network call; restore it afterward.
    import socket

    previous_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(SOCKET_TIMEOUT_S)
    try:
        for asset in ASSETS:
            try:
                series = run_with_timeout(
                    lambda a=asset: _fetch_history(a),
                    THREAD_TIMEOUT_S, label=f"{asset.key}/fetch",
                )
                metrics = _metrics_from_series(asset, series)
            except TimeoutError:
                metrics = Metrics(asset=asset, error="timeout after {}s".format(THREAD_TIMEOUT_S))
            except Exception as exc:  # noqa: BLE001
                metrics = Metrics(asset=asset, error=str(exc)[:100])
            results.append(metrics)
            if log:
                status = "OK" if metrics.error is None else metrics.error
                log(f"    {asset.key}: {status}")
            time.sleep(REQUEST_SPACING_S)
    finally:
        socket.setdefaulttimeout(previous_timeout)

    return results


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #

def _fmt_price(value: Optional[float]) -> str:
    if value is None:
        return "—"
    if abs(value) >= 1000:
        return f"{value:,.2f}"
    if abs(value) >= 1:
        return f"{value:.2f}"
    return f"{value:.4f}"


def _fmt_signed(value: Optional[float], pct: bool = False) -> str:
    if value is None:
        return "—"
    suffix = "%" if pct else ""
    return f"{value:+.2f}{suffix}"


def _fmt_pctile(value: Optional[float]) -> str:
    if value is None or math.isnan(value):
        return "—"
    return f"{value:.0f}%"


def _fmt_range(low: Optional[float], high: Optional[float]) -> str:
    if low is None or high is None:
        return "—"
    return f"{_fmt_price(low)}–{_fmt_price(high)}"


HEADER_ZH = (
    "分位=最新价在该窗口全部交易日收盘价中的百分位（0%=区间最低，100%=区间最高）；"
    "涨跌为相对上一交易日。空缺（—）表示历史不足或该项数据未取得。"
)
HEADER_EN = (
    "Percentile = where the latest close ranks within that window's closes "
    "(0% = window low, 100% = window high); change is vs. the previous session. "
    "A dash (—) means insufficient history or that item could not be fetched."
)

_COLUMNS = (
    "资产 Asset",
    "最新价 Last",
    "日期 Date",
    "涨跌 Chg",
    "涨跌% Chg%",
    "20日分位 20d",
    "60日分位 60d",
    "1年分位 1y",
    "1年区间 1y Range",
)


def _row(metrics: Metrics) -> list[str]:
    asset = metrics.asset
    name = f"{asset.zh} {asset.en}"
    if metrics.error and metrics.last is None:
        return [name, f"[{metrics.error}]", "—", "—", "—", "—", "—", "—", "—"]
    date_str = metrics.last_date.isoformat() if metrics.last_date else "—"
    return [
        name,
        _fmt_price(metrics.last),
        date_str,
        _fmt_signed(metrics.change),
        _fmt_signed(metrics.change_pct, pct=True),
        _fmt_pctile(metrics.pct_20d),
        _fmt_pctile(metrics.pct_60d),
        _fmt_pctile(metrics.pct_1y),
        _fmt_range(metrics.low_1y, metrics.high_1y),
    ]


def render_table(metrics_list: list[Metrics]) -> str:
    rows = [_row(m) for m in metrics_list]
    table = _markdown_table(_COLUMNS, rows)
    ok = sum(1 for m in metrics_list if m.error is None)
    summary = f"覆盖 {ok}/{len(metrics_list)} 项 | Coverage {ok}/{len(metrics_list)}"
    return f"{HEADER_ZH}\n\n{HEADER_EN}\n\n{table}\n\n{summary}"


def _markdown_table(columns: tuple[str, ...], rows: list[list[str]]) -> str:
    header = "| " + " | ".join(columns) + " |"
    divider = "| " + " | ".join("---" for _ in columns) + " |"
    body = ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join([header, divider, *body])
