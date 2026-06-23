#!/usr/bin/env python3
"""Wanshi Tong -- Auto-discovering modular scheduler (bilingual search)"""
import time
from datetime import datetime, timedelta

from core.registry import discover_modules, discover_analyzers, discover_reporters, discover_filters
from core.opencode_client import run_parallel, update_opencode
from reporters.feishu import cleanup_dates


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def main():
    log("=" * 60)
    log("Wanshi Tong Daily Briefing -- starting")
    log("=" * 60)

    # ---- Auto-upgrade opencode on startup ----
    log("[step 1/7] Auto-upgrading opencode...")
    t0 = time.time()
    update_opencode()
    log(f"[step 1/7] done ({time.time()-t0:.1f}s)")

    # ---- Discover modules ----
    log("[step 2/7] Discovering modules...")
    modules = discover_modules()
    analyzers = discover_analyzers()
    reporters = discover_reporters()
    log(f"  modules: {len(modules)} | analyzers: {len(analyzers)} | reporters: {len(reporters)}")

    date_str = datetime.now().strftime('%Y-%m-%d')

    yesterday = datetime.now() - timedelta(days=1)
    today = datetime.now()
    date_templates = {
        "yesterday_cn": f"{yesterday.year}年{yesterday.month}月{yesterday.day}日",
        "today_cn": f"{today.year}年{today.month}月{today.day}日",
        "yesterday_en": f"{yesterday.strftime('%B')} {yesterday.day}, {yesterday.year}",
        "today_en": f"{today.strftime('%B')} {today.day}, {today.year}",
        "yesterday_short_cn": f"{yesterday.month}月{yesterday.day}日",
        "today_short_cn": f"{today.month}月{today.day}日",
        "yesterday_day": str(yesterday.day),
        "today_day": str(today.day),
        "month_en": today.strftime('%B'),
        "year": str(today.year),
    }
    time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # ---- Collection (bilingual search per module) ----
    log("[step 3/7] Bilingual search collection...")
    all_tasks = []
    for m in modules:
        tasks = m.get_tasks(date_templates)
        all_tasks.extend(tasks)

    log(f"  {len(all_tasks)} tasks ({len(modules)} modules x 2 languages), running in parallel...")
    t0 = time.time()
    raw_results = run_parallel(all_tasks)
    t1 = time.time()
    log(f"[step 3/7] collection done ({t1 - t0:.1f}s)")

    # ---- Merge Chinese and English results ----
    log("[step 4/7] Merging Chinese/English results...")
    module_results = []
    for module in modules:
        tasks = module.get_tasks(date_templates)
        zh_name = f"{module.name}_zh"
        en_name = f"{module.name}_en"
        zh_raw = ""
        en_raw = ""
        for j, task in enumerate(tasks):
            if task["name"] == zh_name:
                zh_raw = raw_results[all_tasks.index(task)]
            elif task["name"] == en_name:
                en_raw = raw_results[all_tasks.index(task)]
        combined = module.combine_results(zh_raw, en_raw)
        parsed = module.parse_result(combined)
        module_results.append(parsed)
        zh_len = len(zh_raw)
        en_len = len(en_raw)
        log(f"  {module.name}: zh={zh_len}c + en={en_len}c = {len(combined)}c")
    log("[step 4/7] merge done")

    # ---- Importance filtering ----
    filters = discover_filters()
    if filters:
        log(f"[step 5/7] Importance filtering ({len(filters)} filter(s))...")
        t_filter_start = time.time()
        for f in filters:
            log(f"  {f.name} filtering per module...")
            for i, mr in enumerate(module_results):
                before_len = len(mr.content)
                module_results[i] = f.filter(mr)
                after_len = len(module_results[i].content)
                log(f"    {mr.name}: {before_len}c -> {after_len}c")
        log(f"[step 5/7] filter done ({time.time()-t_filter_start:.1f}s)")
    else:
        log("[step 5/7] no filters, skipping")

    # ---- Analysis ----
    log("[step 6/7] Deep cross-domain analysis...")
    analysis_report = ""
    for analyzer in analyzers:
        log(f"  {analyzer.name} starting (model={analyzer.model})...")
        t2 = time.time()
        analysis_report = analyzer.analyze(module_results)
        t3 = time.time()
        log(f"  {analyzer.name} done ({t3 - t2:.1f}s, {len(analysis_report)}c)")
    log("[step 6/7] analysis done")

    # ---- Assemble final report (Chinese) ----
    log("[step 7/7] Assembling report...")
    lines = [f"# Wanshi Tong Daily Briefing . {date_str}", ""]
    for mr in module_results:
        lines.append("---")
        lines.append(f"## {mr.title}")
        lines.append("")
        lines.append(f"[{mr.error}]" if mr.error else mr.content.strip())
        lines.append("")
    if analysis_report:
        lines.append("---")
        lines.append("## Deep Cross-Domain Analysis")
        lines.append("")
        lines.append(analysis_report.strip())
    lines.append("")
    lines.append("---")
    lines.append(f"Report generated: {time_str}")
    report_text = "\n".join(lines)

    # ---- Date cleanup ----
    report_text = cleanup_dates(report_text)
    log(f"  report length: {len(report_text)}c")

    # ---- Save ----
    report_file = f"wanshi_tong_{datetime.now().strftime('%Y%m%d_%H%M')}.md"
    with open(report_file, "w", encoding="utf-8") as fh:
        fh.write(report_text)
    log(f"  saved: {report_file}")

    # ---- Send ----
    for reporter in reporters:
        log(f"  {reporter.name} sending...")
        try:
            reporter.send("Wanshi Tong Daily", report_text)
            log(f"  {reporter.name} sent")
        except Exception as e:
            log(f"  {reporter.name} failed: {e}")

    log("=" * 60)
    log("Wanshi Tong Daily Briefing -- done")
    log("=" * 60)


if __name__ == "__main__":
    main()
