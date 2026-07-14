from dataclasses import dataclass
from datetime import date, datetime, timedelta


@dataclass(frozen=True)
class RunContext:
    generated_at: datetime

    @classmethod
    def current(cls) -> "RunContext":
        return cls(datetime.now())

    @property
    def today(self) -> date:
        return self.generated_at.date()

    @property
    def yesterday(self) -> date:
        return self.today - timedelta(days=1)

    @property
    def allowed_dates(self) -> tuple[date, date]:
        return self.yesterday, self.today

    @property
    def date_templates(self) -> dict[str, str]:
        yesterday = self.yesterday
        today = self.today
        return {
            "yesterday_cn": _chinese_date(yesterday),
            "today_cn": _chinese_date(today),
            "yesterday_en": _english_date(yesterday),
            "today_en": _english_date(today),
            "yesterday_short_cn": f"{yesterday.month}月{yesterday.day}日",
            "today_short_cn": f"{today.month}月{today.day}日",
            "yesterday_day": str(yesterday.day),
            "today_day": str(today.day),
            "month_en": today.strftime("%B"),
            "year": str(today.year),
        }

    @property
    def report_filename(self) -> str:
        return f"wanshi_tong_{self.generated_at:%Y%m%d_%H%M}.md"


def _chinese_date(value: date) -> str:
    return f"{value.year}年{value.month}月{value.day}日"


def _english_date(value: date) -> str:
    return f"{value.strftime('%B')} {value.day}, {value.year}"
