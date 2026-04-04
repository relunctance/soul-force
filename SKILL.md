---
name: soul-force
description: "OpenClaw - AI Agent Memory Evolution System. The core problem: OpenClaw never auto-updates SOUL.md, USER.md, or IDENTITY.md — corrections are forgotten, preferences fade, AI never gets smarter. SoulForce auto-evolves these files by analyzing memory patterns via your configured LLM. Use when: you want your AI to learn from corrections, discover recurring patterns, and evolve behavior automatically without manual editing. NOT for: one-shot tasks or when manual curation is preferred."
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

## Quick Start

### Install

```bash
clawhub install soul-force --force
```

> ⚠️ `--force` is needed because ClawHub's VirusTotal scan flags any skill calling external APIs as "suspicious" — false positive. SoulForce only calls your configured LLM.

### Run Evolution

```
exec python3 ~/.openclaw/skills/soul-force/scripts/soulforge.py run
```

### Dry Run (Preview)

```
exec python3 ~/.openclaw/skills/soul-force/scripts/soulforge.py run --dry-run
```

### Check Status

```
exec python3 ~/.openclaw/skills/soul-force/scripts/soulforge.py status
```

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

- **Incremental**: Only appends, never overwrites
- **Backups**: Timestamped backups in `.soulforge-{agent}/backups/`
- **Dry Run**: Preview with `--dry-run`
- **Dedup**: Skips patterns already in files
- **Threshold**: Patterns need 3+ occurrences before promoting

## Schedule (Recommended)

```bash
# Set cron (every 2 hours)
soulforge.py cron-set --every 120

# View/remove
soulforge.py cron-set --show
soulforge.py cron-set --remove
```

## Changelog

```bash
# View changelog (English)
soulforge.py changelog

# View changelog (Chinese)
soulforge.py changelog --zh

# View full changelog
soulforge.py changelog --full
```

Changelogs are stored at:
- `.soulforge-{agent}/CHANGELOG.md` (English)
- `.soulforge-{agent}/CHANGELOG.zh-CN.md` (Chinese)

## Exit Codes

- `0` — Success
- `1` — Error (check output)
