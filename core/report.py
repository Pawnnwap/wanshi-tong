import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable

from core.base import ModuleResult
from core.context import RunContext


ANALYSIS_HEADING = "## Deep Cross-Domain Analysis"
_CHINESE_DATE_RE = re.compile(r"(?:(\d{4})年)?(\d{1,2})月(\d{1,2})日")
_ISO_DATE_RE = re.compile(r"(?<!\d)(\d{4})-(\d{1,2})-(\d{1,2})(?!\d)")


def render_report(
    module_results: Iterable[ModuleResult],
    analysis: str,
    context: RunContext,
) -> str:
    sections = [f"# Wanshi Tong Daily Briefing . {context.today:%Y-%m-%d}"]
    for result in module_results:
        content = f"[{result.error}]" if result.error else result.content.strip()
        sections.append(f"## {result.title}\n\n{content}")
    if analysis:
        sections.append(f"{ANALYSIS_HEADING}\n\n{analysis.strip()}")
    sections.append(f"Report generated: {context.generated_at:%Y-%m-%d %H:%M:%S}")
    return "\n\n---\n\n".join(sections)


def save_report(content: str, path: str | Path) -> Path:
    report_path = Path(path)
    report_path.write_text(content, encoding="utf-8")
    return report_path


def cleanup_dates(content: str, allowed_dates=None, preserved_titles=None) -> str:
    """Remove stale collection lines while preserving historical analysis citations.

    Sections whose heading matches ``preserved_titles`` (e.g. authoritative,
    non-agentic market data) are kept verbatim: their dates are real and may be
    a last-trading-day close that legitimately falls outside yesterday/today.
    """
    allowed = _normalize_allowed_dates(allowed_dates)
    allowed_month_days = {(value.month, value.day) for value in allowed}
    preserved = {title.strip() for title in (preserved_titles or ())}
    cleaned_lines = []
    in_analysis = False
    in_preserved = False

    for line in content.splitlines():
        stripped = line.strip()
        if stripped == ANALYSIS_HEADING:
            in_analysis = True
        elif stripped.startswith("## "):
            in_preserved = stripped[len("## "):].strip() in preserved
        if (
            in_analysis
            or in_preserved
            or not _has_disallowed_date(line, allowed, allowed_month_days)
        ):
            cleaned_lines.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(cleaned_lines))


def _normalize_allowed_dates(values) -> set[date]:
    if values is None:
        today = date.today()
        return {today - timedelta(days=1), today}
    return {
        value.date() if isinstance(value, datetime) else value
        for value in values
    }


def _has_disallowed_date(
    line: str,
    allowed: set[date],
    allowed_month_days: set[tuple[int, int]],
) -> bool:
    for year, month, day in _CHINESE_DATE_RE.findall(line):
        if year:
            value = _to_date(year, month, day)
            if value is not None and value not in allowed:
                return True
        elif (int(month), int(day)) not in allowed_month_days:
            return True

    for parts in _ISO_DATE_RE.findall(line):
        value = _to_date(*parts)
        if value is not None and value not in allowed:
            return True
    return False


def _to_date(year: str, month: str, day: str) -> date | None:
    try:
        return date(int(year), int(month), int(day))
    except ValueError:
        return None
