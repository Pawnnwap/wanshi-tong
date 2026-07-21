"""Robust, non-agentic Chinese macro data collection (East Money API).

Replaces the former agentic (LLM + MCP tool) approach to macro data, which
pulled from jin10.com via akshare and became stale (Aug-Sep 2025).
Everything here is deterministic Python hitting the East Money datacenter API,
which delivers current data (verified through June 2026).

Covered indicators: CPI, PPI, PMI (mfg + non-mfg), GDP, M2/M1/M0,
forex + gold reserves, trade (exports/imports), new RMB loans.

Missing (no reliable mainland-accessible source found):
  - Urban unemployment rate
  - Social financing total (TSF) — RMB loans serve as a proxy
  - LPR / SHIBOR
"""

from __future__ import annotations

import socket
import time
from dataclasses import dataclass
from typing import Callable, Optional

import requests

EASTMONEY_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
REQUEST_SPACING_S = 0.5
SOCKET_TIMEOUT_S = 20
HTTP_TIMEOUT_S = 15
_UA = {"User-Agent": "Mozilla/5.0 (compatible; wanshi-tong/1.0)"}


@dataclass(frozen=True)
class IndicatorDef:
    """One macro indicator: source type, report spec, and the field keys."""
    key: str
    zh: str
    en: str
    source: str = "eastmoney"  # "eastmoney" | "akshare_lpr" | "akshare_shibor" | "akshare_tsf"
    report_name: str = ""      # for eastmoney
    value_key: str = ""        # column for current value
    unit: str = ""
    value_is_int: bool = False


@dataclass
class IndicatorResult:
    definition: IndicatorDef
    value: Optional[float] = None
    previous: Optional[float] = None
    obs_date: Optional[str] = None
    error: Optional[str] = None


INDICATORS: tuple[IndicatorDef, ...] = (
    IndicatorDef("cpi", "CPI (同比)", "CPI (YoY)",
                 report_name="RPT_ECONOMY_CPI", value_key="NATIONAL_SAME", unit="%"),
    IndicatorDef("ppi", "PPI (同比)", "PPI (YoY)",
                 report_name="RPT_ECONOMY_PPI", value_key="BASE_SAME", unit="%"),
    IndicatorDef("pmi_mfg", "官方制造业PMI", "Official Mfg PMI",
                 report_name="RPT_ECONOMY_PMI", value_key="MAKE_INDEX"),
    IndicatorDef("pmi_nonmfg", "官方非制造业PMI", "Official Non-Mfg PMI",
                 report_name="RPT_ECONOMY_PMI", value_key="NMAKE_INDEX"),
    IndicatorDef("gdp", "GDP (同比)", "GDP (YoY)",
                 report_name="RPT_ECONOMY_GDP", value_key="SUM_SAME", unit="%"),
    IndicatorDef("m2", "M2 (同比)", "M2 (YoY)",
                 report_name="RPT_ECONOMY_CURRENCY_SUPPLY", value_key="BASIC_CURRENCY_SAME",
                 unit="%", value_is_int=True),
    IndicatorDef("m1", "M1 (同比)", "M1 (YoY)",
                 report_name="RPT_ECONOMY_CURRENCY_SUPPLY", value_key="CURRENCY_SAME",
                 unit="%", value_is_int=True),
    IndicatorDef("m0", "M0 (同比)", "M0 (YoY)",
                 report_name="RPT_ECONOMY_CURRENCY_SUPPLY", value_key="FREE_CASH_SAME",
                 unit="%", value_is_int=True),
    IndicatorDef("forex", "外汇储备", "Forex Reserves",
                 report_name="RPT_ECONOMY_GOLD_CURRENCY", value_key="FOREX",
                 unit="亿美元", value_is_int=True),
    IndicatorDef("gold", "黄金储备", "Gold Reserves",
                 report_name="RPT_ECONOMY_GOLD_CURRENCY", value_key="GOLD_RESERVES",
                 unit="吨", value_is_int=True),
    IndicatorDef("exports", "出口 (同比)", "Exports (YoY)",
                 report_name="RPT_ECONOMY_CUSTOMS", value_key="EXIT_BASE_SAME",
                 unit="%", value_is_int=True),
    IndicatorDef("imports", "进口 (同比)", "Imports (YoY)",
                 report_name="RPT_ECONOMY_CUSTOMS", value_key="IMPORT_BASE_SAME",
                 unit="%", value_is_int=True),
    IndicatorDef("rmb_loan", "新增人民币贷款", "New RMB Loans",
                 report_name="RPT_ECONOMY_RMB_LOAN", value_key="RMB_LOAN",
                 unit="亿元", value_is_int=True),
    IndicatorDef("fixed_asset_inv", "固定资产投资 (同比)", "Fixed Asset Investment (YoY)",
                 report_name="RPT_ECONOMY_ASSET_INVEST", value_key="BASE_SAME",
                 unit="%", value_is_int=True),
    IndicatorDef("retail_sales", "社消零售总额 (同比)", "Total Retail Sales (YoY)",
                 report_name="RPT_ECONOMY_TOTAL_RETAIL", value_key="RETAIL_TOTAL_SAME",
                 unit="%", value_is_int=True),
    IndicatorDef("lpr_1y", "LPR (1年)", "LPR (1Y)",
                 source="akshare_lpr", unit="%"),
    IndicatorDef("lpr_5y", "LPR (5年)", "LPR (5Y)",
                 source="akshare_lpr", unit="%"),
    IndicatorDef("shibor_on", "SHIBOR (隔夜)", "SHIBOR (O/N)",
                 source="akshare_shibor", unit="%"),
    IndicatorDef("tsf", "社融规模增量", "TSF Increment",
                 source="akshare_tsf", unit="亿元", value_is_int=True),
)


def _fetch_raw(report_name: str) -> dict:
    """Fetch the latest row for a report; returns the raw item dict or raises."""
    params = {
        "reportName": report_name,
        "columns": "ALL",
        "pageSize": 1,
        "sortTypes": -1,
        "sortColumns": "REPORT_DATE",
    }
    resp = requests.get(EASTMONEY_URL, params=params, headers=_UA, timeout=HTTP_TIMEOUT_S)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("success") or not data.get("result"):
        raise RuntimeError("API returned no success")
    items = data["result"].get("data", [])
    if not items:
        raise RuntimeError("no data rows")
    return items[0]


def _value_from(item: dict, key: str) -> tuple[Optional[float], Optional[float]]:
    """Return (value, previous) parsed from the raw row dict."""
    raw = item.get(key)
    try:
        value = float(raw) if raw is not None else None
    except (TypeError, ValueError):
        value = None

    prev = None
    return value, prev


def _fetch_akshare_lpr() -> tuple[Optional[float], Optional[float], Optional[str]]:
    """Return (lpr_1y, lpr_5y, date)."""
    import akshare as ak
    df = ak.macro_china_lpr()
    latest = df.iloc[-1]
    date_str = str(latest.iloc[0])
    try:
        lpr_1y = float(latest.iloc[1])
    except (TypeError, ValueError, IndexError):
        lpr_1y = None
    try:
        lpr_5y = float(latest.iloc[2])
    except (TypeError, ValueError, IndexError):
        lpr_5y = None
    return lpr_1y, lpr_5y, date_str


def _fetch_akshare_shibor() -> tuple[Optional[float], Optional[str]]:
    """Return (shibor_overnight, date)."""
    import akshare as ak
    df = ak.macro_china_shibor_all()
    latest = df.iloc[-1]
    date_str = str(latest.iloc[0])
    try:
        on_rate = float(latest.iloc[1])
    except (TypeError, ValueError, IndexError):
        on_rate = None
    return on_rate, date_str


def _fetch_akshare_tsf() -> tuple[Optional[float], Optional[str]]:
    """Return (tsf_increment, date) — social financing total for latest month."""
    import akshare as ak
    df = ak.macro_china_shrzgm()
    latest = df.iloc[-1]
    raw_date = str(latest.iloc[0])
    if len(raw_date) == 6 and raw_date.isdigit():
        date_str = "{}-{}".format(raw_date[:4], raw_date[4:])
    else:
        date_str = raw_date
    try:
        tsf = float(latest.iloc[1])
    except (TypeError, ValueError, IndexError):
        tsf = None
    return tsf, date_str


def collect_indicators(log: Optional[Callable[[str], None]] = None) -> list[IndicatorResult]:
    results: list[IndicatorResult] = []
    report_cache: dict[str, dict] = {}
    akshare_cache: dict[str, tuple] = {}  # "akshare_lpr" -> (lpr_1y, lpr_5y, date), etc.

    previous_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(SOCKET_TIMEOUT_S)
    try:
        for ind in INDICATORS:
            try:
                if ind.source == "eastmoney":
                    result = _collect_eastmoney(ind, report_cache, log)
                elif ind.source == "akshare_lpr":
                    result = _collect_akshare_lpr(ind, akshare_cache, log)
                elif ind.source == "akshare_shibor":
                    result = _collect_akshare_shibor(ind, akshare_cache, log)
                elif ind.source == "akshare_tsf":
                    result = _collect_akshare_tsf(ind, akshare_cache, log)
                else:
                    result = IndicatorResult(definition=ind, error="unknown source: " + ind.source)
                results.append(result)
            except Exception as exc:  # noqa: BLE001
                results.append(IndicatorResult(definition=ind, error=str(exc)[:100]))
                if log:
                    log("    {}: {}".format(ind.key, exc))

            time.sleep(REQUEST_SPACING_S)
    finally:
        socket.setdefaulttimeout(previous_timeout)

    return results


def _collect_eastmoney(ind: IndicatorDef, report_cache: dict, log) -> IndicatorResult:
    if ind.report_name not in report_cache:
        item = _fetch_raw(ind.report_name)
        report_cache[ind.report_name] = item
        if log:
            log("    {}: fetched".format(ind.report_name))
    else:
        item = report_cache[ind.report_name]

    obs_date = item.get("REPORT_DATE", "")
    if obs_date:
        obs_date = obs_date[:10]

    value, _ = _value_from(item, ind.value_key)
    if log:
        log("    {}: OK = {}".format(ind.key, value))
    return IndicatorResult(definition=ind, value=value, obs_date=obs_date)


def _collect_akshare_lpr(ind: IndicatorDef, cache: dict, log) -> IndicatorResult:
    if "lpr" not in cache:
        cache["lpr"] = _fetch_akshare_lpr()
    lpr_1y, lpr_5y, date_str = cache["lpr"]
    value = lpr_1y if ind.key == "lpr_1y" else lpr_5y
    if log:
        log("    {}: OK = {}".format(ind.key, value))
    return IndicatorResult(definition=ind, value=value, obs_date=date_str)


def _collect_akshare_shibor(ind: IndicatorDef, cache: dict, log) -> IndicatorResult:
    if "shibor" not in cache:
        cache["shibor"] = _fetch_akshare_shibor()
    on_rate, date_str = cache["shibor"]
    if log:
        log("    {}: OK = {}".format(ind.key, on_rate))
    return IndicatorResult(definition=ind, value=on_rate, obs_date=date_str)


def _collect_akshare_tsf(ind: IndicatorDef, cache: dict, log) -> IndicatorResult:
    if "tsf" not in cache:
        cache["tsf"] = _fetch_akshare_tsf()
    tsf, date_str = cache["tsf"]
    if log:
        log("    {}: OK = {}".format(ind.key, tsf))
    return IndicatorResult(definition=ind, value=tsf, obs_date=date_str)


HEADER_ZH = (
    "数据来源：东方财富数据中心 | 中国外汇交易中心 (LPR/SHIBOR) | 中国人民银行 (社融)；"
    "按月/季度更新。\"同比\"为相对去年同期变化。空缺（—）表示该项未取得或暂未发布。"
)
HEADER_EN = (
    "Sources: East Money Data Center | CFETS (LPR/SHIBOR) | PBoC (TSF); "
    "updated monthly/quarterly. \"YoY\" = year-over-year. "
    "A dash (—) means the item is unavailable or not yet released."
)


def _source_label(source: str) -> str:
    labels = {
        "eastmoney": "East Money",
        "akshare_lpr": "CFETS",
        "akshare_shibor": "CFETS",
        "akshare_tsf": "PBoC",
    }
    return labels.get(source, source)


def render_table(results: list[IndicatorResult]) -> str:
    ok = sum(1 for r in results if r.error is None)
    coverage = "覆盖 {}/{} 项 | Coverage {}/{}".format(ok, len(results), ok, len(results))

    columns = ("指标 Indicator", "最新值 Latest", "日期 Date", "来源 Source")
    rows = []
    for r in results:
        name = "{} {}".format(r.definition.zh, r.definition.en)
        source = _source_label(r.definition.source)
        unit = r.definition.unit
        if r.error and r.value is None:
            rows.append([name, "[{}]".format(r.error), "—", source])
        elif r.value is None:
            rows.append([name, "—", r.obs_date or "—", source])
        else:
            if r.definition.value_is_int:
                val_str = "{:,.0f}{}".format(r.value, unit)
            elif r.value >= 10:
                val_str = "{:.1f}{}".format(r.value, unit)
            else:
                val_str = "{:.2f}{}".format(r.value, unit)
            rows.append([name, val_str, r.obs_date or "—", source])

    header = "| " + " | ".join(columns) + " |"
    divider = "| " + " | ".join("---" for _ in columns) + " |"
    body = ["| " + " | ".join(row) + " |" for row in rows]
    table = "\n".join([header, divider, *body])
    return "{}\n\n{}\n\n{}\n\n{}".format(HEADER_ZH, HEADER_EN, table, coverage)
