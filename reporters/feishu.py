import json
import hashlib
import base64
import hmac
import time
import re
import requests
from datetime import date, datetime, timedelta
from pathlib import Path
from core.base import Reporter
from core.config import load_config

CREDENTIALS_FILE = Path(__file__).resolve().parent.parent / "credentials.json"




def _load_credentials():
    with open(CREDENTIALS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _gen_sign(timestamp: int, secret: str) -> str:
    string_to_sign = f"{timestamp}\n{secret}"
    h = hmac.new(
        secret.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    )
    return base64.b64encode(h.digest()).decode("utf-8")


def _send_card(webhook_url: str, secret: str, title: str, markdown: str) -> dict:
    timestamp = int(time.time())
    card = {
        "header": {
            "title": {"tag": "plain_text", "content": title},
            "template": "blue",
        },
        "elements": [
            {"tag": "markdown", "content": markdown}
        ],
    }
    payload = {
        "timestamp": str(timestamp),
        "msg_type": "interactive",
        "card": card,
    }
    if secret:
        payload["sign"] = _gen_sign(timestamp, secret)
    resp = requests.post(webhook_url, json=payload, timeout=30)
    resp.raise_for_status()
    result = resp.json()
    result_code = result.get("code", result.get("StatusCode", 0))
    if result_code != 0:
        message = result.get("msg", result.get("StatusMessage", "unknown error"))
        raise RuntimeError(f"Feishu webhook rejected message: {result_code} {message}")
    return result


def _send_card_with_retry(
    webhook_url: str,
    secret: str,
    title: str,
    markdown: str,
    max_attempts: int,
    retry_delay_s: float,
) -> dict:
    for attempt in range(1, max_attempts + 1):
        try:
            return _send_card(webhook_url, secret, title, markdown)
        except Exception:
            if attempt == max_attempts:
                raise
            time.sleep(retry_delay_s * (2 ** (attempt - 1)))
    raise RuntimeError("unreachable")


_CHINESE_DATE_RE = re.compile(r"(?:(\d{4})年)?(\d{1,2})月(\d{1,2})日")
_ISO_DATE_RE = re.compile(r"(?<!\d)(\d{4})-(\d{1,2})-(\d{1,2})(?!\d)")


def cleanup_dates(content: str, allowed_dates=None) -> str:
    """Remove lines with explicit dates outside the collection window."""
    if allowed_dates is None:
        today = date.today()
        allowed = {today - timedelta(days=1), today}
    else:
        allowed = {
            value.date() if isinstance(value, datetime) else value
            for value in allowed_dates
        }

    allowed_month_days = {(value.month, value.day) for value in allowed}

    def has_disallowed_date(line: str) -> bool:
        for year, month, day in _CHINESE_DATE_RE.findall(line):
            if year:
                try:
                    value = date(int(year), int(month), int(day))
                except ValueError:
                    continue
                if value not in allowed:
                    return True
            elif (int(month), int(day)) not in allowed_month_days:
                return True

        for year, month, day in _ISO_DATE_RE.findall(line):
            try:
                value = date(int(year), int(month), int(day))
            except ValueError:
                continue
            if value not in allowed:
                return True
        return False

    cleaned = "\n".join(
        line for line in content.splitlines()
        if not has_disallowed_date(line)
    )
    return re.sub(r"\n{3,}", "\n\n", cleaned)


class FeishuReporter(Reporter):
    name = "feishu"

    def send(self, title: str, content: str) -> None:
        creds = _load_credentials()
        cfg = load_config().get("feishu", {})
        webhook_url = creds.get("feishu_webhook", "")
        secret = creds.get("feishu_secret", "")
        max_chars = cfg.get("max_chars_per_msg", 1200)
        max_attempts = cfg.get("max_attempts", 3)
        retry_delay_s = cfg.get("retry_delay_s", 2)

        if not webhook_url:
            raise ValueError("feishu_webhook not found in credentials.json")
        if max_attempts < 1:
            raise ValueError("feishu.max_attempts must be at least 1")

        parts = self._split(content, max_chars)

        for i, part in enumerate(parts):
            part_title = f"{title} ({i+1}/{len(parts)})" if len(parts) > 1 else title
            _send_card_with_retry(
                webhook_url,
                secret,
                part_title,
                part,
                max_attempts,
                retry_delay_s,
            )
            if i < len(parts) - 1:
                time.sleep(1)
        return

    @staticmethod
    def _split(text: str, max_chars: int) -> list[str]:
        parts = []
        remaining = text
        while len(remaining) > max_chars:
            break_at = remaining.rfind("\n## ", 0, max_chars)
            if break_at > max_chars // 2:
                parts.append(remaining[:break_at])
                remaining = remaining[break_at:]
                continue
            break_at = remaining.rfind("\n\n", 0, max_chars)
            if break_at > max_chars // 2:
                parts.append(remaining[:break_at])
                remaining = remaining[break_at:]
                continue
            break_at = remaining.rfind("\n", 0, max_chars)
            if break_at > 0:
                parts.append(remaining[:break_at])
                remaining = remaining[break_at:]
                continue
            parts.append(remaining[:max_chars])
            remaining = remaining[max_chars:]
        if remaining.strip():
            parts.append(remaining)
        return parts
