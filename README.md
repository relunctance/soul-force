# SoulForce

**SoulForce** — AI Agent Memory Evolution System. Make your OpenClaw smarter with every conversation.

[![MIT License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)

> 📖 **中文文档**: [README.zh-CN.md](README.zh-CN.md)

---

## The Core Problem ❌

**OpenClaw doesn't automatically update SOUL.md, USER.md, or IDENTITY.md.**

You write them once. They stay the same forever. Your AI never gets smarter.

| Pain Point | SoulForce Fix |
|------------|--------------|
| ❌ SOUL.md goes stale after first write — AI stays the same | ✅ Auto-analyzes memory, discovers patterns, evolves SOUL.md |
| ❌ Correct the same mistake 10 times, AI forgets | ✅ Corrections logged → auto-evolved after 3 repetitions |
| ❌ USER.md doesn't track new preferences | ✅ USER.md auto-syncs user preference changes |
| ❌ Multi-agent teams pollute each other's memory | ✅ Full isolation — each agent has its own storage |
| ❌ Manual memory maintenance is tedious | ✅ Cron automation — zero effort, continuous evolution |
| ❌ hawk-bridge memories fade without沉淀 | ✅ Integrates with hawk-bridge vector store, extracts to files |

**Bottom line**: This skill makes your OpenClaw continuously smarter. Every correction, every pattern, every preference gets captured and evolved.

---

## Key Features

### 🔄 Auto Evolution
- Reads `memory/*.md` daily logs
- Analyzes `.learnings/` correction records
- Uses **configured LLM** to detect recurring patterns
- Auto-updates SOUL.md / USER.md / IDENTITY.md / MEMORY.md

### 🏢 Multi-Agent Isolation
Each agent's data is **physically isolated** — no cross-contamination:

| Agent | Backup Dir | State Dir |
|-------|-----------|----------|
| main | `.soulforge-main/backups/` | `.soulforge-main/` |
| wukong | `.soulforge-wukong/backups/` | `.soulforge-wukong/` |
| tseng | `.soulforge-tseng/backups/` | `.soulforge-tseng/` |

### 🧠 hawk-bridge Integration
- Reads hawk-bridge's **LanceDB vector memory**
- Incremental processing — only analyzes new memories
- Shared data source with hawk-bridge for dual-layer backup

### 🔒 Safety
- **Incremental updates**: Only appends, never overwrites
- **Backup before write**: Auto-backup before every update
- **Dedup detection**: Skips patterns already in files
- **Preview mode**: `--dry-run` to see changes first

---

## Before vs After — A Real Example

### SOUL.md

**Before (static, written once):**

```markdown
# SOUL.md

## Who I Am

I'm an AI assistant that helps with tasks.

## How I Work

I try to be helpful and accurate.
```

**After running SoulForge for 1 week:**

```markdown
# SOUL.md

## Who I Am

I'm an AI assistant that helps with tasks.

## How I Work

I try to be helpful and accurate.

---

<!-- SoulForge Update | 2026-04-05 -->
## Behavior: User Prefers Numbered Options

**Source**: memory/2026-04-04.md, memory/2026-04-05.md
**Pattern Type**: communication
**Confidence**: High (observed 4 times)

**Content**:
User gets overwhelmed by long text options. ALWAYS present choices as numbered lists (1/2/3) instead of paragraphs. Keep it scannable.

<!-- /SoulForge Update -->

<!-- SoulForge Update | 2026-04-03 -->
## Behavior: User Corrected "Do It Yourself" Pattern

**Source**: .learnings/LEARNINGS.md (correction)
**Pattern Type**: correction
**Confidence**: High (observed 3 times)

**Content**:
When user says "why does this keep happening" or expresses frustration, it means I should fix the root cause, not just patch symptoms. User values prevention over remediation.

<!-- /SoulForge Update -->
```

---

### USER.md

**Before (generic, never updated):**

```markdown
# USER.md

## User

A person who uses this AI assistant.
```

**After running SoulForge for 1 week:**

```markdown
# USER.md

## User

A person who uses this AI assistant.

---

<!-- SoulForge Update | 2026-04-04 -->
## Discovered: User Works on VPN Project

**Source**: memory/2026-04-04.md
**Pattern Type**: project
**Confidence**: High (observed 2 times)

**Content**:
User is building "SwiftPass VPN" - a subscription VPN service for Russian market. Uses XrayR/sing-box, Cloudflare, USDT+Stripe payments. Team: main + wukong + bajie + bailong + tseng.

<!-- /SoulForge Update -->

<!-- SoulForge Update | 2026-04-05 -->
## Discovered: User Hates Manual Steps

**Source**: memory/2026-04-05.md
**Pattern Type**: preference
**Confidence**: High (observed 5 times)

**Content**:
User repeatedly asks to "automate this". Never suggests manual workarounds. If a task can be scripted, do it without asking.

<!-- /SoulForge Update -->
```

---

### What Changed

| File | Before | After |
|------|--------|-------|
| SOUL.md | 150 chars, 0 updates | 850 chars, 12 updates, 4 new behavior patterns |
| USER.md | 80 chars, static | 620 chars, 6 updates, project + preferences tracked |
| IDENTITY.md | Empty | Full team structure documented |
| MEMORY.md | Empty | 3 important decisions recorded |

**The AI becomes genuinely smarter over time.**

---

## How It Works

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  Memory    │ ──▶ │   Analyzer   │ ──▶ │  Evolver    │
│  Sources   │     │  (LLM)       │     │  (Safe)     │
└─────────────┘     └──────────────┘     └─────────────┘
     │                    │                    │
     ▼                    ▼                    ▼
memory/*.md         Pattern Detection      SOUL.md
.learnings/         3× threshold          USER.md
hawk-bridge         Confidence Scoring     IDENTITY.md
                                          MEMORY.md
```

**Triggers:**
- Same pattern appears **3+ times**
- User corrects same issue **2+ times**
- New preference or decision discovered

---

## Quick Start

### 1. Install

```bash
# Via clawhub (recommended)
clawhub install soul-force --force

# Manual clone
git clone https://github.com/relunctance/soul-force.git ~/.openclaw/skills/soul-force
```

> ⚠️ **Why `--force`?** ClawHub uses VirusTotal to scan all skills. Any skill that calls an external API is flagged as "suspicious" — this is a false positive. The `--force` flag bypasses this warning. SoulForce only uses the LLM you already configured in OpenClaw.

### 2. Run

> No API key configuration needed — SoulForce automatically reads your OpenClaw settings.

```bash

```bash
# Manual trigger
python3 ~/.openclaw/skills/soul-force/scripts/soulforge.py run

# Preview mode (no writes)
python3 ~/.openclaw/skills/soul-force/scripts/soulforge.py run --dry-run

# Check status
python3 ~/.openclaw/skills/soul-force/scripts/soulforge.py status
```

### 3. Schedule (Recommended)

```bash
# Set cron via command (every 2 hours)
soulforge.py cron-set --every 120

# Other intervals
soulforge.py cron-set --every 60    # every hour
soulforge.py cron-set --every 30    # every 30 minutes
soulforge.py cron-set --every 240   # every 4 hours

# View current schedule
soulforge.py cron-set --show

# Remove cron
soulforge.py cron-set --remove
```

Or via OpenClaw CLI directly:
```bash
openclaw cron add --name soulforce-evolve --every 120m \
  --message "exec python3 ~/.openclaw/skills/soul-force/scripts/soulforge.py run"
```

### 4. View Changelog

```bash
# View English changelog
soulforge.py changelog

# View Chinese changelog
soulforge.py changelog --zh

# View full changelog (no truncation)
soulforge.py changelog --full
```

---

## Multi-Agent Usage

Each agent runs its own instance with isolated workspace:

```bash
# main agent
python3 soulforge.py run --workspace ~/.openclaw/workspace

# wukong agent
python3 soulforge.py run --workspace ~/.openclaw/workspace-wukong

# tseng agent
python3 soulforge.py run --workspace ~/.openclaw/workspace-tseng
```

---

## hawk-bridge Integration

**With hawk-bridge installed, SoulForce gains:**

| Feature | Description |
|---------|-------------|
| Semantic Search | Searches 33 vector memories from hawk-bridge |
| Cross-Session | hawk-bridge memories auto-analyzed |
| Incremental | Only processes new memories |
| Dual Backup | Vector layer (hawk) + File layer (soulforce) |

```bash
# Install hawk-bridge first (if not present)
clawhub install hawk-bridge --force

# SoulForce auto-detects hawk-bridge
python3 soulforge.py run
```

---

## Project Structure

```
soul-force/
├── SKILL.md                    # OpenClaw Skill definition
├── README.md                   # English documentation
├── README.zh-CN.md           # 中文文档
├── soulforce/
│   ├── __init__.py
│   ├── config.py              # Config (multi-agent isolation)
│   ├── memory_reader.py        # Multi-source memory reading
│   ├── analyzer.py            # LLM-powered pattern analyzer
│   └── evolver.py             # Safe file updates
├── scripts/
│   └── soulforge.py            # CLI entry point
├── references/
│   └── ARCHITECTURE.md        # Technical architecture
└── tests/
    └── test_soulforge.py       # Unit tests (11/11 passing)
```

---

## Requirements

- Python 3.10+
- OpenClaw with configured LLM
- OpenClaw (optional, for cron)
- hawk-bridge (optional, for vector memory)

---

## License

MIT License — see [LICENSE](LICENSE)
