"""HiPo Work CLI — 面向求职者和招聘方的命令行工具集。

安装后提供 `hipo` 命令（等价于仓库根目录时代的 hipo.py）：

    hipo authorize --role candidate
    hipo match-jobs
    hipo publish-job --json examples/job.example.json

scripts/ 下 16 个子命令模块通过 hipo CLI 统一调度。
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

__version__ = "0.1.0"

SCRIPTS_DIR = Path(__file__).resolve().parent / "scripts"

# 命令名 → 对应脚本文件（不含 .py）
COMMANDS = {
    "authorize": "hipo_authorize",
    "status": "hipo_token_status",
    "refresh": "hipo_token_refresh",
    "token-sync": "hipo_token_sync",
    "accounts": "hipo_accounts",
    "match-jobs": "hipo_match_jobs",
    "publish-job": "hipo_publish_job",
    "close-job": "hipo_close_job",
    "search": "hipo_search_candidates",
    "match-candidates": "hipo_match_candidates",
    "market": "hipo_market",
    "stats": "hipo_stats",
    "resume-extract": "hipo_resume_extract",
    "resume-validate": "hipo_resume_validate",
    "resume-import": "hipo_resume_import",
    "healthcheck": "hipo_healthcheck",
    "e2e": "hipo_e2e",
}

# 各命令的一句话说明（help 输出用）
HELP = {
    "authorize": "OAuth 授权（打开浏览器完成邮箱验证码登录）",
    "status": "查看 token 状态（角色/scope/过期）",
    "refresh": "强制刷新 token",
    "token-sync": "导出 token 到浏览器 localStorage（4 个 base64）",
    "accounts": "多账户管理（list/switch/delete）",
    "match-jobs": "求职者：匹配岗位",
    "publish-job": "招聘方：发布岗位",
    "close-job": "招聘方：关闭已发布的岗位",
    "search": "招聘方：自然语言搜索候选人",
    "match-candidates": "招聘方：结构化/自然语言匹配候选人",
    "market": "招聘方：人才市场分析",
    "stats": "平台统计",
    "resume-extract": "简历文本提取（PDF/DOCX/TXT）",
    "resume-validate": "简历 JSON 结构校验",
    "resume-import": "简历导入（校验 + 写入）",
    "healthcheck": "服务连通性检查（API/MCP/Embedding）",
    "e2e": "端到端冒烟测试",
}

# 需要前置授权的命令（帮助提示用）
AUTH_REQUIRED = {
    "status", "refresh", "token-sync", "accounts", "match-jobs", "publish-job",
    "close-job", "search", "match-candidates", "market", "stats", "resume-import", "e2e",
}


def _print_help() -> None:
    print("HiPo Work CLI — 统一入口")
    print("用法: hipo <command> [args...]\n")
    print("认证与令牌:")
    for k in ("authorize", "status", "refresh", "token-sync", "accounts"):
        print(f"  {k:<16} {HELP[k]}")
    print("\n招聘方:")
    for k in ("publish-job", "close-job", "search", "match-candidates", "market", "stats"):
        print(f"  {k:<16} {HELP[k]}")
    print("\n求职者:")
    for k in ("match-jobs", "resume-extract", "resume-validate", "resume-import"):
        print(f"  {k:<16} {HELP[k]}")
    print("\n运维:")
    for k in ("healthcheck", "e2e"):
        print(f"  {k:<16} {HELP[k]}")
    print("\n任何命令都可用 --help 查看详细参数，例如:")
    print("  hipo publish-job --help")
    print("\n也可以直接运行 src/hipowork_cli/scripts/ 下的独立脚本（等价）。")


def main() -> int:
    # 允许从任意目录运行：把 scripts/ 加进 PYTHONPATH
    env = dict(os.environ)
    pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(SCRIPTS_DIR) + (os.pathsep + pythonpath if pythonpath else "")

    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help", "help"):
        _print_help()
        return 0

    cmd = args[0]
    if cmd not in COMMANDS:
        print(f"❌ 未知命令: {cmd}\n", file=sys.stderr)
        _print_help()
        return 2

    script = SCRIPTS_DIR / f"{COMMANDS[cmd]}.py"
    if not script.exists():
        print(f"❌ 脚本缺失: {script}", file=sys.stderr)
        return 2

    # 转发剩余参数；子进程继承 PYTHONPATH，保证 scripts 内部互相 import 正常
    return subprocess.call([sys.executable, str(script), *args[1:]], env=env)


if __name__ == "__main__":
    sys.exit(main())