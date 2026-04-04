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
- Uses **MiniMax API** to detect recurring patterns
- Auto-updates SOUL.md / USER.md / IDENTITY.md / MEMORY.md

### 🏢 Multi-Agent Isolation
Each agent's data is **physically isolated** — no cross-contamination:

| Agent | Backup Dir | State Dir |
|-------|-----------|----------|
| main | `.soulforge-main/backups/` | `.soulforge-main/` |
| wukong | `.soulforge-wukong/backups/` | `.soulforge-wukong/` |
| tseng | `.soulforge-tseng/backups/` | `.soulforge-tseng/` |

### 🧠 hawk-bridge Integration
- Reads hawk-bridge's **LanceDB vector memory** (33 vectors)
- Incremental processing — only analyzes new memories
- Shared data source with hawk-bridge for dual-layer backup

### 🔒 Safety
- **Incremental updates**: Only appends, never overwrites
- **Backup before write**: Auto-backup before every update
- **Dedup detection**: Skips patterns already in files
- **Preview mode**: `--dry-run` to see changes first

---

## Before vs After

**Before (Static):**
```
SOUL.md (written 3 months ago)
├── Communication: Be concise
├── Role: Team coordinator
└── Behavior: (never changes)
```

**After (Continuously Evolving):**
```
SOUL.md (auto-evolving)
├── Communication: Be concise
├── Role: Team coordinator
├── Behavior:
│   ├── ✅ User said "options too long" → Added "use numbered lists"
│   ├── ✅ User prefers automation → Added "automate when possible"
│   └── ✅ Claude Code rate limit hit → Added "avoid dense calls"
└── Evolution log: 12 updates, 4 new patterns
```

---

## How It Works

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  Memory    │ ──▶ │   Analyzer   │ ──▶ │  Evolver    │
│  Sources   │     │  (MiniMax)   │     │  (Safe)     │
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

> ⚠️ **Why `--force`?** ClawHub uses VirusTotal to scan all skills. Any skill that calls an external API (like MiniMax) is flagged as "suspicious" — this is a false positive. The `--force` flag bypasses this warning so legitimate tools can be installed. SoulForce only calls the LLM API you already configured.

### 2. Configure API Key

```bash
export MINIMAX_API_KEY="your-minimax-api-key"
```

> **OpenClaw users**: API key is injected automatically by OpenClaw. No manual setup needed.

### 3. Run

```bash
# Manual trigger
python3 ~/.openclaw/skills/soul-force/scripts/soulforge.py run

# Preview mode (no writes)
python3 ~/.openclaw/skills/soul-force/scripts/soulforge.py run --dry-run

# Check status
python3 ~/.openclaw/skills/soul-force/scripts/soulforge.py status
```

### 4. Schedule (Recommended)

```bash
# Every 2 hours via OpenClaw cron
openclaw cron add --name soulforce-evolve --every 120m \
  --message "exec python3 ~/.openclaw/skills/soul-force/scripts/soulforge.py run"
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
│   ├── analyzer.py            # MiniMax API analyzer
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
- MiniMax API Key
- OpenClaw (optional, for cron)
- hawk-bridge (optional, for vector memory)

---

## License

MIT License — see [LICENSE](LICENSE)
