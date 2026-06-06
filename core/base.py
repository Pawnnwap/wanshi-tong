from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class ModuleResult:
    name: str
    title: str
    content: str
    model: str = ""
    error: Optional[str] = None


class Module(ABC):
    """Abstract base class for search modules. Subclass and set class attributes."""
    name: str = ""
    title: str = ""
    model: str = ""
    prompt_zh: str = ""
    prompt_en: str = ""

    def get_tasks(self) -> list[dict]:
        """Return two tasks: one Chinese, one English."""
        return [
            {"name": f"{self.name}_zh", "prompt": self.prompt_zh, "model": self.model},
            {"name": f"{self.name}_en", "prompt": self.prompt_en, "model": self.model},
        ]

    def combine_results(self, zh_result: str, en_result: str) -> str:
        """Merge Chinese and English search results. Override for custom logic."""
        return f"=== Chinese Search Results ===\n{zh_result}\n\n=== English Search Results ===\n{en_result}"

    def parse_result(self, raw: str) -> ModuleResult:
        return ModuleResult(
            name=self.name,
            title=self.title,
            content=raw,
            model=self.model,
        )


class Filter(ABC):
    """Abstract base class for importance filters."""
    name: str = ""
    model: str = ""

    @abstractmethod
    def filter(self, module_result: ModuleResult) -> ModuleResult:
        """Filter a single module result; return filtered result."""
        ...


class Analyzer(ABC):
    """Abstract base class for deep analyzers."""
    name: str = ""
    model: str = ""

    @abstractmethod
    def analyze(self, module_results: list[ModuleResult]) -> str:
        ...


class Reporter(ABC):
    """Abstract base class for report delivery."""
    name: str = ""

    @abstractmethod
    def send(self, title: str, content: str) -> None:
        ...


_DATE_RULES_ZH = """
- 禁止包含任何发布日期早于2026年6月5日的新闻
- 禁止包含任何发布日晚于2026年6月6日的新闻（未来日期）
- 只允许 2026年6月5日（昨天）或 2026年6月6日（今天）的新闻
- 搜到不符合日期条件的内容 → 直接丢弃"""

_DATE_RULES_EN = """
- DO NOT include any news published before June 5, 2026
- DO NOT include any news published after June 6, 2026 (future dates)
- ONLY include news from June 5 (yesterday) or June 6 (today) 2026
- Discard any content that doesn't meet the date requirement"""

_TOOLS_ZH = """## Available Tools (priority order)
1. **newsmcp get_news** (preferred): Get real-time structured news directly
2. **websearch**: Supplement with keyword searches
3. **rss-news fetch_news**: Get news from RSS feed subscriptions"""

_TOOLS_EN = """## Available Tools (priority order)
1. **newsmcp get_news** (preferred): Get real-time structured news directly
2. **websearch**: Supplement with keyword searches
3. **rss-news fetch_news**: Get news from RSS feed subscriptions"""

_FORMAT_ZH = "Output format per item: **[Title]** | Summary | Source | **June X, 2026**\nCurrent date: June 6, 2026"
_FORMAT_EN = "Output format per item: **[Title]** | Summary | Source | **June X, 2026**\nCurrent date: June 6, 2026"
