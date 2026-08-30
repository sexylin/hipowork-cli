"""hipo_resume_import 单元测试。

运行：
  cd hipowork-cli
  python3.13 -m unittest tests/test_hipo_resume_import.py -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src" / "hipowork_cli" / "scripts"))

from hipo_resume_import import _guard_empty, _is_empty_resume, _load  # noqa: E402
from hipo_mcp_client import HipiError  # noqa: E402


class TestIsEmptyResume(unittest.TestCase):
    def test_empty_dict_is_empty(self):
        self.assertTrue(_is_empty_resume({}))

    def test_only_empty_basic_is_empty(self):
        self.assertTrue(_is_empty_resume({"basic_info": {}}))

    def test_null_lists_are_empty(self):
        self.assertTrue(_is_empty_resume({
            "basic_info": {},
            "work_experiences": [],
            "skills": None,
        }))

    def test_basic_name_makes_not_empty(self):
        self.assertFalse(_is_empty_resume({"basic_info": {"name": "张三"}}))

    def test_any_skill_makes_not_empty(self):
        self.assertFalse(_is_empty_resume({"skills": [{"name": "Python"}]}))

    def test_any_work_makes_not_empty(self):
        self.assertFalse(_is_empty_resume({
            "work_experiences": [{"company": "某公司"}],
        }))

    def test_any_education_makes_not_empty(self):
        self.assertFalse(_is_empty_resume({
            "education": [{"school": "某大学"}],
        }))


class TestGuardEmpty(unittest.TestCase):
    def test_empty_raises(self):
        with self.assertRaises(HipiError):
            _guard_empty({})

    def test_non_empty_passes(self):
        _guard_empty({"basic_info": {"name": "张三"}})  # 不应抛异常


class TestLoad(unittest.TestCase):
    def test_missing_file_raises(self):
        with self.assertRaises(HipiError):
            _load("/nonexistent/resume.json")

    def test_load_returns_text(self):
        p = Path(__file__).resolve().parent / "fixtures" / "sample_resume.txt"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("张三 区块链全栈工程师\nPython Solidity FastAPI\n", encoding="utf-8")
        try:
            text = _load(str(p))
            self.assertIn("张三", text)
        finally:
            p.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()