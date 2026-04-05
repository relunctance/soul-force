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
- 调用 **配置的 LLM** 发现反复出现的模式
- 自动更新 SOUL.md / USER.md / IDENTITY.md / MEMORY.md / AGENTS.md / TOOLS.md
- **智能插入位置**：追加 / 按章节插入 / 插入文件顶部

### 🏢 多 Agent 完全隔离
每个 Agent 的数据**物理隔离**，绝不互相污染：

| Agent | 备份目录 | 状态目录 |
|-------|---------|---------|
| main | `.soulforge-main/backups/` | `.soulforge-main/` |
| wukong | `.soulforge-wukong/backups/` | `.soulforge-wukong/` |
| tseng | `.soulforge-tseng/backups/` | `.soulforge-tseng/` |

### 🧠 hawk-bridge 无缝集成
- 读取 hawk-bridge 的 **LanceDB 向量记忆库**
- 增量同步，只获取上次运行后的新条目
- 进化结果与 hawk-bridge 共用同一套数据源
- `last_hawk_sync` 时间戳追踪，高效增量处理

### 🔒 安全设计
- **增量更新**：只追加，不覆盖已有内容
- **写前备份**：重要文件保留 20 个备份，普通文件 10 个
- **自动回滚**：写入后验证，失败自动从快照恢复
- **Schema 验证**：Pydantic 验证 LLM 输出，失败重试 1 次
- **去重检测**：已有内容不重复添加
- **预览模式**：`--dry-run` 先看结果再写入
- **Pattern 过期**：可设置 TTL，`--clean --expired` 清理过期块

---

## 使用前 vs 使用后 — 真实案例

### SOUL.md

**使用前（静态，写过一次就停了）：**

```markdown
# SOUL.md

## 我是谁

我是一个 AI 助手，帮助完成各种任务。

## 工作方式

我尽量做到有帮助和准确。
```

**使用 SoulForge 1 周后：**

```markdown
# SOUL.md

## 我是谁

我是一个 AI 助手，帮助完成各种任务。

## 工作方式

我尽量做到有帮助和准确。

---

<!-- SoulForge 更新 | 2026-04-05 -->
## 行为：用户偏好编号选项

**来源**: memory/2026-04-04.md, memory/2026-04-05.md
**模式类型**: 沟通
**置信度**: 高（观察4次）

**内容**:
用户看到长文本选项会感到压力。所有选项必须用编号列表呈现（1/2/3），保持简洁可扫描。

<!-- /SoulForge 更新 -->

<!-- SoulForge 更新 | 2026-04-03 -->
## 行为：用户纠正"自己动手"模式

**来源**: .learnings/LEARNINGS.md (纠错)
**模式类型**: 纠错
**置信度**: 高（观察3次）

**内容**:
当用户说"为什么总是这样"或表达不满时，意味着我应该解决根本原因，而不是只修补表面。用户重视预防而不是补救。

<!-- /SoulForge 更新 -->
```

---

### USER.md

**使用前（通用，从不更新）：**

```markdown
# USER.md

## 用户

使用这个 AI 助手的人。
```

**使用 SoulForge 1 周后：**

```markdown
# USER.md

## 用户

使用这个 AI 助手的人。

---

<!-- SoulForge 更新 | 2026-04-04 -->
## 发现：用户偏好简洁回复

**来源**: memory/2026-04-04.md
**模式类型**: 偏好
**置信度**: 高（观察3次）

**内容**:
用户偏好简洁、可操作的回复，而不是冗长的解释。先给答案，有必要再简要补充。

<!-- /SoulForge 更新 -->

<!-- SoulForge 更新 | 2026-04-05 -->
## 发现：用户讨厌手动操作

**来源**: memory/2026-04-05.md
**模式类型**: 偏好
**置信度**: 高（观察5次）

**内容**:
用户反复要求"把这个自动化"。永远不要建议手动解决方案。如果一个任务可以脚本化，就直接做，不要问。

<!-- /SoulForge 更新 -->
```

---

### 变化对比

| 文件 | 使用前 | 使用后 |
|------|--------|--------|
| SOUL.md | 150 字符，0 次更新 | 850 字符，12 次更新，4 个新行为模式 |
| USER.md | 80 字符，静止 | 620 字符，6 次更新，项目+偏好已追踪 |
| IDENTITY.md | 空 | 完整的团队结构文档 |
| MEMORY.md | 空 | 3 个重要决策已记录 |

**AI 真的在变得越来越聪明。**

---

## 工作原理

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  记忆源     │ ──▶ │   分析引擎    │ ──▶ │  进化器     │
│  Memory    │     │  LLM API    │     │  Safe Write │
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
git clone https://github.com/relunctance/soul-force.git ~/.openclaw/workspace/skills/soul-force
```

> ⚠️ **为什么需要 `--force`？** ClawHub 使用 VirusTotal 扫描所有插件。任何调用外部 API 的插件都会被标记为"suspicious"——这是误报。`--force` 参数用于绕过这个误报。SoulForce 只使用你在 OpenClaw 中已配置的 LLM。

### 2. 运行

> 无需配置 API Key — SoulForce 自动读取 OpenClaw 的配置。

```bash
# 手动触发
python3 ~/.openclaw/workspace/skills/soul-force/scripts/soulforge.py run

# 预览模式（只查看，不写入）
python3 ~/.openclaw/workspace/skills/soul-force/scripts/soulforge.py run --dry-run

# 强制应用所有模式（忽略置信度阈值）
python3 ~/.openclaw/workspace/skills/soul-force/scripts/soulforge.py run --force

# Review 模式：生成模式但不写入
python3 ~/.openclaw/workspace/skills/soul-force/scripts/soulforge.py review

# 确认后从 review 结果写入
python3 ~/.openclaw/workspace/skills/soul-force/scripts/soulforge.py apply --confirm

# 查看状态
python3 ~/.openclaw/workspace/skills/soul-force/scripts/soulforge.py status
```

### 3. 定时任务（推荐）

```bash
# 通过命令设置定时任务（每2小时）
soulforge.py cron-set --every 120

# 其他间隔
soulforge.py cron-set --every 60     # 每小时
soulforge.py cron-set --every 30     # 每30分钟
soulforge.py cron-set --every 240    # 每4小时

# 查看当前定时任务
soulforge.py cron-set --show

# 删除定时任务
soulforge.py cron-set --remove
```

或直接通过 OpenClaw CLI：
```bash
openclaw cron add --name soulforce-evolve --every 120m \
  --message "exec python3 ~/.openclaw/workspace/skills/soul-force/scripts/soulforge.py run"
```

### 4. 配置管理

```bash
# 查看当前配置
soulforge.py config --show

# 设置配置值（持久化到 ~/.soulforgerc.json）
soulforge.py config --set max_token_budget=8192
soulforge.py config --set rollback_auto_enabled=true
```

### 5. 维护命令

```bash
# 清理过期 Pattern 块
soulforge.py clean --expired           # 先 dry run
soulforge.py clean --expired --confirm  # 确认后删除

# 手动快照备份
soulforge.py backup --create

# 回滚上次失败的写入（自动从备份恢复）
soulforge.py rollback --auto

# 查看上次运行以来的变化
soulforge.py diff
```

### 6. 查看更新日志

```bash
# 查看英文更新日志
soulforge.py changelog

# 查看中文更新日志
soulforge.py changelog --zh

# 查看完整日志（不截断）
soulforge.py changelog --full
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
├── soulforge/
│   ├── __init__.py           # 包初始化（v2.1.0）
│   ├── config.py              # 配置（多 Agent 隔离，支持 config.json）
│   ├── memory_reader.py        # 多源记忆读取（增量）
│   ├── analyzer.py            # LLM 模式分析（Schema 验证）
│   ├── evolver.py             # 安全文件更新（自动回滚）
│   └── schema.py              # Pydantic 数据模型
├── scripts/
│   └── soulforge.py            # CLI 入口
├── references/
│   ├── ARCHITECTURE.md        # 技术架构
│   ├── help-en.md             # 英文帮助文本
│   └── help-zh.md             # 中文帮助文本
└── tests/
    └── test_soulforge.py       # 单元测试
```

---

## 环境要求

- Python 3.10+
- OpenClaw（已配置 LLM）
- OpenClaw（可选，用于 cron）
- hawk-bridge（可选，增强向量记忆）

---

## License

MIT License - 参见 [LICENSE](LICENSE)
