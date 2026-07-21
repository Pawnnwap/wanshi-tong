from typing import Mapping

from core.base import LocalModule, ModuleResult
from modules.market_data import collect_metrics, render_table


class AssetPricesModule(LocalModule):
    """Global asset prices, collected deterministically via akshare.

    Replaces the former agentic collector (LLM + financial MCP tools), which
    could not reach data providers from mainland China and failed unreliably.
    Now pulls daily history from mainland-accessible endpoints and reports each
    asset with its absolute change plus 20-day / 60-day / 1-year percentile
    position, so the analyzer can judge where prices sit in their own range.
    """

    name = "asset_prices"
    title = "【资产与股指价格及涨跌】"

    def collect(self, date_templates: Mapping[str, str] | None = None) -> ModuleResult:
        metrics = collect_metrics(log=self._log)
        content = render_table(metrics)
        failed = [m.asset.key for m in metrics if m.error is not None]
        error = None
        if len(failed) == len(metrics):
            error = "asset data collection failed for all items"
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
