# Wanshi Tong

[![中文版](https://img.shields.io/badge/lang-中文-red)](README.zh.md)

Automated daily news briefing system powered by [opencode](https://github.com/anomalyco/opencode) and MCP tool servers.

Collects news across 5 domains in **Chinese + English**, filters by importance, runs cross-domain analysis, and delivers a Markdown report to Feishu (Lark).

## Architecture

```
Modules (5)        -->  Bilingual AI Search (zh + en per module)
    |
Merge              -->  Combine Chinese + English results
    |
Filter (1)         -->  AI importance scoring (>= 7 kept)
    |
Analyzer (1)       -->  Deep cross-domain strategic analysis
    |
Reporter (1)       -->  Feishu webhook delivery
```

All components are auto-discovered via pkgutil -- drop a new .py file in modules/ and it just works.

Runtime responsibilities are split across focused modules: `core/context.py` owns the run timestamp and date templates, `core/pipeline.py` coordinates components, `core/process.py` runs idle-aware subprocesses, and `core/report.py` renders and cleans reports. News and structured-data collectors inherit shared prompt policies from `modules/news.py` and `modules/structured_data.py`.

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
| **financial-mcp** | macro_data, asset_prices | FRED macro series, stock quotes, forex, crypto |
| **rss-news** | All news modules | RSS feed aggregation as fallback |
| **websearch** | All modules | General web search for supplementary detail |

Make sure these MCP servers are configured and running in your opencode environment. See [opencode docs](https://opencode.ai) for setup instructions.

## Modules

| Module | ZH Title | Coverage |
|--------|----------|----------|
| tech_news | 科技新闻 | AI/LLM, semiconductors, EVs, space, big tech |
| social_news | 头条社会新闻 | Livelihood, education, health, environment, breaking news |
| political_news | 头条政经新闻 | Policy, diplomacy, economic data, geopolitics |
| macro_data | 宏观最新数据与指标 | GDP, CPI, PMI, rates, oil (China/US/EU/JP) |
| asset_prices | 资产与股指价格及涨跌 | Major indices, forex, commodities, crypto |

## Adding a Module

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

For date-sensitive news or tabular datasets, inherit `NewsModule` or `StructuredDataModule` to reuse the shared prompt policy. No registration is needed.

## Acknowledgements

- **[opencode](https://github.com/anomalyco/opencode)** -- The AI execution engine that powers all search, filtering, and analysis in this project. Without opencode's free-tier models and MCP integration, this system wouldn't exist.
- **MCP providers** (newsmcp, financial-mcp, rss-news) -- Real-time structured data sources that give the AI agents access to live news and market data.

## License

MIT
