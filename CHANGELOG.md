# SoulForge Changelog

All notable changes to SoulForge are documented here.

## [2.1.0] - 2026-04-05

### Added

#### 1. Rollback Automation (P0)
- **evolver.py**: Added `apply_with_rollback()` / `_apply_to_file_with_rollback()`
- Pre-write snapshot + post-write validation (file readable, block present, marker intact)
- On validation failure: auto-restore from snapshot + increment rollback counter
- CLI: `soulforge.py rollback --auto` command (placeholder/info)
- Results now include `rollbacks` count in output

#### 2. Token Budget Protection (P0)
- **config.py**: Added `max_token_budget` (default 4096)
- **memory_reader.py**: Added `estimated_tokens()`, `_apply_token_budget()`
- Strategy: newest-first, keep entries until budget exhausted
- `_skipped_count` and `_estimated_tokens` tracked in reader
- CLI `status` now shows: `Token budget: 4096 (used ~1234)`, skipped count
- `skipped_entries` and `estimated_tokens` added to `reader.summarize()`

#### 3. Schema Validation Layer (P1)
- **schema.py** (new): `ProposedUpdate` and `DiscoveredPatternSchema` via pydantic
- `validate_proposed_update()` and `validate_proposed_updates_batch()`
- **analyzer.py**: `_parse_with_validation()` wraps `_try_parse()` with retry logic
- Retry once on validation failure; persistent failure → save to `review/failed/failed_{timestamp}.txt`
- `review_failed_dir` added to config

#### 4. Pattern Expiry Mechanism (P1)
- **DiscoveredPattern**: Added `expires_at: Optional[str]` field (ISO date string)
- `to_markdown_block()` now outputs `**Expires**: YYYY-MM-DD` when set
- **analyzer.py**: LLM prompt updated to determine expiry dates
- Added `filter_expired()` method: drops patterns where `expires_at < now`
- **evolver.py**: Added `clean_expired(dry_run=True)` method
- CLI: `soulforge.py clean --expired [--dry-run]` command

#### 5. hawk-bridge Incremental Sync (P2)
- **config.py**: Added `hawk_sync_path` property
- **memory_reader.py**: `_last_hawk_sync` from `config.get_last_hawk_sync()`
- `_read_hawk_bridge()`: only fetches entries where `updated_at > last_hawk_sync`
- After read: `config.set_last_hawk_sync(timestamp)` called
- CLI `status` shows: `hawk-bridge last sync: {timestamp}`
- `last_hawk_sync` included in `reader.summarize()` output

#### 6. CLI Config File Support (P2)
- **config.py**: Full rewrite with explicit priority: CLI > env > config file > OpenClaw config > defaults
- Added `set(key, value)` and `to_file(path)` methods
- Added `review_failed_dir` and `hawk_sync_path` properties
- CLI: `soulforge.py config --show` and `soulforge.py config --set key=value`
- Config persisted to `~/.soulforgerc.json` on `--set`
- `rollback_auto_enabled` (default True), `notify_on_complete`, `notify_chat_id` new config keys

#### 7. Evolution Result Notifications (P2)
- **evolver.py**: Added `deliver_result(results)` method
- Attempts Feishu send via `openclaw message` tool
- Fallback: writes to `{state_dir}/last_notification.txt`
- CLI: `soulforge.py run --notify` enables notification
- Config keys: `notify_on_complete`, `notify_chat_id`
- Notification includes: applied count, files updated, rollback count, errors

### Changed
- **config.py**: Complete refactor with explicit `DEFAULT_CONFIG` dict
- **evolver.py**: `apply_updates()` now delegates to `_apply_to_file_with_rollback()`
- **analyzer.py**: `DiscoveredPattern` now has `expires_at` field
- **memory_reader.py**: Added token estimation and budget truncation
- **memory_reader.py**: hawk-bridge now uses incremental sync via `last_hawk_sync`
- CLI `status` now shows token budget usage and hawk-bridge sync time
- CLI `run` shows estimated tokens before analysis

### Fixed
- **analyzer.py**: Schema validation retry loop — now correctly retries once on validation failure
- **schema.py**: `ProposedUpdate` field order and validators for `insertion_point` and `update_type`

## [2.0.0] - 2026-04-05

### Added

#### 1. LLM Call via OpenClaw exec (P0)
- **analyzer.py**: Replaced `urllib.request` direct API calls with OpenClaw's exec tool
- Now reads API key, base_url, and model from OpenClaw config instead of managing its own
- Compatible with both MiniMax and OpenAI-compatible API formats

#### 2. Incremental Analysis (P0)
- **memory_reader.py**: Added `last_run_timestamp` mechanism
- **config.py**: Added `get_last_run_timestamp()` and `set_last_run_timestamp()` methods
- After each run, stores ISO timestamp in `.soulforge-{agent}/last_run`
- Subsequent runs only analyze entries newer than the stored timestamp
- First run (no `last_run` file) analyzes all entries for backward compatibility

#### 3. Smart Insertion Points (P1)
- **DiscoveredPattern**: Added `insertion_point` field with values:
  - `"append"` (default): Add to end of file
  - `"section:{title}"`: Insert under `## {title}` section
  - `"top"`: Insert at beginning of file
- **SoulEvolver**: Updated `_insert_content()` to handle all three modes
- Added `_insert_after_section()` for section-based insertion
- Pattern blocks now include `**Insertion**: {insertion_point}` in output

#### 4. Review Mode (P1)
- **soulforge.py**: New `review` command generates patterns without writing files
- Review output saved to `.soulforge-{agent}/review/latest.json`
- Organized by confidence level (high/medium/low) in output
- **soulforge.py**: New `apply --confirm` command applies patterns from review
- Added `generate_review()` and `apply_from_review()` to SoulEvolver
- Review results include JSON export with all pattern details

#### 5. Confidence-Based Filtering (P2)
- **PatternAnalyzer**: Added confidence thresholds:
  - High (>0.8): `auto_apply=True`, default applied
  - Medium (0.5-0.8): `needs_review=True`, requires user confirmation
  - Low (<0.5): Ignored, no pattern generated
- `run --force` flag forces application of all patterns regardless of confidence
- Added `filter_auto_apply()`, `filter_needs_review()`, `separate_by_confidence()`
- `DiscoveredPattern` now has `auto_apply` and `needs_review` fields

#### 6. Enhanced Backup Strategy (P2)
- **SoulEvolver**: Important files (SOUL.md, IDENTITY.md) retain 20 backups
- Normal files retain 10 backups (configurable via `backup_retention_important`/`backup_retention_normal`)
- Backup naming: `{filename}.{timestamp}.{type}.bak` where type=`auto` or `manual`
- **soulforge.py**: New `backup --create` command for manual snapshots
- Added `create_manual_backup()` method to SoulEvolver
- Fixed timestamp resolution bug (microsecond precision)

#### 7. Help Text Externalized (P2)
- Help texts moved from `soulforge.py` to `references/help-zh.md` and `references/help-en.md`
- New `help` command in CLI displays help from external files
- `soulforge.py --help-cn` and `soulforge.py help --zh` for Chinese help

### Changed

- **SoulEvolver._create_backup()**: Now uses configurable backup retention (20 for important, 10 for normal)
- **analyzer.py**: Pattern parsing now extracts and normalizes `insertion_point` from LLM response
- **SoulForgeConfig**: Agent suffix derived from workspace path for proper isolation
- **MemoryReader**: Added `since_timestamp` parameter for incremental reads
- **config.py**: Added `agent_suffix`, `review_dir`, `last_run_path` properties
- **DiscoveredPattern**: Added `insertion_point`, `auto_apply`, `needs_review` fields with `__post_init__`

### Fixed

- Backup timestamp collision: Now uses microsecond precision (`%Y%m%d_%H%M%S_%f`)
- Section insertion: Correctly inserts after section content, before next section
- Duplicate filtering: Properly checks for similar patterns before applying

### Test Coverage

- Added 28 unit tests covering:
  - Config: agent suffix, backup retention, last_run timestamp
  - MemoryReader: incremental reading
  - Analyzer: confidence levels, insertion_point, pattern serialization
  - Evolver: smart insertion, backup retention, review generation, manual backups

---

## [1.0.0] - 2026-04-04

### Added

- Initial SoulForge release
- Multi-source memory reading (memory/*.md, .learnings/, hawk-bridge)
- LLM-powered pattern analysis with duplicate detection
- Safe file evolution with backup and changelog
- Multi-agent isolation via per-workspace state directories
- CLI with run, status, diff, stats, inspect, restore, reset, template, changelog commands
- Cron scheduling support
