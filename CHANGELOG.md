# SoulForge Changelog

All notable changes to SoulForge are documented here.

## [2.2.0] - 2026-04-05

### Added

#### 1. Pattern Conflict Detection (P0)
- **schema.py**: `DiscoveredPattern` schema新增 `conflict_with: Optional[str]` 和 `has_conflict: bool` 字段
- **schema.py**: `ProposedUpdate` schema新增 `tags` 和 `conflict_with` 字段
- **analyzer.py**: `DiscoveredPattern` 新增 `tags` 和 `conflict_with` 字段，`to_markdown_block()` 输出冲突警告
- **analyzer.py**: `_detect_conflicts()` 方法检测冲突 pattern（相同 target、相反建议）
- **analyzer.py**: CLI review 时显示冲突警告（⚠️ CONFLICT）

#### 2. Natural Language Query Interface (P1)
- **analyzer.py**: `PatternAnalyzer.ask()` 方法 - 基于 patterns 和 memories 合成自然语言答案
- **soulforge.py**: 新增 `ask "question"` 命令，不写入文件，只输出查询结果
- 使用 LLM 从已有 patterns 和 memories 合成答案

#### 3. Richer Dry-run Preview (P1)
- **evolver.py**: `apply_updates()` 新增 `rich_diff` 参数
- **evolver.py**: `_generate_rich_diff()` 生成 unified diff 格式预览
- **soulforge.py**: `run --dry-run` 输出完整 diff-like 预览（`--- file / +++ file / @@`）
- 冲突 pattern 高亮显示

#### 4. Pattern Tags & Filtering (P1)
- **schema.py**: `DiscoveredPattern` 新增 `tags: List[str]` 字段
- **schema.py**: `ProposedUpdate` 新增 `tags` 字段
- **analyzer.py**: `DiscoveredPattern` 新增 `tags` 字段
- **analyzer.py**: `filter_by_tag()` 和 `filter_by_tags()` 方法
- **analyzer.py**: LLM prompt 指导生成 tags
- **soulforge.py**: CLI 支持 `--tag` 和 `--confidence` 过滤：
  - `soulforge.py review --tag preference`
  - `soulforge.py review --tag error --confidence high`

#### 5. Interactive Review Mode (P1)
- **soulforge.py**: 新增 `review --interactive` 命令
- 逐个 pattern 提问：`[1] Apply "pattern summary"? [y/n/a/q]`
- `y=yes, n=no, a=yes to all high-confidence, q=quit`
- 选择结果写入 `.soulforge-{agent}/review/interactive_{timestamp}.json`
- `apply --interactive` 读取该文件应用决策

#### 6. Real Token Counting (P2)
- **memory_reader.py**: `_get_tokenizer()` 和 `_tokenize_text()` 使用 tiktoken 真实 token 计数
- **memory_reader.py**: `tiktoken` 不可用时回退到 `chars/4` 估算
- **config.py**: 新增 `tokenizer_model` 配置项（默认 "cl100k_base"）
- **memory_reader.py**: `MemoryEntry.estimated_tokens()` 使用 tiktoken（真实）或 char-based（回退）
- CLI `status` 显示真实预估 token 消耗

#### 7. Changelog Visualization (P2)
- **evolver.py**: `_format_visual_changelog()` 输出 ASCII tree 格式
- **evolver.py**: `get_changelog(lang, visual=True)` 支持可视化模式
- **soulforge.py**: `changelog --visual` 输出 ASCII tree
- 格式：
  ```
  v2.1.0 (2026-04-05)
  ├── SOUL.md
  │   └── +2 patterns (communication)
  ├── USER.md
  │   └── +1 pattern (preference)
  └── IDENTITY.md
      └── no changes
  ```

### Changed
- **schema.py**: `DiscoveredPatternSchema` 新增 `tags`, `conflict_with`, `has_conflict` 字段
- **analyzer.py**: `to_markdown_block()` 新增标签和冲突标记输出
- **evolver.py**: `apply_updates()` 新增 `rich_diff` 参数控制 diff 输出
- **memory_reader.py**: `estimated_tokens()` 优先使用 tiktoken
- **soulforge.py**: `cmd_run` 在 dry-run 模式下使用 `rich_diff=True`
- **soulforge.py**: `cmd_review` 新增 `--tag`, `--confidence`, `--interactive` 参数
- **soulforge.py**: `cmd_changelog` 新增 `--visual` 参数
- **soulforge.py**: `cmd_apply` 新增 `--interactive` 参数

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
