# hipowork-cli

<div align="center">

# Make Your Resume Seen by AI
### Where Opportunities Meet Talent Naturally

[![PyPI](https://img.shields.io/pypi/v/hipowork-cli?color=blue)](https://pypi.org/project/hipowork-cli/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![OAuth 2.0](https://img.shields.io/badge/Auth-OAuth2.0-green)](https://oauth.net/2/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

[中文文档](README.md) · [English](README_EN.md)

**Official Website:** [https://hipowork.com](https://hipowork.com) · [https://www.hipowork.com](https://www.hipowork.com)  
**Remote MCP Endpoint:** `https://mcp.hipowork.com/mcp`  
**API Endpoint:** `https://api.hipowork.com`

</div>

---

## 🌟 Philosophy

In traditional recruitment, outstanding resumes often sit dormant in static files or closed talent pools, passively waiting for rigid keyword matching.

**HiPo Work** is built to change this paradigm:
- **Transform Resumes into High-Precision Semantic Assets**: Via AI agents or CLI tools, candidates' technical skills, standalone project experiences, responsibilities, and key achievements are fully structured and embedded into semantic vectors.
- **Make Your Resume Instantly Searchable by AI Tools**: Whether it's Claude Code, Cursor, OpenAI Codex, Hermes Agent, or enterprise recruiting agents, candidates can be accurately discovered, evaluated, and contacted within seconds through tool calls.
- **Where Opportunities Meet Talent Naturally**: Say goodbye to blind mass applications and noisy screening. Based on verified project depth and core competencies, employers and candidates achieve two-way, high-relevance matching.

---

## 🔗 Ecosystem & Public Repositories

HiPo Work delivers a complete Agent-native recruitment ecosystem, spanning CLI tools, remote MCP services, and a modern web portal:

| Project / Platform | Link | Description |
|---|---|---|
| **Official Website** | [hipowork.com](https://hipowork.com) | Candidate portal, employer console, job management, and semantic matching demo |
| **hipowork-cli** (This Repo) | [github.com/sexylin/hipowork-cli](https://github.com/sexylin/hipowork-cli) | Client CLI toolkit (PyPI: `pip install hipowork-cli`), providing `hipo` and `hipowork-cli` entrypoints |
| **hipo-mcp** | [github.com/sexylin/hipo-mcp](https://github.com/sexylin/hipo-mcp) | Remote MCP server implementing Model Context Protocol with OAuth 2.0 (PKCE) |
| **MCP Registry** | `io.github.sexylin/hipo-work` | Officially registered MCP coordinates on the Model Context Protocol Registry |

---

## 📦 Installation

```bash
# Install from PyPI (Recommended, Python 3.10+ required)
pip install hipowork-cli

# Optional: with local resume PDF text extraction support
pip install hipowork-cli[resume]
```

After installation, both `hipo` and `hipowork-cli` are available as equivalent commands in your shell.

---

## 🚀 Quick Start

### 1. Login & Authorization

```bash
# Candidate login (displays standard instructions in terminal and completes email verification in browser)
hipowork-cli login --role candidate     # or: hipo login --role candidate

# Employer login
hipowork-cli login --role employer
```

> **Tips**:
> - First-time authorization requires completing email verification code login in the browser. If you are already logged in to the HiPo Work web portal ([hipowork.com](https://hipowork.com)), the authorization screen directly shows **"Authorize"**, allowing one-click approval without re-entering verification codes.
> - Once authorized, tokens are automatically refreshed and persisted securely in `~/.hipo_mcp_tokens.json` (mode `0600`). No manual maintenance required.
> - Successful CLI login automatically opens the Web Handoff page directly into your corresponding profile dashboard.

### 2. Status Check & Account Management

```bash
hipo status          # View current identity, token validity, and scope permissions
hipo refresh         # Force rotate Access Token
hipo accounts list   # List saved accounts (supports seamless switching between multiple emails and roles)
```

### 3. Everyday Usage

```bash
# Candidate: match active jobs based on your resume
hipo match-jobs

# Candidate: import structured resume with local attachment
hipo resume-import --json my_resume.json --attachment my_resume.pdf

# Employer: publish an open position
hipo publish-job --json examples/job.example.json

# Employer: search candidates using natural language
hipo search "Chengdu 5 years experience fullstack developer familiar with Solidity and Go"
```

---

## 📋 Command Reference

### Authentication & Credentials
| Command | Description |
|---|---|
| `hipowork-cli login --role candidate/employer` | Unified login entrypoint (prints formatted instructions and opens browser authorization) |
| `hipo authorize --role candidate/employer` | OAuth authorization (`login` alias, PKCE + email verification) |
| `hipo status` | Inspect current token status, role, permissions, and expiration time |
| `hipo refresh` | Force refresh Access Token |
| `hipo token-sync [--refresh]` | Export token in Base64 format for web frontend debugging |
| `hipo accounts list/current/switch/delete` | Multi-account management (isolated storage across multiple roles and emails) |

### Candidate
| Command | Description |
|---|---|
| `hipo match-jobs [--json]` | Match active platform jobs against your resume, ranked by relevance score with breakdown |
| `hipo resume-extract <file.pdf> [--out x.txt]` | Extract text from resume files locally (supports PDF, DOCX, TXT) |
| `hipo resume-validate <resume.json>` | Validate JSON structure before import (verifies `duration_months`, projects integrity, etc.) |
| `hipo resume-import --json <resume.json> [--attachment file.pdf]` | **Recommended**: Import structured resume JSON directly, optionally archiving original attachment |
| `hipo resume-import --text <resume.txt>` | Upload raw resume text to platform backend AI parser for automatic structuring and import |

### Employer
| Command | Description |
|---|---|
| `hipo publish-job --title x --text "..." [--json file]` | Post a job opening (supports structured criteria and negotiable salary) |
| `hipo close-job <job_id>` | Close an active job opening (closed positions are excluded from candidate searches and matching) |
| `hipo search "natural language query" [--max n]` | Search candidate profiles and experiences directly using natural language queries |
| `hipo match-candidates --text "..." / --json cond.json / --job <id>` | Multi-dimensional candidate matching (combines hard skill filters with semantic vector search) |
| `hipo market --keyword python [--industry tech]` | Talent supply & demand market intelligence for skills and industries |
| `hipo stats` | Platform overview statistics (open positions, candidate demographics, etc.) |

### Operations & End-to-End Diagnostics
| Command | Description |
|---|---|
| `hipo healthcheck` | Health diagnostics: checks API / MCP / OAuth metadata / Embedding connectivity |
| `hipo e2e` | Full end-to-end smoke test: Token verification → REST /auth/me → MCP session → protected tool execution |

> Add `--help` to any command to view available options. Most commands support `--json` output for easy integration into automated scripts and agents.

---

## 📄 Best Practices for Resume Import

### 1. Recommended: `--json` (with Standalone Projects & Original Attachment)
Use your local LLM or Agent to structure your resume into JSON format (refer to `examples/resume.example.json`), paying special attention to:
- **`projects`**: Standalone projects, open-source work, and commercial deliveries (treated and displayed as first-class citizens);
- **`work_experiences`**: Responsibilities, achievements, tech stack, and exact `duration_months` (used for calculating total work experience);
- **`--attachment`**: Include original local PDF/Word files for secure cloud storage and employer preview.

```bash
hipo resume-import --json my_resume.json --attachment my_resume.pdf
```

### 2. Text Parsing: `--text`
If you prefer not to prepare JSON manually, you can extract plain text and let the backend AI parse it automatically:
```bash
hipo resume-extract my_resume.pdf --out resume.txt
hipo resume-import --text resume.txt
```

---

## 🛠️ Local Development & Testing

```bash
git clone git@github.com:sexylin/hipowork-cli.git
cd hipowork-cli

python3 -m venv .venv
.venv/bin/pip install -e .[resume]

# Run full test suite
.venv/bin/python -m unittest discover -s tests
```

---

## 📄 License

Open-sourced under the [MIT License](LICENSE).
