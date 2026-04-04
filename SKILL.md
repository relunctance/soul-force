---
name: soul-force
description: "SoulForce - AI Agent Memory Evolution System. Automatically analyzes memory files and evolves SOUL.md, USER.md, IDENTITY.md, and other workspace identity files using MiniMax API. Triggers when: agent accumulates new patterns in memory/*.md or .learnings/, needs to update behavioral guidelines, discovers recurring user preferences, or evolves team workflows. Use when: you want your AI to become smarter over time automatically, need to propagate learnings across sessions, or want automatic identity file maintenance. NOT for: one-shot tasks, real-time responses, or when manual curation is preferred."
metadata:
  openclaw:
    requires:
      bins:
        - python3
    env:
      MINIMAX_API_KEY:
        description: MiniMax API key for pattern analysis
        required: true
---

# SoulForce Skill

SoulForce automatically evolves your AI agent's identity files by analyzing memory sources and discovering patterns over time.

## Pain Points Solved ❌ → ✅

| Pain Point | SoulForce Solution |
|------------|-------------------|
| SOUL.md goes stale after first write | ✅ Auto-analyzes memory, discovers new patterns |
| Same corrections repeated endlessly | ✅ Corrections logged → auto-evolved after 3× |
| User preferences forgotten | ✅ USER.md auto-syncs preference changes |
| Multi-agent memory contamination | ✅ Full isolation per agent workspace |
| Manual memory maintenance | ✅ Cron automation, zero effort |
| hawk-bridge memories fade away | ✅ Integrates with hawk-bridge vector store |

## Quick Start

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

## Configuration

Set your MiniMax API key:

```bash
export MINIMAX_API_KEY="your-api-key"
```

> **OpenClaw users**: API key is injected automatically. Manual setting not needed.

## How It Works

```
memory/*.md + .learnings/ + hawk-bridge → MiniMax Analysis → Pattern Discovery → File Updates
```

### Trigger Conditions

| File | Triggers |
|------|----------|
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

Each agent runs its own cron job:

```bash
# For main
openclaw cron add --name soulforce-evolve --every 120m \
  --message "exec python3 ~/.openclaw/skills/soul-force/scripts/soulforge.py run"

# For wukong
openclaw cron add --name soulforce-evolve-wukong --every 120m \
  --message "exec python3 ~/.openclaw/skills/soul-force/scripts/soulforge.py run --workspace ~/.openclaw/workspace-wukong"
```

## hawk-bridge Integration

With hawk-bridge installed, SoulForce gains:

| Feature | Description |
|---------|-------------|
| Semantic Memory | Searches 33 vector memories from hawk-bridge |
| Cross-Session | hawk-bridge memories auto-analyzed |
| Incremental | Only processes new memories |
| Dual Backup | Vector layer (hawk) + File layer (soulforce) |

```bash
# Install hawk-bridge first (if not present)
clawhub install hawk-bridge --force

# SoulForce auto-detects hawk-bridge on next run
python3 soulforge.py run
```

## Safety

- **Incremental**: Only appends, never overwrites
- **Backups**: Timestamped backups in `.soulforge-{agent}/backups/`
- **Dry Run**: Preview with `--dry-run`
- **Dedup**: Skips patterns already in files
- **Threshold**: Patterns need 3+ occurrences before promoting

## Files Generated

- `.soulforge-{agent}/backups/*.bak` — Timestamped backups
- `.soulforge-{agent}/` — Agent-specific state

## Exit Codes

- `0` — Success
- `1` — Error (check output)
