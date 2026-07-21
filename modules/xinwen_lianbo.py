"""新闻联播 scraper — deterministic HTML parsing from cn.govopendata.com.

Each news item is in an <article class="content-section"> containing an <h2>
headline and one or more <p> paragraphs. BeautifulSoup extracts these cleanly.
No LLM required. Authoritative=True so the importance filter skips it.
"""

from __future__ import annotations

import re
from typing import Mapping

import requests
from bs4 import BeautifulSoup

from core.base import LocalModule, ModuleResult

_URL = "https://cn.govopendata.com/xinwenlianbo/{date_digits}/"
_HTTP_TIMEOUT = 15

_CLEAN = re.compile(r"\s+")
_SORRY = "对不起，可能是网络原因或无此页面，请稍后尝试。"


def _clean(s: str) -> str:
    return _CLEAN.sub(" ", s.replace("\xa0", " ")).strip()


class XinwenLianboModule(LocalModule):
    name = "xinwen_lianbo"
    title = "【新闻联播要闻】"
    preserve_dates = True

    def run(self, date_templates: Mapping[str, str] | None = None) -> ModuleResult:
        if date_templates is None:
            return ModuleResult(self.name, self.title, "", authoritative=True)

        yesterday_digits = date_templates.get("yesterday_digits", "")
        yesterday_cn = date_templates.get("yesterday_cn", "")
        if not yesterday_digits:
            return ModuleResult(self.name, self.title, "日期参数缺失", authoritative=True)

        url = _URL.format(date_digits=yesterday_digits)

        try:
            resp = requests.get(url, timeout=_HTTP_TIMEOUT, headers={
                "User-Agent": "Mozilla/5.0 (compatible; wanshi-tong/1.0)",
            })
        except Exception:
            return ModuleResult(self.name, self.title, "新闻联播获取失败（网络错误）", authoritative=True)

        if resp.status_code != 200:
            return ModuleResult(self.name, self.title, "新闻联播页面不可用", authoritative=True)

        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup.find_all(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        items = []
        for article in soup.find_all("article", class_="content-section"):
            headline_tag = article.find(["h2", "h3"])
            if not headline_tag:
                continue
            headline = _clean(headline_tag.get_text())
            if not headline or _SORRY in headline or len(headline) > 120:
                continue

            paragraphs = article.find_all("p")
            body = " ".join(
                _clean(p.get_text())
                for p in paragraphs[:3]  # first 3 paragraphs max
                if _clean(p.get_text())
            )[:300]

            if not body:
                continue

            items.append((headline, body))

        if not items:
            return ModuleResult(self.name, self.title, "未提取到新闻条目", authoritative=True)

        lines = []
        for i, (headline, body) in enumerate(items, 1):
            lines.append(f"{i}. **{headline}**")
            lines.append(f"   {body}")
            lines.append("")

        header = (
            "日期覆盖可核验（精确至日）；URL根如未提供请默认 cn.govopendata.com；"
            "禁止编造发布日期。"
        )
        content = (
            f"{header}\n\n"
            f"{yesterday_cn} 新闻联播（共{len(items)}条）\n\n"
            f"{''.join(lines)}"
        )
        return ModuleResult(self.name, self.title, content, authoritative=True)
