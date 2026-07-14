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


def cleanup_dates(content: str, allowed_dates=None) -> str:
    """Remove stale collection lines while preserving historical analysis citations."""
    allowed = _normalize_allowed_dates(allowed_dates)
    allowed_month_days = {(value.month, value.day) for value in allowed}
    cleaned_lines = []
    in_analysis = False

    for line in content.splitlines():
        if line.strip() == ANALYSIS_HEADING:
            in_analysis = True
        if in_analysis or not _has_disallowed_date(line, allowed, allowed_month_days):
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
