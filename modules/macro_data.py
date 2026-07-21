"""Chinese macro data, collected deterministically via East Money API.

Replaces the former agentic (LLM + MCP tool) approach, which relied on
jin10.com via akshare (data became stale by Aug-Sep 2025) and was prone
to LLM hallucination on exact dates. Now pulls current data directly
from the East Money datacenter, validated through June 2026.

Covered: CPI, PPI, PMI (mfg + non-mfg), GDP, M2/M1/M0, forex reserves,
gold reserves, trade (exports/imports), new RMB loans.
"""

from typing import Mapping

from core.base import LocalModule, ModuleResult
from modules.macros_china import collect_indicators, render_table


class MacroDataModule(LocalModule):
    name = "macro_data"
    title = "【宏观最新数据与指标】"

    def collect(self, date_templates: Mapping[str, str] | None = None) -> ModuleResult:
        results = collect_indicators(log=self._log)
        content = render_table(results)
        failed = [r.definition.key for r in results if r.error is not None]
        error = None
        if len(failed) == len(results):
            error = "macro data collection failed for all indicators"
        return ModuleResult(
            name=self.name,
            title=self.title,
            content=content,
            error=error,
            authoritative=True,
        )

    @staticmethod
    def _log(message: str) -> None:
        print(message, flush=True)
