import time
from collections import Counter
from dataclasses import dataclass
from typing import Callable, Sequence

from core.base import Analyzer, Filter, Module, ModuleResult, Reporter, Task
from core.opencode_client import run_parallel
from core.registry import (
    discover_analyzers,
    discover_filters,
    discover_modules,
    discover_reporters,
)


Log = Callable[[str], None]


@dataclass(frozen=True)
class Components:
    modules: list[Module]
    filters: list[Filter]
    analyzers: list[Analyzer]
    reporters: list[Reporter]

    @classmethod
    def discover(cls) -> "Components":
        return cls(
            modules=discover_modules(),
            filters=discover_filters(),
            analyzers=discover_analyzers(),
            reporters=discover_reporters(),
        )


def collect_tasks(
    modules: Sequence[Module],
    date_templates: dict[str, str],
    log: Log,
) -> dict[str, str]:
    tasks = [
        Task.from_value(task)
        for module in modules
        for task in module.get_tasks(date_templates)
    ]
    _ensure_unique_task_names(tasks)
    log(f"  {len(tasks)} tasks ({len(modules)} modules x 2 languages), running in parallel...")

    started_at = time.monotonic()
    raw_results = run_parallel(tasks)
    log(f"[step 3/7] collection done ({time.monotonic() - started_at:.1f}s)")
    return dict(zip((task.name for task in tasks), raw_results, strict=True))


def merge_results(
    modules: Sequence[Module],
    results_by_task: dict[str, str],
    log: Log,
) -> list[ModuleResult]:
    module_results = []
    for module in modules:
        zh_raw = results_by_task[f"{module.name}_zh"]
        en_raw = results_by_task[f"{module.name}_en"]
        combined = module.combine_results(zh_raw, en_raw)
        module_results.append(module.parse_result(combined))
        log(f"  {module.name}: zh={len(zh_raw)}c + en={len(en_raw)}c = {len(combined)}c")
    return module_results


def apply_filters(
    module_results: Sequence[ModuleResult],
    filters: Sequence[Filter],
    log: Log,
) -> list[ModuleResult]:
    filtered = list(module_results)
    for result_filter in filters:
        log(f"  {result_filter.name} filtering per module...")
        for index, result in enumerate(filtered):
            filtered[index] = result_filter.filter(result)
            log(f"    {result.name}: {len(result.content)}c -> {len(filtered[index].content)}c")
    return filtered


def analyze_results(
    module_results: Sequence[ModuleResult],
    analyzers: Sequence[Analyzer],
    log: Log,
) -> str:
    reports = []
    for analyzer in analyzers:
        log(f"  {analyzer.name} starting (model={analyzer.model})...")
        started_at = time.monotonic()
        report = analyzer.analyze(list(module_results))
        reports.append(report)
        log(f"  {analyzer.name} done ({time.monotonic() - started_at:.1f}s, {len(report)}c)")
    return "\n\n".join(report.strip() for report in reports if report.strip())


def deliver_report(
    reporters: Sequence[Reporter],
    title: str,
    content: str,
    log: Log,
) -> None:
    errors = []
    for reporter in reporters:
        log(f"  {reporter.name} sending...")
        try:
            reporter.send(title, content)
            log(f"  {reporter.name} sent")
        except Exception as exc:
            log(f"  {reporter.name} failed: {exc}")
            errors.append(f"{reporter.name}: {exc}")
    if errors:
        raise RuntimeError("report delivery failed: " + "; ".join(errors))


def _ensure_unique_task_names(tasks: Sequence[Task]) -> None:
    counts = Counter(task.name for task in tasks)
    duplicates = sorted(name for name, count in counts.items() if count > 1)
    if duplicates:
        raise ValueError("duplicate task names: " + ", ".join(duplicates))
