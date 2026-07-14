import base64
import hashlib
import hmac
import json
import time

import requests
from pathlib import Path

from core.base import Reporter
from core.config import load_config
from core.progress import sleep_with_progress
from core.report import cleanup_dates

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


def _build_payload(timestamp: int, secret: str, title: str, markdown: str) -> dict:
    payload = {
        "timestamp": str(timestamp),
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": title},
                "template": "blue",
            },
            "elements": [{"tag": "markdown", "content": markdown}],
        },
    }
    if secret:
        payload["sign"] = _gen_sign(timestamp, secret)
    return payload


def _send_card(
    webhook_url: str,
    secret: str,
    title: str,
    markdown: str,
    network_idle_timeout_s: int = 30,
) -> dict:
    timestamp = int(time.time())
    payload = _build_payload(timestamp, secret, title, markdown)
    resp = requests.post(
        webhook_url,
        json=payload,
        timeout=(network_idle_timeout_s, network_idle_timeout_s),
    )
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
            sleep_with_progress(retry_delay_s * (2 ** (attempt - 1)), f"feishu retry {attempt + 1}/{max_attempts}")
    raise RuntimeError("unreachable")


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
        if max_chars < 1:
            raise ValueError("feishu.max_chars_per_msg must be at least 1")

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
                sleep_with_progress(1, f"feishu next message {i + 2}/{len(parts)}")
    @staticmethod
    def _split(text: str, max_chars: int) -> list[str]:
        parts = []
        remaining = text
        while len(remaining) > max_chars:
            break_at = _find_breakpoint(remaining, max_chars)
            if break_at > 0:
                parts.append(remaining[:break_at])
                remaining = remaining[break_at:]
                continue
            parts.append(remaining[:max_chars])
            remaining = remaining[max_chars:]
        if remaining.strip():
            parts.append(remaining)
        return parts


def _find_breakpoint(text: str, max_chars: int) -> int:
    for separator, minimum in (("\n## ", max_chars // 2), ("\n\n", max_chars // 2), ("\n", 0)):
        breakpoint = text.rfind(separator, 0, max_chars)
        if breakpoint > minimum:
            return breakpoint
    return -1
