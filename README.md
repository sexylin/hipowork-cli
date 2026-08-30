# hipowork-cli

HiPo Work 客户端命令行工具集 — 面向求职者和招聘方的纯 Python 脚本集，
直接对接 https://api.hipowork.com 后端 REST API（底层与 MCP 工具同一套接口），
无需浏览器、无需配置 API Key，用 OAuth 授权后即可在终端完成简历导入、岗位发布、
候选人匹配、市场分析等操作。

## 安装

```bash
# 从 PyPI 安装（Python 3.10+）
pip install hipowork-cli

# 可选：简历 PDF 提取依赖
pip install hipowork-cli[resume]
```

安装后提供 `hipo` 命令，可从任意目录运行。

## 快速开始

```bash
# 1. 授权（浏览器完成邮箱验证码登录）
hipo authorize --role candidate     # 求职者授权
# hipo authorize --role employer    # 招聘方授权

# 2. 看授权状态 / 刷新 / 多账户
hipo status
hipo refresh
hipo accounts list

# 3. 用起来
hipo match-jobs                                       # 求职者匹配岗位
hipo resume-import --json my_resume.json              # 导入简历
hipo publish-job --json examples/job.example.json     # 招聘方发布岗位
hipo search "成都 Python 后端"
```

> 提示：授权流程需要浏览器完成邮箱验证码登录；授权完成后 token 自动刷新，
> 无需再手动处理。token 只存在本机 `~/.hipo_mcp_tokens.json`（0600 权限）。

### 开发模式（从源码运行）

```bash
git clone git@github.com:sexylin/hipowork-cli.git
cd hipowork-cli
python3.13 -m venv .venv
.venv/bin/pip install -e .            # 可编辑安装，命令即 hipo
.venv/bin/python -m unittest discover -s tests   # 运行测试
```

## 命令速查

### 认证与令牌
| 命令 | 说明 |
|---|---|
| `hipo authorize --role candidate/employer [--email x]` | OAuth 授权（PKCE + 邮箱验证码） |
| `hipo status` | 查看当前 token：角色/scope/过期时间 |
| `hipo refresh` | 强制刷新 access_token |
| `hipo token-sync [--refresh]` | 导出 token 到浏览器 localStorage（4 个 base64） |
| `hipo accounts list/current/switch/delete` | 多账户管理（多邮箱多角色分开存） |

### 求职者
| 命令 | 说明 |
|---|---|
| `hipo match-jobs [--json]` | 根据我的简历匹配岗位 |
| `hipo resume-extract <file.pdf> [--out x.txt]` | 提取简历文本（PDF/DOCX/TXT） |
| `hipo resume-validate <resume.json>` | 导入前校验 JSON 结构 |
| `hipo resume-import --json <resume.json>` | 校验后导入简历（推荐） |
| `hipo resume-import --text <resume.txt>` | 走平台 AI 服务解析后导入 |

### 招聘方
| 命令 | 说明 |
|---|---|
| `hipo publish-job --title x --text "..." [--json file]` | 发布岗位 |
| `hipo close-job <job_id>` | 关闭已发布的岗位（关闭后不再参与匹配） |
| `hipo search "自然语言描述" [--max n]` | 自然语言搜索候选人 |
| `hipo match-candidates --text "..." / --json cond.json / --job <id>` | 结构化匹配候选人 |
| `hipo market --keyword python [--industry tech]` | 人才市场分析 |
| `hipo stats` | 平台统计 |

### 运维诊断
| 命令 | 说明 |
|---|---|
| `hipo healthcheck` | 检查 API / MCP / OAuth metadata / Embedding 连通性 |
| `hipo e2e` | 端到端冒烟：token → REST /auth/me → MCP 会话 → 工具调用 |

任意命令加 `--help` 查看详细参数；大部分命令支持 `--json` 输出原始 JSON 便于脚本消费。

## 简历导入两种方式

1. **推荐：`--json`** — 用你自己的 LLM / Agent 把简历解析为结构化 JSON
   （参考 `examples/resume.example.json`），本地校验通过后导入。不依赖平台 AI 服务。
   ```bash
   hipo resume-import --json my_resume.json
   ```
2. **`--text`** — 传入简历纯文本，由平台后端 AI 服务解析（需要后端配置了
   AI_SERVICE_URL；否则会提示改用 `--json`）。
   ```bash
   hipo resume-extract resume.pdf --out resume.txt
   hipo resume-import --text resume.txt
   ```

`hipo resume-validate` 会提前发现常见问题：`duration_months` 缺失
（会导致经验年限不累计、岗位匹配经验分拿不到）、字段超长、类型错误、
数量超限等，规则与后端 `POST /agent/import-resume` 的白名单/上限一致。

## 目录结构

```text
src/hipowork_cli/
  __init__.py               # 统一入口（console script: hipo）
  scripts/
    hipo_auth.py            # 共享认证库：token 仓库/刷新/API 客户端
    hipo_authorize.py       # OAuth 授权 + 本地回调 + 统一成功页
    hipo_token_status.py    # token 状态
    hipo_token_refresh.py   # 强制刷新
    hipo_token_sync.py      # token → 浏览器 localStorage
    hipo_accounts.py        # 多账户管理
    hipo_mcp_client.py      # 业务封装：匹配/发布/搜索/统计/导入等
    hipo_match_jobs.py      # 求职者匹配岗位
    hipo_publish_job.py     # 发布岗位
    hipo_close_job.py       # 关闭岗位
    hipo_search_candidates.py  # 搜索候选人
    hipo_match_candidates.py   # 结构化匹配候选人
    hipo_market.py          # 市场分析
    hipo_stats.py           # 平台统计
    hipo_resume_extract.py  # 简历文本提取
    hipo_resume_validate.py # 简历 JSON 校验
    hipo_resume_import.py   # 简历导入
    hipo_healthcheck.py     # 服务连通性检查
    hipo_e2e.py             # 端到端冒烟
  templates/
    success.html            # 统一授权成功页（深色玻璃拟态）
  examples/
    resume.example.json     # 结构化简历示例
    job.example.json        # 结构化岗位示例
tests/
  test_hipo_accounts.py     # 多账户管理单元测试
  test_hipo_resume_import.py  # 简历流水线单元测试
```

## 相关服务地址

```text
API:   https://api.hipowork.com        (docs: /docs)
MCP:   https://mcp.hipowork.com/mcp
官网:  https://hipowork.com
```
