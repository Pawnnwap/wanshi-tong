import json
import hashlib
import base64
import hmac
import time
import re
import requests
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
    return resp.json()


def cleanup_dates(content: str) -> str:
    """Remove lines containing dates outside the allowed range."""
    lines = content.split("\n")
    return "\n".join(
        line for line in lines
        if not any(int(d) not in (5, 6) for d in re.findall(r'6月(\d+)日', line))
    )


class FeishuReporter(Reporter):
    name = "feishu"

    def send(self, title: str, content: str) -> None:
        creds = _load_credentials()
        cfg = load_config().get("feishu", {})
        webhook_url = creds.get("feishu_webhook", "")
        secret = creds.get("feishu_secret", "")
        max_chars = cfg.get("max_chars_per_msg", 1200)

        if not webhook_url:
            raise ValueError("feishu_webhook not found in credentials.json")

        parts = self._split(content, max_chars)

        for i, part in enumerate(parts):
            part_title = f"{title} ({i+1}/{len(parts)})" if len(parts) > 1 else title
            _send_card(webhook_url, secret, part_title, part)
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
