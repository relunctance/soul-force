---
name: soul-force
description: "OpenClaw - AI Agent Memory Evolution System. The core problem: OpenClaw never auto-updates SOUL.md, USER.md, or IDENTITY.md — corrections are forgotten, preferences fade, AI never gets smarter. SoulForce auto-evolves these files by analyzing memory patterns via your configured LLM. Features: incremental analysis, confidence-based filtering, smart insertion points (append/section/top), review mode, manual backups. Use when: you want your AI to learn from corrections, discover recurring patterns, and evolve behavior automatically without manual editing. NOT for: one-shot tasks or when manual curation is preferred."
metadata:
  openclaw:
    requires:
      bins:
        - python3
---

# SoulForce Skill

**SoulForce** makes your OpenClaw continuously smarter by auto-evolving identity files.

> 📖 **中文说明**: [README.zh-CN.md](README.zh-CN.md)

## The Core Problem ❌

**OpenClaw doesn't auto-update SOUL.md, USER.md, or IDENTITY.md.** Your AI never gets smarter.

SoulForce fixes this.

## Pain Points Solved

| Pain Point | SoulForce Solution |
|------------|------------------|
| ❌ SOUL.md goes stale after first write | ✅ Auto-evolves from memory patterns |
| ❌ Same corrections repeated endlessly | ✅ Corrections → auto-evolved after 3× |
| ❌ User preferences forgotten | ✅ USER.md auto-syncs preferences |
| ❌ Multi-agent memory contamination | ✅ Full isolation per workspace |
| ❌ Manual memory maintenance | ✅ Cron automation — zero effort |
| ❌ hawk-bridge memories fade away | ✅ Integrates with hawk-bridge vector store |
| ❌ Low-quality patterns applied blindly | ✅ Confidence-based filtering (>0.8 auto, 0.5-0.8 review) |

## New Features (v2.1)

| Feature | Description |
|---------|-------------|
| **Incremental Analysis** | Only analyzes new entries since last run (via `last_run` timestamp) |
| **Confidence Levels** | High (>0.8) auto-apply, Medium (0.5-0.8) review, Low (<0.5) ignore |
| **Smart Insertion** | Insert patterns at `append`, `section:{title}`, or `top` |
| **Review Mode** | `soulforge.py review` — preview patterns without writing |
| **Apply from Review** | `soulforge.py apply --confirm` — apply reviewed patterns |
| **Manual Backups** | `soulforge.py backup --create` — manual snapshots |
| **Enhanced Retention** | Important files (SOUL.md, IDENTITY.md) keep 20 backups; others keep 10 |
| **Externalized Help** | Help texts in `references/help-zh.md` and `references/help-en.md` |
| **LLM via exec** | Uses OpenClaw's exec tool for LLM calls instead of direct API |
| **Token Budget** | Truncates entries to stay within `max_token_budget` (default 4096 tokens) |
| **Schema Validation** | Pydantic validation of LLM responses; retry on failure; raw output saved to `review/failed/` |
| **Pattern Expiry** | Patterns can have `expires_at` date; `soulforge.py clean --expired` removes stale blocks |
| **Auto-Rollback** | Writes are validated post-commit; failed writes auto-restore from snapshot |
| **hawk-bridge Incremental** | Only syncs entries updated since last `hawk-bridge` sync timestamp |
| **Config File** | `~/.soulforgerc.json` with `config --show` / `config --set key=value` |
| **Feishu Notifications** | `run --notify` sends evolution results to configured Feishu chat |

## New Features (v2.2)

| Feature | Description |
|---------|-------------|
| **Pattern Conflict Detection** | Detects patterns targeting same file with opposite advice; review shows ⚠️ CONFLICT |
| **Natural Language Query** | `soulforge.py ask "question"` — synthesize answers from patterns and memories |
| **Richer Dry-run Preview** | `run --dry-run` shows unified diff format (`--- file / +++ file / @@`) |
| **Pattern Tags** | Patterns have `tags: List[str]`; filter by `--tag preference` or `--tag error` |
| **Interactive Review** | `review --interactive` asks y/n per pattern; saves to `interactive_{timestamp}.json` |
| **Real Token Counting** | Uses `tiktoken` for accurate token counts (falls back to chars/4) |
| **Changelog Visualization** | `changelog --visual` shows evolution history as ASCII tree |

## Quick Start

### Install / Update

```bash
clawhub install soul-force --force
```

> ⚠️ `--force` is needed because ClawHub's VirusTotal scan flags any skill calling external APIs as "suspicious" — false positive. SoulForce only calls your configured LLM via OpenClaw.

### Run Evolution

```bash
python3 ~/.openclaw/workspace/skills/soul-force/scripts/soulforge.py run
```

### Dry Run (Preview)

```bash
python3 ~/.openclaw/workspace/skills/soul-force/scripts/soulforge.py run --dry-run
```

### Force Apply (All Patterns)

```bash
python3 ~/.openclaw/workspace/skills/soul-force/scripts/soulforge.py run --force
```

### Review Mode

```bash
python3 ~/.openclaw/workspace/skills/soul-force/scripts/soulforge.py review
```

Review results are saved to `.soulforge-{agent}/review/latest.json`.

### Apply from Review

```bash
# Preview what would be applied
python3 ~/.openclaw/workspace/skills/soul-force/scripts/soulforge.py apply

# Confirm and apply
python3 ~/.openclaw/workspace/skills/soul-force/scripts/soulforge.py apply --confirm
```

### Manual Backup

```bash
python3 ~/.openclaw/workspace/skills/soul-force/scripts/soulforge.py backup --create
```

### Check Status

```bash
python3 ~/.openclaw/workspace/skills/soul-force/scripts/soulforge.py status
```

## Confidence-Based Filtering

| Confidence | Level | Action |
|------------|-------|--------|
| > 0.8 | High | Auto-apply |
| 0.5 - 0.8 | Medium | Needs review (`soulforge.py review`) |
| < 0.5 | Low | Ignored |

Use `--force` flag to apply all patterns regardless of confidence.

## Smart Insertion Points

Patterns can specify where to insert in the target file:

- **`append`** (default): Add to end of file
- **`section:{title}`**: Insert under `## {title}` section
- **`top`**: Insert at beginning of file

## Incremental Analysis

After the first run, SoulForge only analyzes entries newer than the last run timestamp stored in `.soulforge-{agent}/last_run`. To force a full analysis, delete the `last_run` file or run with `--force`.

## How It Works

```
memory/*.md + .learnings/ + hawk-bridge → LLM Analysis → Pattern Discovery → File Updates
```

**Trigger Conditions:**

| File | Trigger |
|------|---------|
| SOUL.md | Same behavior 3+ times, user corrections 2+ times |
| USER.md | New preferences, project changes |
| IDENTITY.md | Role/responsibility changes |
| MEMORY.md | Important decisions, milestones |
| AGENTS.md | New workflow patterns |
| TOOLS.md | Tool usage discoveries |

## Multi-Agent Isolation

Each agent has **completely isolated** storage:

```
~/.openclaw/workspace/        → .soulforge-main/
~/.openclaw/workspace-wukong/ → .soulforge-wukong/
~/.openclaw/workspace-tseng/  → .soulforge-tseng/
```

## hawk-bridge Integration

With hawk-bridge installed, SoulForce gains:

| Feature | Description |
|---------|-------------|
| Semantic Memory | Searches vector memories from hawk-bridge |
| Cross-Session | hawk-bridge memories auto-analyzed |
| Incremental | Only processes new memories |
| Dual Backup | Vector layer (hawk) + File layer (soulforce) |

```bash
clawhub install hawk-bridge --force
python3 soulforge.py run  # auto-detects hawk-bridge
```

## Safety

- **Incremental**: Only appends/inserts, never overwrites existing content
- **Backups**: Timestamped backups in `.soulforge-{agent}/backups/`
  - Important files (SOUL.md, IDENTITY.md): Keep 20 backups
  - Normal files: Keep 10 backups
- **Dry Run**: Preview with `--dry-run`
- **Dedup**: Skips patterns already in files
- **Confidence Filter**: Low-confidence patterns ignored
- **Review Mode**: Preview all patterns before applying

## Schedule (Recommended)

```bash
# Set cron (every 2 hours)
python3 soulforge.py cron-set --every 120

# View/remove
python3 soulforge.py cron-set --show
python3 soulforge.py cron-set --remove
```

## All Commands

```
run          Run evolution process
review       Review patterns without writing (supports --tag, --confidence, --interactive)
apply        Apply patterns from review (supports --confirm, --interactive)
backup       Backup management
status       Show current status
diff         Show changes since last run
stats        Show evolution statistics
inspect      Inspect patterns for a specific file
restore      Restore files from backup
reset        Reset SoulForge state
template     Generate standard templates
changelog    Show evolution changelog (supports --visual)
cron         Cron setup help
cron-set     Set/update cron schedule
ask          Natural language query (v2.2.0)
help         Show help message
```

Run `python3 soulforge.py help` or `python3 soulforge.py help --zh` for full help.

## Changelog

```bash
# View changelog (English)
python3 soulforge.py changelog

# View changelog (Chinese)
python3 soulforge.py changelog --zh

# View full changelog
python3 soulforge.py changelog --full
```

Changelogs are stored at:
- `.soulforge-{agent}/CHANGELOG.md` (English)
- `.soulforge-{agent}/CHANGELOG.zh-CN.md` (Chinese)

## Exit Codes

- `0` — Success
- `1` — Error (check output)
