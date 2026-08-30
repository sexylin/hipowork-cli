"""hipo_accounts 多账户管理单元测试（使用临时 token 仓库，不碰真实 ~/.hipo_mcp_tokens.json）。

运行：
  cd hipowork-cli
  python3.13 -m unittest tests/test_hipo_accounts.py -v
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src" / "hipowork_cli" / "scripts"))

from hipo_auth import TokenStore  # noqa: E402


def _make_token(role: str = "candidate", email: str = "a@b.com") -> dict:
    return {
        "role": role,
        "email": email,
        "tokens": {
            "access_token": "at_" + email,
            "refresh_token": "rt_" + email,
            "scope": "profile candidate:read",
        },
        "client_info": {"client_id": "client-" + email},
    }


class TestTokenStoreMultiAccount(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.path = str(Path(self._tmpdir.name) / "tokens.json")

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_empty_store(self):
        s = TokenStore(self.path)
        self.assertFalse(s.exists())
        self.assertEqual(s.accounts(), {})
        # 空仓库时 default_account 返回空字符串（无账户，不指向任何 account_id）
        self.assertEqual(s.default_account(), "")
        self.assertIsNone(s.get_account())

    def test_set_account_and_default(self):
        s = TokenStore(self.path)
        acc = _make_token(email="x@test.com")
        s.set_account("x@test.com", acc, make_default=True)
        self.assertTrue(s.exists())
        self.assertEqual(s.default_account(), "x@test.com")
        self.assertEqual(s.role(), "candidate")
        self.assertEqual(s.email(), "x@test.com")

    def test_multiple_accounts_isolated(self):
        s = TokenStore(self.path)
        s.set_account("cand@test.com", _make_token(role="candidate", email="cand@test.com"), make_default=True)
        s.set_account("emp@test.com", _make_token(role="employer", email="emp@test.com"))
        self.assertEqual(len(s.accounts()), 2)
        # 默认账户是第一个；查指定账户角色互不影响
        self.assertEqual(s.role("cand@test.com"), "candidate")
        self.assertEqual(s.role("emp@test.com"), "employer")

    def test_switch_default(self):
        s = TokenStore(self.path)
        s.set_account("a@t.com", _make_token(email="a@t.com"), make_default=True)
        s.set_account("b@t.com", _make_token(email="b@t.com"))
        s.set_account("b@t.com", s.accounts()["b@t.com"], make_default=True)
        self.assertEqual(s.default_account(), "b@t.com")

    def test_delete_account_and_fallback_default(self):
        s = TokenStore(self.path)
        s.set_account("a@t.com", _make_token(email="a@t.com"), make_default=True)
        s.set_account("b@t.com", _make_token(email="b@t.com"))
        # 用 accounts 命令同款逻辑删除默认账户
        del s._data["accounts"]["a@t.com"]
        s._data["default_account"] = list(s.accounts().keys())[0] if s.accounts() else ""
        s._save()
        self.assertEqual(s.default_account(), "b@t.com")

    def test_legacy_flat_migration(self):
        """旧版平铺结构 {client_info, tokens} 读取时自动迁移为多账户。"""
        legacy = {
            "email": "old@t.com",
            "role": "employer",
            "tokens": {"access_token": "at_old", "refresh_token": "rt_old"},
            "client_info": {"client_id": "client-old"},
        }
        Path(self.path).write_text(json.dumps(legacy), encoding="utf-8")
        s = TokenStore(self.path)
        self.assertTrue(s.exists())
        self.assertEqual(s.default_account(), "old@t.com")
        self.assertEqual(s.role(), "employer")
        self.assertEqual(s.email(), "old@t.com")
        self.assertEqual(s.tokens().get("access_token"), "at_old")
        # 迁移后文件应改写为多账户结构
        data = json.loads(Path(self.path).read_text(encoding="utf-8"))
        self.assertIn("accounts", data)
        self.assertEqual(data["default_account"], "old@t.com")

    def test_tokens_roundtrip(self):
        s = TokenStore(self.path)
        acc = _make_token(email="rt@t.com")
        s.set_account("rt@t.com", acc, make_default=True)
        s2 = TokenStore(self.path)  # 重新读取
        self.assertEqual(s2.tokens().get("access_token"), "at_rt@t.com")
        self.assertEqual(s2.tokens().get("refresh_token"), "rt_rt@t.com")


if __name__ == "__main__":
    unittest.main()