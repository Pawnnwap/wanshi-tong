#!/usr/bin/env python3
"""Wanshi Tong daily briefing pipeline."""

import time
from datetime import datetime

from core.context import RunContext
from core.opencode_client import update_opencode
from core.pipeline import (
    Components,
    analyze_results,
    apply_filters,
    collect_local,
    collect_tasks,
    deliver_report,
    merge_results,
)
from core.report import cleanup_dates, render_report, save_report


def log(message: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {message}", flush=True)


def main() -> None:
    context = RunContext.current()
    log("=" * 60)
    log("Wanshi Tong Daily Briefing -- starting")
    log("=" * 60)

    log("[step 1/8] Discovering components...")
    components = Components.discover()
    log(
        f"  modules: {len(components.modules)} | filters: {len(components.filters)} | "
        f"analyzers: {len(components.analyzers)} | reporters: {len(components.reporters)}"
    )

    log("[step 2/8] Local data collection (non-agentic, runs first -- before opencode/agentic)...")
    started_at = time.monotonic()
    local_results = collect_local(components.modules, context.date_templates, log)
    log(f"[step 2/8] local done ({time.monotonic() - started_at:.1f}s, {len(local_results)} modules)")

    log("[step 3/8] Auto-upgrading opencode (agentic infra)...")
    started_at = time.monotonic()
    update_opencode()
    log(f"[step 3/8] done ({time.monotonic() - started_at:.1f}s)")

    log("[step 4/8] Bilingual search collection (agentic)...")
    task_results = collect_tasks(components.modules, context.date_templates, log)

    log("[step 5/8] Merging results...")
    module_results = merge_results(
        components.modules, task_results, log, context.date_templates, local_results
    )
    log("[step 5/8] merge done")

    if components.filters:
        log(f"[step 6/8] Importance filtering ({len(components.filters)} filter(s))...")
        started_at = time.monotonic()
        module_results = apply_filters(module_results, components.filters, log)
        log(f"[step 6/8] filter done ({time.monotonic() - started_at:.1f}s)")
    else:
        log("[step 6/8] no filters, skipping")

    log("[step 7/8] Deep cross-domain analysis...")
    analysis = analyze_results(module_results, components.analyzers, log)
    log("[step 7/8] analysis done")

    log("[step 8/8] Assembling report...")
    report = render_report(module_results, analysis, context)
    preserved_titles = [
        module.title
        for module in components.modules
        if getattr(module, "preserve_dates", False)
    ]
    report = cleanup_dates(report, context.allowed_dates, preserved_titles)
    report_path = save_report(report, context.report_filename)
    log(f"  report length: {len(report)}c")
    log(f"  saved: {report_path}")

    deliver_report(components.reporters, "Wanshi Tong Daily", report, log)
    log("=" * 60)
    log("Wanshi Tong Daily Briefing -- done")
    log("=" * 60)


if __name__ == "__main__":
    main()
