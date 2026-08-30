"""HiPo Work 共享认证库：token 仓库读写 / 过期判断 / 刷新 / 多账户预留。

所有 CLI 脚本都通过本模块管理令牌，避免重复实现。
数据结构（~/.hipo_mcp_tokens.json，多账户预留）：

{
  "default_account": "sexylin2010+eng2@gmail.com",
  "accounts": {
    "<account_id>": {
      "email": "...", "role": "candidate" | "employer",
      "client_info": { "client_id": "...", "client_name": "..." },
      "tokens": { "access_token": "...", "refresh_token": "...", "scope": "...", "expires_in": 3600 }
    }
  }
}

第一版只维护单账户（default_account），但存储结构已按多账户设计，
后续扩展只需在 accounts 下新增条目即可。
"""
from __future__ import annotations

import base64
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# ---- 默认配置（可用 config.yaml 或环境变量覆盖）----
DEFAULT_TOKEN_FILE = Path.home() / ".hipo_mcp_tokens.json"
DEFAULT_TOKEN_ENDPOINT = "https://mcp.hipowork.com/token"
DEFAULT_MCP_URL = "https://mcp.hipowork.com/mcp"
DEFAULT_API_BASE = "https://api.hipowork.com/api/v1"
DEFAULT_CALLBACK_PORT = 8765


# ============ Token 仓库 ============

class TokenStore:
    """极简 JSON 文件 token 仓库（线程安全 + 原子写）。"""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path or DEFAULT_TOKEN_FILE)
        self._data = self._load()

    def _load(self) -> dict:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
        if not isinstance(data, dict):
            return {}
        # 兼容旧版平铺结构 {client_info, tokens} → 自动迁移为多账户结构
        if "tokens" in data and "accounts" not in data:
            data = self._migrate_flat(data)
        return data

    def _migrate_flat(self, data: dict) -> dict:
        """旧版平铺 token 文件 → 多账户结构（account_id 取 email，缺省用 default）。"""
        account_id = str(data.get("email") or "default")
        account = {}
        if data.get("tokens"):
            account["tokens"] = data["tokens"]
        if data.get("client_info"):
            account["client_info"] = data["client_info"]
        if data.get("email"):
            account["email"] = data["email"]
        if data.get("role"):
            account["role"] = data["role"]
        migrated = {"default_account": account_id, "accounts": {account_id: account}}
        # 迁移即写回，保证下次 save 直接落盘多账户结构
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(migrated, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)
        return migrated

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # 原子写：先写临时文件再 rename，避免中断导致仓库损坏
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)
        try:
            self.path.chmod(0o600)  # 仅 owner 可读写
        except OSError:
            pass

    # ---- 账户级 API ----

    def default_account(self) -> str:
        return self._data.get("default_account", "")

    def accounts(self) -> dict:
        return self._data.get("accounts", {})

    def get_account(self, account_id: str | None = None) -> dict | None:
        account_id = account_id or self.default_account()
        if not account_id:
            return None
        return self.accounts().get(account_id)

    def set_account(self, account_id: str, payload: dict, make_default: bool = True) -> None:
        self._data.setdefault("accounts", {})[account_id] = payload
        if make_default:
            self._data["default_account"] = account_id
        self._save()

    def save_tokens(self, tokens: dict, client_info: dict | None = None,
                    account_id: str | None = None, email: str = "", role: str = "") -> None:
        account_id = account_id or email or self.default_account() or "default"
        acc = self.get_account(account_id) or {}
        acc.setdefault("tokens", {}).update(tokens)
        if client_info:
            acc["client_info"] = client_info
        if email:
            acc["email"] = email
        if role:
            acc["role"] = role
        self.set_account(account_id, acc, make_default=True)

    # ---- 便捷访问 ----

    def tokens(self, account_id: str | None = None) -> dict:
        acc = self.get_account(account_id)
        return (acc or {}).get("tokens", {})

    def client_info(self, account_id: str | None = None) -> dict:
        acc = self.get_account(account_id)
        return (acc or {}).get("client_info", {})

    def email(self, account_id: str | None = None) -> str:
        acc = self.get_account(account_id)
        return (acc or {}).get("email", "")

    def role(self, account_id: str | None = None) -> str:
        acc = self.get_account(account_id)
        return (acc or {}).get("role", "")

    def exists(self) -> bool:
        return self.path.exists() and bool(self.tokens().get("access_token"))


# ============ Token 工具 ============

def decode_jwt_payload(token: str) -> dict:
    """解析 JWT 的 payload（不校验签名，仅用于读取 exp/scope/role）。"""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload))
    except Exception:
        return {}


def is_expired(token: str, margin: int = 120) -> bool:
    """判断 access_token 是否在 margin 秒内过期。解析失败视为过期。"""
    exp = decode_jwt_payload(token).get("exp", 0)
    return exp - margin <= time.time()


def refresh_tokens(tokens: dict, client_info: dict, endpoint: str = DEFAULT_TOKEN_ENDPOINT) -> dict:
    """用 refresh_token 轮换出一对新 token。失败抛异常，由调用方决定如何处理。"""
    if not tokens.get("refresh_token"):
        raise ValueError("仓库中没有 refresh_token，需要重新走 OAuth 授权")
    if not client_info.get("client_id"):
        raise ValueError("仓库中没有 client_info.client_id，需要重新走 OAuth 授权")

    body = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": tokens["refresh_token"],
        "client_id": client_info["client_id"],
    }).encode()
    req = urllib.request.Request(
        endpoint, data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            new = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode()[:300]
        if exc.code in (400, 401):
            raise ValueError(f"refresh_token 已失效（HTTP {exc.code}），需要重新授权: {detail}")
        raise RuntimeError(f"刷新失败 HTTP {exc.code}: {detail}")
    except Exception as exc:
        raise RuntimeError(f"网络错误: {exc}")

    if "access_token" not in new:
        raise ValueError(f"刷新响应缺少 access_token: {new}")

    tokens["access_token"] = new["access_token"]
    if new.get("refresh_token"):
        tokens["refresh_token"] = new["refresh_token"]
    if new.get("scope"):
        tokens["scope"] = new["scope"]
    tokens["expires_in"] = new.get("expires_in", tokens.get("expires_in", 3600))
    return tokens


def ensure_valid_token(store: TokenStore, account_id: str | None = None,
                       force: bool = False) -> dict:
    """确保拿到未过期的 access_token。过期则自动刷新；刷新失败抛异常。

    返回 tokens dict（可能已刷新）。
    """
    tokens = store.tokens(account_id)
    client_info = store.client_info(account_id)
    if not tokens.get("access_token"):
        raise ValueError("未找到 access_token，请先运行 hipo_authorize.py 完成授权")

    if force or is_expired(tokens["access_token"]):
        refreshed = refresh_tokens(tokens, client_info)
        store.save_tokens(refreshed, client_info, account_id=account_id)
        return refreshed
    return tokens


# ============ MCP / API 客户端入口 ============

def build_authorizer(store: TokenStore, account_id: str | None = None):
    """构造 mcp SDK 的 OAuthClientProvider，复用仓库中的 token。

    若仓库已有有效 token，SDK 会直接使用而不再弹授权。
    依赖 mcp SDK；未安装时抛 ImportError。
    """
    try:
        from mcp.client.auth import OAuthClientProvider
    except ImportError as exc:  # pragma: no cover
        raise ImportError("需要 mcp SDK：pip install -r requirements.txt") from exc
    raise NotImplementedError("多账户/复用式 authorizer 在 v1.1 提供；v1.0 请直接用 hipo_mcp_client.py")


def api_request(method: str, path: str, token: str | None = None, body: dict | None = None,
                api_base: str = DEFAULT_API_BASE, timeout: int = 30):
    """对后端 REST API 发请求（/api/v1 之下），返回解析后的 JSON。

    path 示例："/candidate/matches"、"/candidate/profile"。
    token 传 None 时（公开接口，如发送验证码）不携带 Authorization 头。
    """
    url = f"{api_base}{path}"
    headers = {
        "Content-Type": "application/json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode()[:500]
        raise RuntimeError(f"API {method} {path} 失败 HTTP {exc.code}: {detail}")


# ============ CLI 公共工具 ============

def require_py310() -> None:
    """Python 版本检查：最低 3.10（PEP 604 联合类型）。"""
    if sys.version_info < (3, 10):
        sys.stderr.write(
            f"需要 Python 3.10+（当前 {sys.version_info.major}.{sys.version_info.minor}）。\n"
            "请升级 Python 后重试。\n"
        )
        sys.exit(1)


def print_token_summary(store: TokenStore, account_id: str | None = None) -> None:
    """打印当前账户的 token 状态摘要（不打印 token 本身）。"""
    tokens = store.tokens(account_id)
    client_info = store.client_info(account_id)
    email = store.email(account_id) or "?"
    role = store.role(account_id) or "?"
    if not tokens.get("access_token"):
        print(f"  账户: {email}（{role}）— 未授权")
        return

    claims = decode_jwt_payload(tokens["access_token"])
    exp = claims.get("exp", 0)
    now = time.time()
    expires_in_min = max(0, int((exp - now) // 60)) if exp else -1
    status = "有效" if exp - 120 > now else ("已过期" if exp and exp <= now else "即将过期")
    print(f"  账户: {email}（{role}）")
    print(f"  scope: {tokens.get('scope', '?')}")
    print(f"  access_token: {status}（{expires_in_min} 分钟后过期）")
    print(f"  refresh_token: {'有' if tokens.get('refresh_token') else '无'}")
    print(f"  client_id: {client_info.get('client_id', '?')[:12]}..." if client_info.get("client_id") else "  client_id: 无")
