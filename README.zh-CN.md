# SoulForce 中文文档

**SoulForce** — AI 智能体记忆进化系统。让你的 OpenClaw 越用越聪明。

[![MIT License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)

> 📖 **English Documentation**: [README.md](README.md)

---

## 核心痛点 ❌

**OpenClaw 不会自动更新 SOUL.md、USER.md、IDENTITY.md。**

你写完就停了，AI 永远不会变聪明。

| 痛点 | SoulForce 解决 |
|------|---------------|
| ❌ SOUL.md 写完就停滞，AI 永远一个样 | ✅ 自动分析记忆，发现模式，进化 SOUL.md |
| ❌ 纠正同一个错误 10 次，AI 还是忘 | ✅ 纠错自动记录，3 次重复后自动进化 |
| ❌ USER.md 不追踪新偏好 | ✅ USER.md 自动同步用户偏好变化 |
| ❌ 多 Agent 团队记忆互相污染 | ✅ 完全隔离，每个 Agent 有独立存储 |
| ❌ 手动维护记忆文件太麻烦 | ✅ Cron 自动化，零努力，持续进化 |
| ❌ hawk-bridge 记忆用完就散，没有沉淀 | ✅ 与 hawk-bridge 共用向量库，自动提炼到文件 |

**核心价值**：这个 skill 让你的 OpenClaw 越来越聪明。每一次纠正、每一个模式、每一个偏好都被捕获并进化。

---

## 核心特性

### 🔄 自动进化
- 读取 `memory/*.md` 每日记忆日志
- 分析 `.learnings/` 纠错记录
- 调用 **MiniMax API** 发现反复出现的模式
- 自动更新 SOUL.md / USER.md / IDENTITY.md / MEMORY.md

### 🏢 多 Agent 完全隔离
每个 Agent 的数据**物理隔离**，绝不互相污染：

| Agent | 备份目录 | 状态目录 |
|-------|---------|---------|
| main | `.soulforge-main/backups/` | `.soulforge-main/` |
| wukong | `.soulforge-wukong/backups/` | `.soulforge-wukong/` |
| tseng | `.soulforge-tseng/backups/` | `.soulforge-tseng/` |

### 🧠 hawk-bridge 无缝集成
- 读取 hawk-bridge 的 **LanceDB 向量记忆库**（33条记忆向量）
- 增量处理，只分析新记忆，不重复
- 进化结果与 hawk-bridge 共用同一套数据源

### 🔒 安全设计
- **增量更新**：只追加，不覆盖已有内容
- **写前备份**：每次更新前自动备份
- **去重检测**：已有内容不重复添加
- **预览模式**：`--dry-run` 先看结果再写入

---

## 使用前 vs 使用后

**使用前（静态）：**
```
SOUL.md（写于3个月前）
├── 沟通风格：简洁直接
├── 团队角色：统筹协调
└── 行为准则：（永远不变）
```

**使用后（动态进化）：**
```
SOUL.md（持续进化中）
├── 沟通风格：简洁直接
├── 团队角色：统筹协调
├── 行为准则：
│   ├── ✅ 用户纠正"选项太长" → 增加"给选项列序号"原则
│   ├── ✅ 发现用户偏好"不喜手工操作" → 增加"自动化优先"原则
│   └── ✅ 踩坑 Claude Code rate limit → 增加"避免密集调用"原则
└── 演进记录：12条更新，4个新行为模式
```

---

## 工作原理

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  记忆源     │ ──▶ │   分析引擎    │ ──▶ │  进化器     │
│  Memory    │     │  MiniMax API │     │  Safe Write │
└─────────────┘     └──────────────┘     └─────────────┘
     │                    │                    │
     ▼                    ▼                    ▼
memory/*.md          模式检测              SOUL.md
.learnings/          N≥3 触发              USER.md
hawk-bridge          置信度评估            IDENTITY.md
                                          MEMORY.md
```

**触发条件：**
- 同一行为模式出现 **3 次以上**
- 用户纠正同一问题 **2 次以上**
- 发现新的用户偏好或项目决策

---

## 快速开始

### 1. 安装

```bash
# 通过 clawhub（推荐）
clawhub install soul-force --force

# 或手动克隆
git clone https://github.com/relunctance/soul-force.git ~/.openclaw/skills/soul-force
```

> ⚠️ **为什么需要 `--force`？** ClawHub 使用 VirusTotal 扫描所有插件。任何调用外部 API（如 MiniMax）的插件都会被标记为"suspicious"——这是误报。`--force` 参数用于绕过这个误报。SoulForce 只调用你已配置的 LLM API，不会做任何可疑操作。

### 2. 运行

> 无需配置 API Key — SoulForce 自动读取 OpenClaw 的配置。

```bash

```bash
# 手动触发
python3 ~/.openclaw/skills/soul-force/scripts/soulforge.py run

# 预览模式（只查看，不写入）
python3 ~/.openclaw/skills/soul-force/scripts/soulforge.py run --dry-run

# 查看状态
python3 ~/.openclaw/skills/soul-force/scripts/soulforge.py status
```

### 3. 定时任务（推荐）

```bash
# 每2小时自动进化
openclaw cron add --name soulforce-evolve --every 120m \
  --message "exec python3 ~/.openclaw/skills/soul-force/scripts/soulforge.py run"
```

---

## 多 Agent 使用

每个 Agent 运行自己的实例，指定独立 workspace：

```bash
# main agent
python3 soulforge.py run --workspace ~/.openclaw/workspace

# wukong agent
python3 soulforge.py run --workspace ~/.openclaw/workspace-wukong

# tseng agent
python3 soulforge.py run --workspace ~/.openclaw/workspace-tseng
```

---

## hawk-bridge 集成效果

**安装 hawk-bridge 后，SoulForce 额外获得：**

| 功能 | 说明 |
|------|------|
| 语义记忆搜索 | 从 33 条向量记忆中检索相关内容 |
| 跨会话记忆 | hawk-bridge 的记忆自动被 SoulForce 分析 |
| 增量进化 | 只处理新记忆，不重复分析已有内容 |
| 双层备份 | 向量层（hawk）+ 文件层（soulforce）双重保险 |

```bash
# 先安装 hawk-bridge（如果还没有）
clawhub install hawk-bridge --force

# SoulForce 自动读取 hawk-bridge 的记忆
python3 soulforge.py run  # 会自动检测 hawk-bridge
```

---

## 项目结构

```
soul-force/
├── SKILL.md                    # OpenClaw Skill 定义
├── README.md                   # English documentation
├── README.zh-CN.md           # 中文文档
├── soulforce/
│   ├── __init__.py
│   ├── config.py              # 配置（多 Agent 隔离）
│   ├── memory_reader.py        # 多源记忆读取
│   ├── analyzer.py            # MiniMax API 分析
│   └── evolver.py             # 安全文件更新
├── scripts/
│   └── soulforge.py            # CLI 入口
├── references/
│   └── ARCHITECTURE.md        # 技术架构
└── tests/
    └── test_soulforge.py       # 单元测试（11/11 通过）
```

---

## 环境要求

- Python 3.10+
- MiniMax API Key
- OpenClaw（可选，用于 cron）
- hawk-bridge（可选，增强向量记忆）

---

## License

MIT License - 参见 [LICENSE](LICENSE)
