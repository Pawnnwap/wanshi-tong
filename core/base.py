from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Mapping, Optional


@dataclass(frozen=True)
class Task:
    name: str
    prompt: str
    model: str = ""
    idle_timeout_s: float = 0
    max_attempts: int = 0

    @classmethod
    def from_value(cls, value: "Task | Mapping") -> "Task":
        if isinstance(value, cls):
            return value
        return cls(
            name=value.get("name", ""),
            prompt=value["prompt"],
            model=value.get("model", ""),
            idle_timeout_s=value.get("idle_timeout_s", value.get("timeout_s", 0)),
            max_attempts=value.get("max_attempts", 0),
        )


@dataclass
class ModuleResult:
    name: str
    title: str
    content: str
    model: str = ""
    error: Optional[str] = None
    # Deterministic data that must not be reprocessed/rescored by LLM filters.
    authoritative: bool = False


class Module(ABC):
    """搜索模块抽象基类。新增模块只需继承此类并设置类属性。"""
    name: str = ""
    title: str = ""
    model: str = ""
    prompt_zh: str = ""
    prompt_en: str = ""
    task_idle_timeout_s: float = 0
    task_max_attempts: int = 0

    def get_prompt_templates(self) -> Mapping[str, str]:
        return {"zh": self.prompt_zh, "en": self.prompt_en}

    def get_tasks(self, date_templates: Mapping[str, str] | None = None) -> list[Task]:
        """返回中英双语两个任务，支持日期模板注入。"""
        prompts = self.get_prompt_templates()
        if date_templates:
            prompts = {
                language: prompt.format(**date_templates)
                for language, prompt in prompts.items()
            }
        return [
            Task(
                name=f"{self.name}_{language}",
                prompt=prompt,
                model=self.model,
                idle_timeout_s=self.task_idle_timeout_s,
                max_attempts=self.task_max_attempts,
            )
            for language, prompt in prompts.items()
        ]

    def combine_results(self, zh_result: str, en_result: str) -> str:
        """合并中英文搜索结果，子类可覆盖以自定义合并逻辑。"""
        return f"=== 中文搜索结果 ===\n{zh_result}\n\n=== English Search Results ===\n{en_result}"

    def parse_result(self, raw: str) -> ModuleResult:
        return ModuleResult(
            name=self.name,
            title=self.title,
            content=raw,
            model=self.model,
        )


class LocalModule(Module):
    """Non-agentic module that computes its own content in Python.

    Unlike a normal Module, it emits no opencode tasks; the pipeline calls
    ``collect`` directly. Use this for deterministic data (e.g. market prices)
    that should be fetched from an API rather than an LLM + search tools.
    """

    # When True, the report's date-cleanup pass keeps this section verbatim,
    # so authoritative rows are never dropped for carrying a non-today date
    # (e.g. a last-trading-day close over a weekend or holiday).
    preserve_dates: bool = True

    def get_tasks(self, date_templates: Mapping[str, str] | None = None) -> list[Task]:
        return []

    def collect(self, date_templates: Mapping[str, str] | None = None) -> ModuleResult:
        """Fetch data and return the finished result. Must not raise."""
        raise NotImplementedError


class Filter(ABC):
    """重要性过滤器抽象基类。"""
    name: str = ""
    model: str = ""

    @abstractmethod
    def filter(self, module_result: ModuleResult) -> ModuleResult:
        """过滤单个模块结果，返回过滤后的结果。"""
        ...


class Analyzer(ABC):
    """深度分析器抽象基类。"""
    name: str = ""
    model: str = ""

    @abstractmethod
    def analyze(self, module_results: list[ModuleResult]) -> str:
        ...


class Reporter(ABC):
    """报告发送器抽象基类。"""
    name: str = ""

    @abstractmethod
    def send(self, title: str, content: str) -> bool:
        ...
