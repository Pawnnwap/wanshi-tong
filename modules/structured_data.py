from typing import Mapping

from core.base import Module


class StructuredDataModule(Module):
    request_zh = ""
    request_en = ""
    rules_zh: tuple[str, ...] = ()
    rules_en: tuple[str, ...] = ()
    output_zh = ""
    output_en = ""

    def get_prompt_templates(self) -> Mapping[str, str]:
        return {
            "zh": self._build_prompt(
                self.request_zh,
                "要求：",
                self.rules_zh,
                self.output_zh,
                "当前日期：{today_cn}",
            ),
            "en": self._build_prompt(
                self.request_en,
                "Rules:",
                self.rules_en,
                self.output_en,
                "Current date: {today_en}",
            ),
        }

    @staticmethod
    def _build_prompt(
        request: str,
        heading: str,
        rules: tuple[str, ...],
        output: str,
        current_date: str,
    ) -> str:
        rule_lines = "\n".join(f"- {rule}" for rule in rules)
        return f"{request}\n\n{heading}\n{rule_lines}\n\n{output}\n{current_date}"
