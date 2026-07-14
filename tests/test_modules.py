import unittest
from datetime import datetime

from core.context import RunContext
from modules.macro_data import MacroDataModule
from modules.political_news import PoliticalNewsModule
from modules.social_news import SocialNewsModule
from modules.tech_news import TechNewsModule


class ModuleTaskTest(unittest.TestCase):
    def setUp(self):
        self.templates = RunContext(datetime(2026, 7, 14)).date_templates

    def test_news_modules_share_policy_but_keep_domain_coverage(self):
        modules = [PoliticalNewsModule(), SocialNewsModule(), TechNewsModule()]

        for module in modules:
            zh_task, en_task = module.get_tasks(self.templates)
            self.assertIn("2026年7月13日或2026年7月14日", zh_task.prompt)
            self.assertIn("更早、未来或日期不明的直接丢弃", zh_task.prompt)
            self.assertIn("July 13, 2026 or July 14, 2026", en_task.prompt)
            self.assertIn("discard older, future, or undated items", en_task.prompt)

        self.assertIn("领导讲话", modules[0].get_tasks(self.templates)[0].prompt)
        self.assertIn("教育医疗", modules[1].get_tasks(self.templates)[0].prompt)
        self.assertIn("AI/大模型", modules[2].get_tasks(self.templates)[0].prompt)

    def test_macro_task_policy_is_declarative(self):
        tasks = MacroDataModule().get_tasks(self.templates)

        self.assertEqual([task.idle_timeout_s for task in tasks], [600, 600])
        self.assertEqual([task.max_attempts for task in tasks], [1, 1])


if __name__ == "__main__":
    unittest.main()
