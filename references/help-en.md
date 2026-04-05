# SoulForge - AI Agent Memory Evolution System

Automatically analyzes memory files, discovers behavioral patterns, and evolves your AI identity files.

## Usage

    soulforge.py run [--workspace PATH] [--dry-run] [--force]
    soulforge.py status [--workspace PATH]
    soulforge.py diff [--workspace PATH]
    soulforge.py stats [--workspace PATH]
    soulforge.py inspect FILE [--workspace PATH]
    soulforge.py restore [FILE] [--backup PATH] [--preview] [--all]
    soulforge.py reset [--workspace PATH]
    soulforge.py template [TEMPLATE]
    soulforge.py changelog [--zh] [--full]
    soulforge.py cron [--every MINUTES]
    soulforge.py cron-set [--every N] [--show] [--remove]
    soulforge.py review [--workspace PATH]
    soulforge.py apply [--confirm] [--workspace PATH]
    soulforge.py backup --create [--workspace PATH]
    soulforge.py help

## Examples

    soulforge.py run                    # Run evolution (with auto-rollback)
    soulforge.py run --dry-run         # Preview mode (no writes)
    soulforge.py run --force           # Force apply all patterns (ignore confidence)
    soulforge.py run --notify          # Run with Feishu notification on completion
    soulforge.py review                 # Review mode: generate patterns without writing
    soulforge.py apply --confirm       # Confirm and apply from review output
    soulforge.py backup --create        # Create manual snapshot
    soulforge.py status                # View current status (includes token budget)
    soulforge.py clean --expired       # Remove expired pattern blocks
    soulforge.py clean --expired --dry-run  # Preview expired blocks without removing
    soulforge.py rollback --auto       # Show rollback info (auto-applied during run)
    soulforge.py config --show         # Show current configuration
    soulforge.py config --set max_token_budget=8192  # Set config value
    soulforge.py changelog             # View changelog

---

## Commands

### run
Run the evolution process. Reads memory from memory/ and .learnings/,
calls LLM to analyze patterns, writes discovered patterns to SOUL.md, USER.md etc.

- `--dry-run`: Preview mode, show results without writing
- `--force`: Force apply all patterns (ignore confidence threshold)

### review
Review mode: generate pattern analysis but don't write to files.
Outputs all pending patterns, supports JSON export.
Results saved to `.soulforge-{agent}/review/latest.json`.

### apply
Apply patterns from review output after confirmation. Run `soulforge.py review` first.
- `--confirm`: Confirm and apply all reviewed patterns

### backup
Backup management:
- `--create`: Create manual snapshot (distinct from auto-backups)

### status
Show current status overview. Memory entry counts, source stats, target file states, backup counts.

### diff
Show changes since last evolution run. Compare current files with latest backups.

### stats
Show evolution statistics. SoulForge update counts, file evolution counts, backup stats.

### inspect FILE
Inspect evolution patterns for a specific file (e.g., SOUL.md).
Shows current content and pending patterns.

### restore [FILE] [--backup N] [--preview] [--all]
Restore files from backup.
- No args: List all available backups
- `--backup N`: Restore backup #N (1=most recent)
- `--preview`: Preview changes without restoring
- `--all`: Restore all files with backups

### reset
Reset SoulForge state. Delete all backups and state files.
Note: Target files (SOUL.md etc.) are NOT modified.

### template [NAME]
Generate standard templates for target files.
- No args: List all available templates
- With name: Show specific template content

### changelog [--zh] [--full]
Show evolution changelog.
- `--zh`: Show Chinese version (default for zh-CN locale)
- `--full`: Show full changelog (no truncation)

### cron [--every MINUTES]
Show cron setup help.

### cron-set [--every N] [--show] [--remove]
Set cron schedule via OpenClaw.
- `--every N`: Run every N minutes
- `--show`: Show current schedule
- `--remove`: Remove cron job

### help
Show this help message.

---

## Global Options

- `--workspace PATH`: Workspace directory. Default: ~/.openclaw/workspace
- `--config PATH`: Path to config.json file.
- `--dry-run`: Preview mode, show results without writing.
- `--force`: Force apply all patterns (ignore confidence threshold).
- `--log-level LEVEL`: Log level: DEBUG, INFO, WARNING, ERROR

---

### clean --expired [--dry-run]
Remove expired SoulForge update blocks from target files.

- `--expired`: Required flag to confirm this operation
- `--dry-run`: Preview what would be removed without actually removing

Expired blocks are those with `**Expires**: YYYY-MM-DD` past the current date.

### rollback --auto
Show rollback automation info. Rollback is applied automatically during `run` — this command shows status.

### config --show | --set KEY=VALUE
Show or set configuration values. Values persist to `~/.soulforgerc.json`.

Examples:
```
soulforge.py config --show
soulforge.py config --set max_token_budget=8192
soulforge.py config --set notify_on_complete=true
soulforge.py config --set notify_chat_id=oc_xxx
soulforge.py config --set rollback_auto_enabled=false
```

## Confidence Levels

- High confidence (>0.8): Auto-apply
- Medium confidence (0.5-0.8): Needs review confirmation
- Low confidence (<0.5): Ignored, no pattern generated

---

## Incremental Analysis

First run analyzes all historical memory. Subsequent runs only analyze new entries
since last run, tracked via `.soulforge-{agent}/last_run` timestamp file.

---

For more info:
  https://github.com/relunctance/soul-force
