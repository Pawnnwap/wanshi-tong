# Wanshi Tong

[![中文版](https://img.shields.io/badge/lang-中文-red)](README.zh.md)

Automated daily news briefing system powered by [opencode](https://github.com/anomalyco/opencode) and MCP tool servers.

Collects news across 5 domains in **Chinese + English**, filters by importance, runs cross-domain analysis, and delivers a Markdown report to Feishu (Lark).

## Architecture

```
Modules (6+)       -->  Bilingual AI Search (zh + en per module)
    |
Merge              -->  Combine Chinese + English results
    |
Filter (1)         -->  AI importance scoring (>= 7 kept)
    |
Analyzer (1)       -->  Deep cross-domain strategic analysis
    |
Reporter (1)       -->  Feishu webhook delivery
```

Discovery: `core/registry.py` auto-discovers modules, filters, analyzers, and reporters via `pkgutil`. Shared catalog constants (macro indicators) are in `modules/catalog.py`.

All components are auto-discovered via pkgutil -- drop a new .py file in modules/ and it just works. Shared constants for macro indicators live in `modules/catalog.py`. Date-sensitive news collectors inherit `NewsModule` from `modules/news.py`, and tabular/structured collectors inherit `StructuredDataModule` from `modules/structured_data.py`. Deterministic, non-agentic collectors (e.g. `asset_prices`) inherit `LocalModule` from `core/base.py` and fetch data directly in Python instead of driving an LLM.

Runtime responsibilities are split across focused modules: `core/context.py` owns the run timestamp and date templates, `core/pipeline.py` coordinates components, `core/process.py` runs idle-aware subprocesses, `core/report.py` renders and cleans reports, and `core/registry.py` handles auto-discovery of all component types. News and structured-data collectors inherit shared prompt policies from `modules/news.py` and `modules/structured_data.py`.

## Prerequisites

- **Python 3.10+**
- **Node.js 18+** (for the opencode CLI)
- An **opencode** account with API access (free tier works)

## Quick Start

### 1. Install opencode CLI

```bash
npm install -g opencode-ai@latest
```

### 2. Authenticate opencode

```bash
opencode auth login
```

This opens a browser to configure your AI provider. The free models (opencode/mimo-v2.5-free, opencode/deepseek-v4-flash-free, etc.) work out of the box.

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure

Create config.json in the project root:

```json
{
  "opencode": {
    "permissions": {},
    "idle_timeout_s": 600
  },
  "parallel": {
    "max_workers": 5
  },
  "feishu": {
    "max_chars_per_msg": 1200,
    "max_attempts": 3,
    "retry_delay_s": 2
  }
}
```

`opencode.idle_timeout_s` resets whenever the subprocess emits output; there is no total runtime limit. The legacy `timeout_s` key remains supported as an alias.

For Feishu delivery, create credentials.json:

```json
{
  "feishu_webhook": "https://open.feishu.cn/open-apis/bot/v2/hook/YOUR_HOOK_ID",
  "feishu_secret": "YOUR_SIGNING_SECRET"
}
```

### 5. Run

```bash
python main.py
```

The report is saved as wanshi_tong_YYYYMMDD_HHMM.md in the project root.

## MCP Tool Providers

The modules rely on these MCP (Model Context Protocol) servers for real-time data:

| Provider | Used By | Purpose |
|----------|---------|---------|
| **newsmcp** | tech_news, social_news, political_news | Structured news headlines with metadata |
| **financial-mcp** | macro_data | FRED macro series |
| **rss-news** | All news modules | RSS feed aggregation as fallback |
| **websearch** | All agentic modules | General web search for supplementary detail |

Make sure these MCP servers are configured and running in your opencode environment. See [opencode docs](https://opencode.ai) for setup instructions.

> **Note:** `asset_prices` is **non-agentic** — it does not use opencode or MCP at all. It fetches market data deterministically via [akshare](https://akshare.akfamily.xyz/) from mainland-China-accessible endpoints (East Money, Sina, Jin10), so it works where `yfinance` and other overseas providers are blocked. See [Local (non-agentic) data module](#local-non-agentic-data-module).

## Modules

| Module | ZH Title | Coverage |
|--------|----------|----------|
| tech_news | 科技新闻 | AI/LLM, semiconductors, EVs, space, big tech |
| social_news | 头条社会新闻 | Livelihood, education, health, environment, breaking news |
| political_news | 头条政经新闻 | Policy, diplomacy, economic data, geopolitics |
| macro_data | 宏观最新数据与指标 | GDP, CPI, PMI, rates, oil (China/US/EU/JP) |
| asset_prices | 资产与股指价格及涨跌 | 23 assets: indices, forex, commodities, crypto — **non-agentic** (akshare), with 20d/60d/1y percentile position |

## Adding a Module

### Basic module

Create a new file in `modules/`:

```python
from core.base import Module


class MyModule(Module):
    name = "my_module"
    title = "My Title"
    model = ""  # empty = use the configured default model
    prompt_zh = "搜索{today_cn}发布的示例数据。输出中文并标注来源和日期。"
    prompt_en = "Find example data published on {today_en}. Include source and date."
```

### Date-sensitive news module

Inherit `NewsModule` from `modules/news.py` and set class attributes:

```python
from modules.news import NewsModule


class MyNewsModule(NewsModule):
    name = "my_news"
    title = "My News"
    search_scope_zh = "示例新闻"
    search_scope_en = "example news"
    coverage_zh = "领域覆盖说明"
    coverage_en = "coverage description"
    sources_zh = "来源1, 来源2"
    sources_en = "Source 1, Source 2"
    empty_label_zh = "示例"
    empty_label_en = "example"
```

### Structured/tabular data module

Inherit `StructuredDataModule` from `modules/structured_data.py`:

```python
from modules.structured_data import StructuredDataModule


class MyDataModule(StructuredDataModule):
    name = "my_data"
    title = "My Data"
    request_zh = "获取示例数据"
    request_en = "Get example data"
    rules_zh = ("规则1", "规则2")
    rules_en = ("Rule 1", "Rule 2")
    output_zh = "输出格式说明"
    output_en = "output format"
```

### Local (non-agentic) data module

For deterministic data that should come from an API rather than an LLM, inherit `LocalModule` from `core/base.py` and implement `collect()`. It emits no opencode tasks; the pipeline calls `collect()` directly, and the result is marked `authoritative` so the importance filter leaves it untouched. `preserve_dates` (default `True`) also keeps its section out of the report's stale-date cleanup, so a last-trading-day close over a weekend is never dropped.

```python
from typing import Mapping

from core.base import LocalModule, ModuleResult


class MyLocalModule(LocalModule):
    name = "my_local"
    title = "My Local Data"

    def collect(self, date_templates: Mapping[str, str] | None = None) -> ModuleResult:
        content = ...  # fetch + format deterministically (must not raise)
        return ModuleResult(self.name, self.title, content, authoritative=True)
```

`asset_prices` is the reference implementation: [modules/asset_prices.py](modules/asset_prices.py) is a thin `LocalModule`, and [modules/market_data.py](modules/market_data.py) holds the fetching, retry/spacing logic, the 23-asset catalog, and the percentile-metric computation. Each row reports the latest close, absolute and percent change vs. the prior session, and the close's percentile position within its trailing 20-day / 60-day / 1-calendar-year window (0% = window low, 100% = window high) plus the 1-year range.

**Multi-host fallback:** every asset lists an ordered set of `Source`s spanning **different hosts**, tried until one returns data, so no single provider is a single point of failure (East Money in particular rate-limits aggressively). Data flows entirely from mainland-China-accessible endpoints:

| Asset class | Primary source | Fallback(s) | Sina-free? |
|---|---|---|---|
| China A-share indices | Tencent kline (qq.com) | East Money | ✅ |
| Hong Kong indices | Tencent kline (qq.com) | East Money | ✅ |
| US indices | Tencent kline (qq.com) | East Money | ✅ |
| Europe / Japan indices | Sina (`index_global_hist_sina`) | East Money | ❌ no 3rd source |
| Dollar index (DXY) | East Money (`index_global_hist_em`) | — | ✅ |
| Forex pairs | East Money (`forex_hist_em`) | CFETS spot (chinamoney.com.cn) | ✅ |
| Commodities | Sina (`futures_foreign_hist`) | — | ❌ no 3rd source |
| Crypto (BTC/ETH) | Kraken public API | — | ✅ |

China/HK/US indices and forex involve **no Sina**. Europe/Japan indices and commodities have no third China-accessible source in akshare — only Sina and East Money exist — so Sina is unavoidable there (East Money is the EU/JP fallback).

For catalog constants (macro indicators), import from `modules.catalog`. No registration is needed for any module type.

## Acknowledgements

- **[opencode](https://github.com/anomalyco/opencode)** -- The AI execution engine that powers all search, filtering, and analysis in this project. Without opencode's free-tier models and MCP integration, this system wouldn't exist.
- **MCP providers** (newsmcp, financial-mcp, rss-news) -- Real-time structured data sources that give the AI agents access to live news and market data.

## License

MIT
