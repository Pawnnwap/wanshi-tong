# 万事通 (Wanshi Tong)

[![English](https://img.shields.io/badge/lang-English-blue)](README.md)

基于 [opencode](https://github.com/anomalyco/opencode) 和 MCP 工具服务器的自动化每日新闻简报系统。

覆盖 **5 个领域**的中英文新闻采集，按重要性过滤，进行跨领域分析，并以 Markdown 格式推送到飞书。

## 架构

```
模块 (6+)        -->  双语 AI 搜索（每个模块中 + 英）
    |
合并              -->  合并中英文结果
    |
过滤 (1 个）      -->  AI 重要性评分（>= 7 保留）
    |
分析器 (1 个）    -->  深度跨领域战略分析
    |
报告器 (1 个）    -->  飞书 Webhook 推送
```

自动发现：`core/registry.py` 通过 `pkgutil` 自动发现模块、过滤器、分析器和报告器。`modules/catalog.py` 包含共享的宏观指标目录常量。

所有组件通过 `pkgutil` 自动发现 —— 在 `modules/` 下新建 `.py` 文件即可，无需注册。`modules/catalog.py` 提供宏观指标的共享常量。日期敏感型新闻采集器继承 `modules/news.py` 中的 `NewsModule`，表格/结构化数据采集器继承 `modules/structured_data.py` 中的 `StructuredDataModule`。确定性的非智能体采集器（如 `asset_prices`）继承 `core/base.py` 中的 `LocalModule`，直接用 Python 拉取数据而不驱动大模型。

运行职责按模块拆分：`core/context.py` 统一管理运行时间和日期模板，`core/pipeline.py` 编排组件，`core/process.py` 执行带空闲进度监控的子进程，`core/report.py` 负责报告渲染和日期清理，`core/registry.py` 处理所有组件类型的自动发现。新闻和结构化数据采集器分别继承 `modules/news.py` 与 `modules/structured_data.py` 的共享提示词策略。

## 前置条件

- **Python 3.10+**
- **Node.js 18+**（用于 opencode CLI）
- 一个 **opencode** 账号（免费版即可）

## 快速开始

### 1. 安装 opencode CLI

```bash
npm install -g opencode-ai@latest
```

### 2. 认证 opencode

```bash
opencode auth login
```

这将在浏览器中打开配置页，选择 AI 提供商。免费模型（opencode/mimo-v2.5-free、opencode/deepseek-v4-flash-free 等）开箱即用。

### 3. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

### 4. 配置

在项目根目录创建 `config.json`：

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

`opencode.idle_timeout_s` 是空闲超时：子进程只要有输出就会重置计时，不存在总运行时长限制。旧的 `timeout_s` 键仍作为兼容别名支持。

如需飞书推送，创建 `credentials.json`：

```json
{
  "feishu_webhook": "https://open.feishu.cn/open-apis/bot/v2/hook/YOUR_HOOK_ID",
  "feishu_secret": "YOUR_SIGNING_SECRET"
}
```

### 5. 运行

```bash
python main.py
```

报告将保存为 `wanshi_tong_YYYYMMDD_HHMM.md`（项目根目录）。

## MCP 工具提供商

模块依赖以下 MCP（Model Context Protocol）服务器获取实时数据：

| 提供商 | 使用方 | 用途 |
|--------|--------|------|
| **newsmcp** | tech_news, social_news, political_news | 结构化新闻头条及元数据 |
| **financial-mcp** | macro_data | FRED 宏观数据 |
| **rss-news** | 所有新闻模块 | RSS 订阅聚合（备选方案） |
| **websearch** | 所有智能体模块 | 通用网页搜索补充细节 |

请确保这些 MCP 服务器已配置并在你的 opencode 环境中运行。配置指南见 [opencode 文档](https://opencode.ai)。

> **说明：** `asset_prices` 为**非智能体（non-agentic）**模块，完全不经过 opencode 或 MCP。它通过 [akshare](https://akshare.akfamily.xyz/) 从中国大陆可访问的数据源（东方财富、新浪、金十）确定性地拉取行情，因此在 `yfinance` 等境外数据源被墙的环境下仍可正常工作。详见 [本地（非智能体）数据模块](#本地非智能体数据模块)。

## 模块列表

| 模块 | 中文名称 | 覆盖范围 |
|------|----------|----------|
| tech_news | 科技新闻 | AI/LLM、半导体、电动车、航天、科技巨头 |
| social_news | 头条社会新闻 | 民生、教育、健康、环境、突发新闻 |
| political_news | 头条政经新闻 | 政策、外交、经济数据、地缘政治 |
| macro_data | 宏观最新数据与指标 | GDP、CPI、PMI、利率、油价（中国/美国/欧盟/日本） |
| asset_prices | 资产与股指价格及涨跌 | 23 项资产：股指、外汇、大宗商品、加密货币 —— **非智能体**（akshare），附 20日/60日/1年分位 |

## 添加模块

### 基础模块

在 `modules/` 下新建文件：

```python
from core.base import Module


class MyModule(Module):
    name = "my_module"
    title = "我的模块"
    model = ""  # 空 = 使用配置中的默认模型
    prompt_zh = "搜索{today_cn}发布的示例数据。输出中文并标注来源和日期。"
    prompt_en = "Find example data published on {today_en}. Include source and date."
```

### 日期敏感型新闻模块

继承 `modules/news.py` 中的 `NewsModule` 并设置类属性：

```python
from modules.news import NewsModule


class MyNewsModule(NewsModule):
    name = "my_news"
    title = "我的新闻"
    search_scope_zh = "示例新闻"
    search_scope_en = "example news"
    coverage_zh = "领域覆盖说明"
    coverage_en = "coverage description"
    sources_zh = "来源1, 来源2"
    sources_en = "Source 1, Source 2"
    empty_label_zh = "示例"
    empty_label_en = "example"
```

### 结构化/表格数据模块

继承 `modules/structured_data.py` 中的 `StructuredDataModule`：

```python
from modules.structured_data import StructuredDataModule


class MyDataModule(StructuredDataModule):
    name = "my_data"
    title = "我的数据"
    request_zh = "获取示例数据"
    request_en = "Get example data"
    rules_zh = ("规则1", "规则2")
    rules_en = ("Rule 1", "Rule 2")
    output_zh = "输出格式说明"
    output_en = "output format"
```

### 本地（非智能体）数据模块

对于应通过 API 而非大模型获取的确定性数据，继承 `core/base.py` 中的 `LocalModule` 并实现 `collect()`。它不产生 opencode 任务，流水线会直接调用 `collect()`；返回结果标记为 `authoritative`，重要性过滤器因此不会改动它。`preserve_dates`（默认 `True`）还会让该板块跳过报告的过期日期清理，因此周末/节假日的最后交易日收盘价不会被误删。

```python
from typing import Mapping

from core.base import LocalModule, ModuleResult


class MyLocalModule(LocalModule):
    name = "my_local"
    title = "我的本地数据"

    def collect(self, date_templates: Mapping[str, str] | None = None) -> ModuleResult:
        content = ...  # 确定性地拉取并格式化（不得抛异常）
        return ModuleResult(self.name, self.title, content, authoritative=True)
```

`asset_prices` 即参考实现：[modules/asset_prices.py](modules/asset_prices.py) 是一个轻量 `LocalModule`，而 [modules/market_data.py](modules/market_data.py) 承载数据拉取、重试/限速逻辑、23 项资产目录以及分位指标计算。每行给出最新收盘价、相对上一交易日的绝对与百分比涨跌，以及收盘价在其过去 20 日/60 日/1 个日历年窗口内的分位位置（0%＝区间最低，100%＝区间最高）和 1 年区间。

**多源容错：** 每项资产都配置了一组跨**不同主机**的 `Source`，按顺序尝试直到某个返回数据，因此没有任何单一数据源会成为单点故障（尤其东方财富限流较严）。全部数据均来自中国大陆可访问的端点：

| 资产类别 | 主源 | 备源 | 无新浪？ |
|---|---|---|---|
| A 股指数 | 腾讯 kline（qq.com） | 东方财富 | ✅ |
| 港股指数 | 腾讯 kline（qq.com） | 东方财富 | ✅ |
| 美股指数 | 腾讯 kline（qq.com） | 东方财富 | ✅ |
| 欧洲/日本指数 | 新浪（`index_global_hist_sina`） | 东方财富 | ❌ 无第三源 |
| 美元指数（DXY） | 东方财富（`index_global_hist_em`） | — | ✅ |
| 外汇对 | 东方财富（`forex_hist_em`） | CFETS 即期（chinamoney.com.cn） | ✅ |
| 大宗商品 | 新浪（`futures_foreign_hist`） | — | ❌ 无第三源 |
| 加密货币（BTC/ETH） | Kraken 公共 API | — | ✅ |

A 股/港股/美股指数与外汇**完全不经过新浪**。欧洲/日本指数与大宗商品在 akshare 中没有第三个中国大陆可访问源（仅有新浪和东方财富），因此这两类无法避开新浪（东方财富为欧洲/日本的备源）。

对于宏观指标常量，可从 `modules.catalog` 导入。任何模块类型都无需注册。

## 致谢

- **[opencode](https://github.com/anomalyco/opencode)** —— 驱动所有搜索、过滤和分析的 AI 执行引擎。没有 opencode 的免费模型和 MCP 集成，这个系统就不可能存在。
- **MCP 提供商**（newsmcp、financial-mcp、rss-news）—— 为 AI 代理提供实时新闻和市场数据的结构化数据源。

## 许可证

MIT
