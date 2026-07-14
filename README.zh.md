# 万事通 (Wanshi Tong)

[![English](https://img.shields.io/badge/lang-English-blue)](README.md)

基于 [opencode](https://github.com/anomalyco/opencode) 和 MCP 工具服务器的自动化每日新闻简报系统。

覆盖 **5 个领域**的中英文新闻采集，按重要性过滤，进行跨领域分析，并以 Markdown 格式推送到飞书。

## 架构

```
模块 (5 个）     -->  双语 AI 搜索（每个模块中 + 英）
    |
合并              -->  合并中英文结果
    |
过滤 (1 个）      -->  AI 重要性评分（>= 7 保留）
    |
分析器 (1 个）    -->  深度跨领域战略分析
    |
报告器 (1 个）    -->  飞书 Webhook 推送
```

所有组件通过 `pkgutil` 自动发现 —— 在 `modules/` 下新建 `.py` 文件即可，无需注册。

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
    "timeout_s": 600
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

如需飞书推送，创建 `credentials.json`：

`opencode.timeout_s` 是空闲超时：子进程只要有输出就会重置计时，不是总运行时长限制。

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
| **financial-mcp** | macro_data, asset_prices | FRED 宏观数据、股票报价、外汇、加密货币 |
| **rss-news** | 所有新闻模块 | RSS 订阅聚合（备选方案） |
| **websearch** | 所有模块 | 通用网页搜索补充细节 |

请确保这些 MCP 服务器已配置并在你的 opencode 环境中运行。配置指南见 [opencode 文档](https://opencode.ai)。

## 模块列表

| 模块 | 中文名称 | 覆盖范围 |
|------|----------|----------|
| tech_news | 科技新闻 | AI/LLM、半导体、电动车、航天、科技巨头 |
| social_news | 头条社会新闻 | 民生、教育、健康、环境、突发新闻 |
| political_news | 头条政经新闻 | 政策、外交、经济数据、地缘政治 |
| macro_data | 宏观最新数据与指标 | GDP、CPI、PMI、利率、油价（中国/美国/欧盟/日本） |
| asset_prices | 资产与股指价格及涨跌 | 主要股指、外汇、大宗商品、加密货币 |

## 添加模块

在 `modules/` 下新建文件：

```python
from core.base import Module, _DATE_RULES_ZH, _DATE_RULES_EN, _FORMAT_ZH, _FORMAT_EN


class MyModule(Module):
    name = "my_module"
    title = "My Title"
    model = ""  # 空 = 尝试所有备用模型

    prompt_zh = f"""
你是...请搜索...的新闻。
## 日期红线（必须遵守）
{_DATE_RULES_ZH}
{_FORMAT_ZH}"""

    prompt_en = f"""
You are... Search for... news.
## Date Red Lines (MUST follow)
{_DATE_RULES_EN}
{_FORMAT_EN}"""
```

无需注册——下次运行时自动发现。

## 致谢

- **[opencode](https://github.com/anomalyco/opencode)** —— 驱动所有搜索、过滤和分析的 AI 执行引擎。没有 opencode 的免费模型和 MCP 集成，这个系统就不可能存在。
- **MCP 提供商**（newsmcp、financial-mcp、rss-news）—— 为 AI 代理提供实时新闻和市场数据的结构化数据源。

## 许可证

MIT
