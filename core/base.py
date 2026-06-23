from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class ModuleResult:
    name: str
    title: str
    content: str
    model: str = ""
    error: Optional[str] = None


class Module(ABC):
    """搜索模块抽象基类。新增模块只需继承此类并设置类属性。"""
    name: str = ""
    title: str = ""
    model: str = ""
    prompt_zh: str = ""
    prompt_en: str = ""

    def get_tasks(self, date_templates: dict | None = None) -> list[dict]:
        """返回中英双语两个任务，支持日期模板注入。"""
        prompt_zh = self.prompt_zh
        prompt_en = self.prompt_en
        if date_templates:
            prompt_zh = prompt_zh.format(**date_templates)
            prompt_en = prompt_en.format(**date_templates)
        return [
            {"name": f"{self.name}_zh", "prompt": prompt_zh, "model": self.model},
            {"name": f"{self.name}_en", "prompt": prompt_en, "model": self.model},
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
