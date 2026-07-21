import time
from collections import Counter
from dataclasses import dataclass
from typing import Callable, Sequence

from core.base import Analyzer, Filter, LocalModule, Module, ModuleResult, Reporter, Task
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
    log(f"[step 4/8] agentic collection done ({time.monotonic() - started_at:.1f}s)")
    return dict(zip((task.name for task in tasks), raw_results, strict=True))


def collect_local(
    modules: Sequence[Module],
    date_templates: dict[str, str] | None,
    log: Log,
) -> dict[str, ModuleResult]:
    """Run every LocalModule's ``collect()`` first, before agentic tasks.

    Non-agentic data fetching (asset prices, Chinese macro indicators, 新闻联播)
    is deterministic and bounded, so it runs ahead of -- and never waits on --
    the slower LLM-driven agentic collection loop. Returns a name->result dict
    so the merge step can slot the local results back in without re-fetching.
    """
    local_modules = [m for m in modules if isinstance(m, LocalModule)]
    local_results: dict[str, ModuleResult] = {}
    if not local_modules:
        return local_results
    log(f"  {len(local_modules)} non-agentic modules, collecting first...")
    for module in local_modules:
        local_results[module.name] = _collect_local(module, date_templates, log)
    return local_results


def merge_results(
    modules: Sequence[Module],
    results_by_task: dict[str, str],
    log: Log,
    date_templates: dict[str, str] | None = None,
    local_results: dict[str, ModuleResult] | None = None,
) -> list[ModuleResult]:
    """Combine agentic task results with pre-collected local module results.

    ``local_results`` (produced by :func:`collect_local`) supplies the
    LocalModule outputs collected before the agentic loop; if absent, the
    local collection is performed inline for backward compatibility.
    """
    local_results = local_results or {}
    module_results = []
    for module in modules:
        if isinstance(module, LocalModule):
            if module.name in local_results:
                module_results.append(local_results[module.name])
            else:
                module_results.append(_collect_local(module, date_templates, log))
        else:
            module_results.append(_merge_agentic(module, results_by_task, log))
    return module_results


def _merge_agentic(
    module: Module,
    results_by_task: dict[str, str],
    log: Log,
) -> ModuleResult:
    zh_raw = results_by_task[f"{module.name}_zh"]
    en_raw = results_by_task[f"{module.name}_en"]
    combined = module.combine_results(zh_raw, en_raw)
    log(f"  {module.name}: zh={len(zh_raw)}c + en={len(en_raw)}c = {len(combined)}c")
    return module.parse_result(combined)


def _collect_local(
    module: LocalModule,
    date_templates: dict[str, str] | None,
    log: Log,
) -> ModuleResult:
    log(f"  {module.name}: collecting locally (non-agentic)...")
    started_at = time.monotonic()
    try:
        result = module.collect(date_templates)
    except Exception as exc:  # noqa: BLE001 -- keep the pipeline alive on data failures
        log(f"  {module.name}: local collection failed: {exc}")
        return ModuleResult(name=module.name, title=module.title, content="", error=str(exc))
    log(f"  {module.name}: local collection done ({time.monotonic() - started_at:.1f}s, {len(result.content)}c)")
    return result


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
