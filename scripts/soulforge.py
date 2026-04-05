#!/usr/bin/env python3
"""
SoulForge CLI - AI Agent Memory Evolution System

Usage:
    python3 soulforge.py run [--workspace PATH] [--dry-run] [--force] [--notify]
    python3 soulforge.py review [--workspace PATH]
    python3 soulforge.py apply --confirm [--workspace PATH]
    python3 soulforge.py backup --create [--workspace PATH]
    python3 soulforge.py status [--workspace PATH]
    python3 soulforge.py diff [--workspace PATH]
    python3 soulforge.py stats [--workspace PATH]
    python3 soulforge.py inspect FILE [--workspace PATH]
    python3 soulforge.py restore [FILE] [--backup PATH] [--preview] [--all]
    python3 soulforge.py reset [--workspace PATH]
    python3 soulforge.py template [--workspace PATH]
    python3 soulforge.py changelog [--zh] [--full]
    python3 soulforge.py cron [--every MINUTES]
    python3 soulforge.py clean --expired [--workspace PATH] [--dry-run]
    python3 soulforge.py rollback --auto [--workspace PATH]
    python3 soulforge.py config --show [--workspace PATH]
    python3 soulforge.py config --set KEY=VALUE [--workspace PATH]
    python3 soulforge.py help

Examples:
    python3 soulforge.py run
    python3 soulforge.py run --dry-run
    python3 soulforge.py run --force --notify
    python3 soulforge.py review
    python3 soulforge.py apply --confirm
    python3 soulforge.py backup --create
    python3 soulforge.py status
    python3 soulforge.py clean --expired
    python3 soulforge.py rollback --auto
    python3 soulforge.py config --show
    python3 soulforge.py config --set max_token_budget=8192
    python3 soulforge.py help
"""

import argparse
import logging
import sys
import os
import json
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from soulforge import SoulForgeConfig, MemoryReader, PatternAnalyzer, SoulEvolver


def _load_help_text(lang: str = "en") -> str:
    """Load help text from references/ directory."""
    skill_dir = Path(__file__).parent.parent
    help_path = skill_dir / "references" / f"help-{lang}.md"
    if help_path.exists():
        return help_path.read_text(encoding="utf-8")
    return f"Help file not found: {help_path}"


def setup_logging(level: str = "INFO") -> None:
    """Configure logging for the CLI."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def cmd_run(args) -> int:
    """
    Run the evolution process - the main command.
    """
    config = SoulForgeConfig(
        config_path=args.config,
        overrides={
            "dry_run": args.dry_run,
            "workspace": args.workspace,
            "notify_on_complete": args.notify,
        }
    )
    setup_logging(config.log_level)

    logger = logging.getLogger("soulforge.run")
    logger.info(f"SoulForge starting (workspace: {config.workspace})")

    last_run = config.get_last_run_timestamp()
    if last_run:
        print(f"📊 Incremental mode: analyzing entries since {last_run}")
    else:
        print("📊 Full analysis mode: no previous run found")

    # Token budget info
    print(f"📊 Token budget: {config.max_token_budget} max")

    # Step 1: Read memory sources
    print("📖 Reading memory sources...")
    reader = MemoryReader(config.workspace, config)
    entries = reader.read_all()

    if not entries:
        print("⚠️  No memory entries found. Nothing to analyze.")
        return 0

    summary = reader.summarize()
    print(f"   ✓ Read {summary['total_entries']} entries from {len(summary['sources'])} sources")
    print(f"   ✓ Estimated tokens: ~{summary['estimated_tokens']} / {summary['max_token_budget']}")
    if summary.get("skipped_entries", 0) > 0:
        print(f"   ⚠️  Skipped {summary['skipped_entries']} entries (over token budget)")
    if summary.get("last_hawk_sync"):
        print(f"   ✓ hawk-bridge last sync: {summary['last_hawk_sync']}")

    # Step 2: Read existing content
    print("📄 Checking existing file content...")
    existing_content = {}
    for target in config.target_files:
        target_path = Path(config.workspace) / target
        if target_path.exists():
            existing_content[target] = target_path.read_text(encoding="utf-8")

    # Step 3: Analyze patterns
    print("🔍 Analyzing patterns with configured LLM...")
    analyzer = PatternAnalyzer(config, force_apply=args.force)
    patterns = analyzer.analyze(entries, existing_content)

    if not patterns:
        print("   ⚠️  No significant patterns found.")
        return 0

    # Filter by threshold
    filtered = analyzer.filter_by_threshold(patterns)
    # Remove expired patterns
    filtered = analyzer.filter_expired(filtered)
    print(f"   ✓ Found {len(filtered)} patterns above threshold")

    by_conf = analyzer.separate_by_confidence(filtered)
    if by_conf["high"]:
        print(f"   ✓ High confidence (auto-apply): {len(by_conf['high'])}")
    if by_conf["medium"]:
        print(f"   ⚠️  Medium confidence (needs review): {len(by_conf['medium'])}")
    if by_conf["low"]:
        print(f"   - Low confidence (ignored): {len(by_conf['low'])}")

    auto_patterns = filtered if args.force else analyzer.filter_auto_apply(filtered)
    review_patterns = analyzer.filter_needs_review(filtered)

    if not auto_patterns and not args.force:
        print("\n⚠️  No high-confidence patterns to auto-apply.")
        print("   Run 'soulforge.py review' to see medium-confidence patterns.")
        print("   Or use 'soulforge.py run --force' to apply all patterns.")
        return 0

    # Step 4: Apply updates with rollback
    print("✏️  Applying updates (with rollback protection)...")
    evolver = SoulEvolver(config.workspace, config)
    results = evolver.apply_updates(auto_patterns)

    if results["dry_run"]:
        print(f"   ⚠️  DRY RUN - no files were written")
        print("")
        print("   Would update:")
        for filename in results["files_updated"]:
            print(f"     - {filename}")
    else:
        print(f"   ✓ Updated {len(results['files_updated'])} files")
        print(f"   ✓ Applied {results['patterns_applied']} patterns")
        if results.get("rollbacks", 0) > 0:
            print(f"   ⚠️  Rollbacks performed: {results['rollbacks']}")

    if review_patterns:
        print(f"\n   ⚠️  {len(review_patterns)} medium-confidence patterns need review.")

    if results["errors"]:
        print(f"   ⚠️  Errors encountered:")
        for err in results["errors"]:
            for file, error in err.items():
                print(f"     - {file}: {error}")

    # Send notification
    if args.notify and not results["dry_run"]:
        print("\n📬 Sending notification...")
        evolver.deliver_result(results)

    if results.get("changes"):
        print("")
        print(evolver.summarize_changes())

    print("")
    if results["dry_run"]:
        print("🔍 DRY RUN complete. Run without --dry-run to write changes.")
    else:
        print("✅ SoulForge evolution complete!")

    return 0


def cmd_review(args) -> int:
    """Review mode: generate pattern analysis without writing files."""
    config = SoulForgeConfig(overrides={"workspace": args.workspace})
    setup_logging(config.log_level)

    print(f"SoulForge Review (workspace: {config.workspace})")
    print("=" * 50)
    print("Generating patterns without writing to files...")
    print("")

    reader = MemoryReader(config.workspace, config)
    entries = reader.read_all()

    if not entries:
        print("⚠️  No memory entries found.")
        return 0

    summary = reader.summarize()
    print(f"   ✓ Read {summary['total_entries']} entries")
    print(f"   ✓ Tokens: ~{summary['estimated_tokens']} / {summary['max_token_budget']}")

    existing_content = {}
    for target in config.target_files:
        target_path = Path(config.workspace) / target
        if target_path.exists():
            existing_content[target] = target_path.read_text(encoding="utf-8")

    print("🔍 Analyzing patterns...")
    analyzer = PatternAnalyzer(config, force_apply=True)
    patterns = analyzer.analyze(entries, existing_content)

    if not patterns:
        print("   ⚠️  No patterns found.")
        return 0

    filtered = analyzer.filter_by_threshold(patterns)
    filtered = analyzer.filter_expired(filtered)

    by_conf = analyzer.separate_by_confidence(filtered)

    print(f"   ✓ Found {len(filtered)} patterns:")
    print(f"     - High confidence (>0.8): {len(by_conf['high'])}")
    print(f"     - Medium confidence (0.5-0.8): {len(by_conf['medium'])}")
    print(f"     - Low confidence (<0.5): {len(by_conf['low'])}")

    evolver = SoulEvolver(config.workspace, config)
    review_results = evolver.generate_review(filtered)

    print("")
    print(f"📄 Review output saved to:")
    print(f"   {review_results['review_file']}")

    if by_conf["high"]:
        print("\n🔵 HIGH CONFIDENCE PATTERNS (will auto-apply):")
        print("-" * 40)
        for p in by_conf["high"]:
            print(f"  [{p.target_file}] {p.summary}")
            print(f"    Confidence: {p.confidence:.1f}, Evidence: {p.evidence_count}")
            print(f"    Insertion: {p.insertion_point}")
            if p.expires_at:
                print(f"    Expires: {p.expires_at}")
            print(f"    Content: {p.content[:100]}...")
            print("")

    if by_conf["medium"]:
        print("\n🟡 MEDIUM CONFIDENCE PATTERNS (need review):")
        print("-" * 40)
        for p in by_conf["medium"]:
            print(f"  [{p.target_file}] {p.summary}")
            print(f"    Confidence: {p.confidence:.1f}, Evidence: {p.evidence_count}")
            print(f"    Insertion: {p.insertion_point}")
            print(f"    Content: {p.content[:100]}...")
            print("")

    if by_conf["low"]:
        print("\n🔴 LOW CONFIDENCE PATTERNS (ignored):")
        print("-" * 40)
        for p in by_conf["low"]:
            print(f"  [{p.target_file}] {p.summary}")
            print(f"    Confidence: {p.confidence:.1f}, Evidence: {p.evidence_count}")

    print("\nTo apply high-confidence patterns, run:")
    print("  soulforge.py run")
    print("")
    print("To apply ALL patterns (including medium-confidence):")
    print("  soulforge.py run --force")
    print("")
    print("To apply from review after confirmation:")
    print("  soulforge.py apply --confirm")

    return 0


def cmd_apply(args) -> int:
    """Apply patterns from the latest review output."""
    config = SoulForgeConfig(overrides={"workspace": args.workspace})
    setup_logging(config.log_level)

    print(f"SoulForge Apply (workspace: {config.workspace})")
    print("=" * 50)

    evolver = SoulEvolver(config.workspace, config)

    if not args.confirm:
        result = evolver.apply_from_review(confirm=False)
        if "error" in result:
            print(f"❌ {result['error']}")
            return 1

        print(f"Patterns from latest review:")
        print(f"  Total: {result['total_patterns']}")
        print("")
        for p_dict in result.get("patterns", []):
            print(f"  [{p_dict['target_file']}] {p_dict['summary']}")
            print(f"    Confidence: {p_dict['confidence']:.1f}, Insertion: {p_dict['insertion_point']}")
        print("")
        print("Run with --confirm to actually apply these patterns.")
        return 0

    print("⚠️  Applying ALL patterns from latest review (including medium-confidence).")
    print("")
    confirm = input("Type 'yes' to confirm: ")
    if confirm.lower() != "yes":
        print("Cancelled.")
        return 0

    result = evolver.apply_from_review(confirm=True)

    if "error" in result:
        print(f"❌ {result['error']}")
        return 1

    print(f"   ✓ Updated {len(result.get('files_updated', []))} files")
    print(f"   ✓ Applied {result.get('patterns_applied', 0)} patterns")

    if result.get("errors"):
        print(f"   ⚠️  Errors:")
        for err in result.get("errors", []):
            print(f"     - {err}")

    return 0


def cmd_backup_create(args) -> int:
    """Create a manual backup snapshot of all target files."""
    config = SoulForgeConfig(overrides={"workspace": args.workspace})
    setup_logging(config.log_level)

    print(f"SoulForge Backup (workspace: {config.workspace})")
    print("=" * 50)
    print("Creating manual snapshot...")
    print("")

    evolver = SoulEvolver(config.workspace, config)
    result = evolver.create_manual_backup()

    if result["backed_up"]:
        print(f"✅ Backed up {len(result['backed_up'])} files:")
        for f in result["backed_up"]:
            print(f"   - {f}")
    if result["skipped"]:
        print(f"   Skipped {len(result['skipped'])} files (not found):")
        for f in result["skipped"]:
            print(f"   - {f}")
    if result["errors"]:
        print(f"   Errors:")
        for err in result["errors"]:
            for f, e in err.items():
                print(f"   - {f}: {e}")

    return 0


def cmd_status(args) -> int:
    """Show current status - memory overview and target file states."""
    config = SoulForgeConfig(overrides={"workspace": args.workspace})
    setup_logging(config.log_level)

    print(f"SoulForge Status (workspace: {config.workspace})")
    print("=" * 50)

    reader = MemoryReader(config.workspace, config)
    entries = reader.read_all()
    summary = reader.summarize()

    print(f"\n📊 Memory Overview:")
    print(f"   Total entries: {summary['total_entries']}")
    print(f"   Sources: {len(summary['sources'])}")
    print(f"   Token budget: {summary['max_token_budget']} (used ~{summary['estimated_tokens']})")
    if summary.get("skipped_entries", 0) > 0:
        print(f"   Skipped (over budget): {summary['skipped_entries']}")
    if summary.get("is_incremental"):
        print(f"   Last run: {summary.get('last_run')}")
    else:
        print(f"   Mode: Full analysis (no previous run)")

    if summary.get("last_hawk_sync"):
        print(f"   hawk-bridge last sync: {summary['last_hawk_sync']}")

    print(f"\n   By source type:")
    for source_type, count in summary.get("by_source_type", {}).items():
        print(f"     - {source_type}: {count}")

    print(f"\n   By category:")
    for category, count in summary.get("by_category", {}).items():
        print(f"     - {category}: {count}")

    print(f"\n📝 Target Files:")
    for target in config.target_files:
        target_path = Path(config.workspace) / target
        if target_path.exists():
            stat = target_path.stat()
            size = stat.st_size
            modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
            print(f"   ✓ {target} ({size} bytes, modified {modified})")
        else:
            print(f"   - {target} (not created)")

    backup_dir = Path(config.backup_dir)
    if backup_dir.exists():
        backups = list(backup_dir.glob("*.bak"))
        print(f"\n💾 Backups: {len(backups)} files in {backup_dir}")

        backup_counts = {}
        for b in backups:
            name = ".".join(b.name.split(".")[:-2])
            backup_counts[name] = backup_counts.get(name, 0) + 1
        for name, count in sorted(backup_counts.items()):
            retention = config.get_backup_retention(name)
            status = "✓" if count >= retention else "⚠️"
            print(f"   {status} {name}: {count} backups (keeps {retention})")

    last_run = config.get_last_run_timestamp()
    if last_run:
        print(f"\n⏱️  Last run: {last_run}")

    # Config info
    print(f"\n⚙️  Config:")
    print(f"   Auto-rollback: {config.rollback_auto_enabled}")
    print(f"   Notifications: {config.notify_on_complete}")
    if config.notify_chat_id:
        print(f"   Notify chat: {config.notify_chat_id}")

    return 0


def cmd_diff(args) -> int:
    """Show what changed since last evolution run."""
    config = SoulForgeConfig(overrides={"workspace": args.workspace})
    setup_logging(config.log_level)

    print(f"SoulForge Diff (workspace: {config.workspace})")
    print("=" * 50)

    evolver = SoulEvolver(config.workspace, config)

    for target in config.target_files:
        backups = evolver.get_backup_list(target)
        if not backups:
            print(f"\n📄 {target}: No backups found")
            continue

        latest_backup = backups[0]["path"]
        current_path = Path(config.workspace) / target

        print(f"\n📄 {target}:")
        print(f"   Current: {current_path}")
        print(f"   Latest backup: {backups[0]['timestamp']} ({backups[0].get('type', 'auto')})")

        if current_path.exists():
            current_content = current_path.read_text(encoding="utf-8")
            backup_content = Path(latest_backup).read_text(encoding="utf-8")

            if current_content == backup_content:
                print(f"   Status: No changes since backup")
            else:
                print(f"   Status: ⚠️  Changed (use 'restore' to revert)")
        else:
            print(f"   Status: File does not exist")

    return 0


def cmd_stats(args) -> int:
    """Show evolution statistics."""
    config = SoulForgeConfig(overrides={"workspace": args.workspace})
    setup_logging(config.log_level)

    print(f"SoulForge Stats (workspace: {config.workspace})")
    print("=" * 50)

    reader = MemoryReader(config.workspace, config)
    entries = reader.read_all()
    summary = reader.summarize()

    update_counts = {}
    for target in config.target_files:
        target_path = Path(config.workspace) / target
        if target_path.exists():
            content = target_path.read_text(encoding="utf-8")
            count = content.count("<!-- SoulForge Update")
            update_counts[target] = count

    print(f"\n📊 Evolution Statistics:")
    print(f"   Total memory entries: {summary['total_entries']}")
    print(f"   Token budget: {summary['max_token_budget']} (~{summary['estimated_tokens']} used)")
    print(f"   SoulForge updates per file:")
    for target, count in update_counts.items():
        print(f"     - {target}: {count} updates")

    backup_dir = Path(config.backup_dir)
    if backup_dir.exists():
        backups = list(backup_dir.glob("*.bak"))
        print(f"\n💾 Total backups: {len(backups)}")

        auto_count = len([b for b in backups if ".auto." in b.name])
        manual_count = len([b for b in backups if ".manual." in b.name])
        print(f"     - Auto: {auto_count}")
        print(f"     - Manual: {manual_count}")

    last_run = config.get_last_run_timestamp()
    if last_run:
        print(f"\n⏱️  Last run: {last_run}")

    last_hawk = config.get_last_hawk_sync()
    if last_hawk:
        print(f"   hawk-bridge sync: {last_hawk}")

    return 0


def cmd_inspect(args) -> int:
    """Inspect what would be evolved for a specific file."""
    config = SoulForgeConfig(overrides={"workspace": args.workspace})
    setup_logging(config.log_level)

    target_file = args.file
    if not target_file.endswith(".md"):
        target_file += ".md"

    print(f"SoulForge Inspect: {target_file} (workspace: {config.workspace})")
    print("=" * 50)

    target_path = Path(config.workspace) / target_file
    if target_path.exists():
        content = target_path.read_text(encoding="utf-8")
        print(f"\n📄 Current content ({len(content)} chars):")
        print("-" * 40)
        print(content[:1000])
        if len(content) > 1000:
            print("...(truncated)")
    else:
        print(f"\n📄 File does not exist yet.")

    print(f"\n🔍 Analyzing patterns for {target_file}...")
    reader = MemoryReader(config.workspace, config)
    entries = reader.read_all()

    analyzer = PatternAnalyzer(config, force_apply=True)
    existing_content = {target_file: target_path.read_text()} if target_path.exists() else {}
    patterns = analyzer.analyze(entries, existing_content)

    file_patterns = [p for p in patterns if p.target_file == target_file]
    filtered = analyzer.filter_by_threshold(file_patterns)
    filtered = analyzer.filter_expired(filtered)

    if filtered:
        print(f"\n   ✓ Found {len(filtered)} patterns for {target_file}:")
        by_conf = analyzer.separate_by_confidence(filtered)
        if by_conf["high"]:
            print(f"\n   🔵 High confidence:")
            for p in by_conf["high"]:
                print(f"     - {p.summary}")
                print(f"       Confidence: {p.confidence}, Evidence: {p.evidence_count}")
                print(f"       Insertion: {p.insertion_point}")
                if p.expires_at:
                    print(f"       Expires: {p.expires_at}")
        if by_conf["medium"]:
            print(f"\n   🟡 Medium confidence:")
            for p in by_conf["medium"]:
                print(f"     - {p.summary}")
                print(f"       Confidence: {p.confidence}, Evidence: {p.evidence_count}")
                print(f"       Insertion: {p.insertion_point}")
                if p.expires_at:
                    print(f"       Expires: {p.expires_at}")
    else:
        print(f"\n   ⚠️  No patterns found for {target_file}")

    return 0


def cmd_restore(args) -> int:
    """Restore files from backup."""
    config = SoulForgeConfig(overrides={"workspace": args.workspace})
    setup_logging(config.log_level)

    evolver = SoulEvolver(config.workspace, config)

    if args.restore_all:
        return _restore_all(evolver, config, args)

    target_file = args.file
    if not target_file.endswith(".md"):
        target_file += ".md"

    if not args.backup and not args.preview:
        print(f"Available backups for {target_file}:")
        print("=" * 50)
        backups = evolver.get_backup_list(target_file)
        if not backups:
            print("No backups found")
            return 1
        for i, b in enumerate(backups[:10]):
            print(f"  [{i+1}] {b['path']}")
            print(f"      {b['timestamp']} ({b.get('type', 'auto')})")
        if len(backups) > 10:
            print(f"\n  ... and {len(backups) - 10} more")
        print("")
        print(f"Usage:")
        print(f"  soulforge.py restore {args.file} --preview")
        print(f"  soulforge.py restore {args.file} --backup 1")
        return 0

    backup_path = args.backup
    backups = evolver.get_backup_list(target_file)

    if backup_path is not None:
        if str(backup_path).isdigit():
            idx = int(backup_path) - 1
            if idx < 0 or idx >= len(backups):
                print(f"Invalid backup index: {backup_path}")
                return 1
            backup_path = backups[idx]["path"]
    elif backups:
        backup_path = backups[0]["path"]
    else:
        print(f"No backups found for {target_file}")
        return 1

    if args.preview:
        return _preview_restore(target_file, backup_path, config)

    print(f"SoulForge Restore: {target_file}")
    print("=" * 50)
    print(f"Restore from: {backup_path}")
    print("")
    confirm = input("Type 'yes' to confirm: ")
    if confirm.lower() != "yes":
        print("Cancelled.")
        return 0

    success = evolver.restore_from_backup(target_file, backup_path)
    if success:
        print(f"✅ Restored {target_file}")
        return 0
    else:
        print(f"❌ Restore failed")
        return 1


def _preview_restore(target_file: str, backup_path: str, config) -> int:
    """Show a preview of what will change when restoring."""
    print(f"Preview: Restore {target_file}")
    print("=" * 50)
    print(f"Backup: {backup_path}")

    current_path = Path(config.workspace) / target_file

    print("\nCurrent content:")
    print("-" * 40)
    if current_path.exists():
        current = current_path.read_text(encoding="utf-8")
        print(f"  {len(current)} chars")
        print(current[:500])
        if len(current) > 500:
            print("  ...(truncated)")
    else:
        print("  (file does not exist)")

    print("\nBackup content:")
    print("-" * 40)
    backup = Path(backup_path).read_text(encoding="utf-8")
    print(f"  {len(backup)} chars")
    print(backup[:500])
    if len(backup) > 500:
        print("  ...(truncated)")

    return 0


def _restore_all(evolver, config, args) -> int:
    """Restore all files from their latest backups."""
    print(f"SoulForge Restore All (workspace: {config.workspace})")
    print("=" * 50)

    all_backups = {}
    for target in config.target_files:
        backups = evolver.get_backup_list(target)
        if backups:
            all_backups[target] = backups[0]

    if not all_backups:
        print("No backups found for any file")
        return 1

    print(f"Files with backups: {len(all_backups)}")
    for target, backup_info in all_backups.items():
        print(f"  - {target}: {backup_info['path']}")

    print("")

    if args.preview:
        for target, backup_info in all_backups.items():
            print(f"\n--- {target} ---")
            current_path = Path(config.workspace) / target
            if current_path.exists():
                current = current_path.read_text(encoding="utf-8")
                backup = Path(backup_info["path"]).read_text(encoding="utf-8")
                if current == backup:
                    print(f"  No change (identical)")
                else:
                    print(f"  Current: {len(current)} chars")
                    print(f"  Backup:  {len(backup)} chars")
            else:
                print(f"  File does not exist, will be created")
        return 0

    print("⚠️  This will REPLACE current content of ALL listed files.")
    print("")

    confirm = input("Type 'yes' to restore ALL files: ")
    if confirm.lower() != "yes":
        print("Cancelled.")
        return 0

    restored = []
    failed = []
    for target, backup_info in all_backups.items():
        success = evolver.restore_from_backup(target, backup_info["path"])
        if success:
            restored.append(target)
        else:
            failed.append(target)

    print("")
    if restored:
        print(f"✅ Restored {len(restored)} files:")
        for t in restored:
            print(f"  - {t}")
    if failed:
        print(f"❌ Failed to restore {len(failed)} files:")
        for t in failed:
            print(f"  - {t}")
        return 1

    return 0


def cmd_reset(args) -> int:
    """Reset all SoulForge state for this workspace."""
    config = SoulForgeConfig(overrides={"workspace": args.workspace})
    setup_logging(config.log_level)

    print(f"⚠️  SoulForge Reset (workspace: {config.workspace})")
    print("=" * 50)
    print("This will remove all SoulForge backups and state files.")
    print("Target files (SOUL.md, etc.) will NOT be modified.")
    print("")

    confirm = input("Type 'yes' to confirm: ")
    if confirm.lower() != "yes":
        print("Cancelled.")
        return 0

    backup_dir = Path(config.backup_dir)
    if backup_dir.exists():
        import shutil
        shutil.rmtree(backup_dir)
        print(f"✅ Removed {backup_dir}")

    state_dir = Path(config.state_dir)
    if state_dir.exists():
        import shutil
        shutil.rmtree(state_dir)
        print(f"✅ Removed {state_dir}")

    print("\n✅ Reset complete. Run 'soulforge.py run' to start fresh.")
    return 0


def cmd_template(args) -> int:
    """Generate standard templates for target files."""
    templates = {
        "SOUL.md": """# SOUL.md - Who I Am

_Update this file to reflect your current identity. SoulForge will auto-evolve it._

## Core Identity

Your name, role, and purpose here.

## Communication Style

How you communicate with your human.

## Principles

Key principles that guide your behavior.

## Boundaries

What you will and won't do.

---
_Last updated: {date}_
""",
        "USER.md": """# USER.md - About Your Human

_Track what you know about your human. SoulForge will auto-update this._

## Basic Info

Name, timezone, preferences.

## Communication Preferences

How they like to communicate.

## Projects

Active projects and context.

## Notes

Important things to remember about this user.

---
_Last updated: {date}_
""",
        "IDENTITY.md": """# IDENTITY.md

_Your role definition. SoulForge will auto-evolve this._

## Role

Your position and responsibilities.

## Team

Team structure and who you work with.

## Scope

What you're responsible for.

---
_Last updated: {date}_
""",
    }

    print("SoulForge Templates")
    print("=" * 50)
    print("\nAvailable templates:")
    for name in templates.keys():
        print(f"  - {name}")

    if args.template:
        if args.template in templates:
            date = datetime.now().strftime("%Y-%m-%d")
            content = templates[args.template].format(date=date)
            print(f"\n{args.template}:\n")
            print(content)
        else:
            print(f"Unknown template: {args.template}")
            return 1

    return 0


def cmd_changelog(args) -> int:
    """Show the evolution changelog."""
    config = SoulForgeConfig(overrides={"workspace": args.workspace})
    setup_logging(config.log_level)

    lang = "zh-CN" if args.zh else "en"
    lang_name = "中文" if lang == "zh-CN" else "English"

    print(f"SoulForge Changelog ({lang_name}) (workspace: {config.workspace})")
    print("=" * 50)

    evolver = SoulEvolver(config.workspace, config)
    content = evolver.get_changelog(lang)

    if not content:
        print("No changelog found yet.")
        print("Run 'soulforge.py run' first to create evolution history.")
        return 1

    preview_lines = content.split("\n")[:50]
    print("\n".join(preview_lines))

    if len(content.split("\n")) > 50:
        print("\n... (truncated, use --full to see all)")

    print(f"\n📄 Full changelog: {Path(config.state_dir) / ('CHANGELOG.' + lang + '.md')}")
    return 0


def cmd_cron(args) -> int:
    """Show how to set up cron scheduling."""
    if args.every:
        print(f"To schedule SoulForge every {args.every} minutes, add this to your crontab:")
        print("")
        print(f"*/{args.every} * * * * cd {os.getcwd()} && python3 {__file__} run >> /var/log/soulforge.log 2>&1")
        print("")
        print("Or with OpenClaw cron:")
        print(f"  openclaw cron add --name soulforce-evolve --every {args.every}m \\")
        print(f"    --message 'exec python3 {__file__} run'")
    return 0


def cmd_cron_set(args) -> int:
    """Set or update the SoulForge cron schedule via OpenClaw."""
    config = SoulForgeConfig(overrides={"workspace": args.workspace})

    script_path = str(Path(__file__).resolve())
    workspace = os.path.expanduser(args.workspace)

    if args.remove:
        print("SoulForge Cron: Remove")
        print("=" * 50)
        confirm = input("Remove the SoulForge cron job? Type 'yes': ")
        if confirm.lower() != "yes":
            print("Cancelled.")
            return 0
        try:
            import subprocess
            result = subprocess.run(
                ["openclaw", "cron", "remove", "--name", "soulforce-evolve"],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                print("✅ Cron job removed")
                return 0
            else:
                print(f"❌ Failed: {result.stderr}")
                return 1
        except FileNotFoundError:
            print("❌ openclaw command not found.")
            return 1

    elif args.show:
        print("SoulForge Cron: Current Schedule")
        print("=" * 50)
        try:
            import subprocess
            result = subprocess.run(
                ["openclaw", "cron", "list", "--name", "soulforce-evolve"],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                print(result.stdout)
            else:
                print("No SoulForge cron job found.")
                print("Use: soulforge.py cron-set --every 120")
        except FileNotFoundError:
            print("❌ openclaw command not found.")
        return 0

    elif args.every is not None:
        minutes = args.every
        print("SoulForge Cron: Set Schedule")
        print("=" * 50)
        print(f"Interval: every {minutes} minutes")
        print(f"Workspace: {workspace}")

        confirm = input("Apply this schedule? Type 'yes': ")
        if confirm.lower() != "yes":
            print("Cancelled.")
            return 0

        try:
            import subprocess
            subprocess.run(
                ["openclaw", "cron", "remove", "--name", "soulforce-evolve"],
                capture_output=True
            )
            result = subprocess.run(
                [
                    "openclaw", "cron", "add",
                    "--name", "soulforce-evolve",
                    "--every", f"{minutes}m",
                    "--message", f"exec python3 {script_path} run --workspace {workspace}"
                ],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                print(f"✅ Cron job set: every {minutes} minutes")
                return 0
            else:
                print(f"❌ Failed: {result.stderr}")
                return 1
        except FileNotFoundError:
            print("❌ openclaw command not found.")
            return 1

    else:
        print("SoulForge Cron: Configuration")
        print("=" * 50)
        print("Usage:")
        print(f"  soulforge.py cron-set --every 120")
        print(f"  soulforge.py cron-set --show")
        print(f"  soulforge.py cron-set --remove")
        return 0


def cmd_clean(args) -> int:
    """Clean expired SoulForge update blocks from target files."""
    config = SoulForgeConfig(overrides={"workspace": args.workspace})
    setup_logging(config.log_level)

    dry_run = args.dry_run
    mode = "DRY RUN" if dry_run else "LIVE"

    print(f"SoulForge Clean Expired Blocks ({mode}) (workspace: {config.workspace})")
    print("=" * 50)

    evolver = SoulEvolver(config.workspace, config)
    results = evolver.clean_expired(dry_run=dry_run)

    print(f"\n📊 Results:")
    print(f"   Files scanned: {results['files_scanned']}")
    print(f"   Blocks removed: {results['blocks_removed']}")
    print(f"   Blocks marked stale: {results['blocks_marked_stale']}")

    if results['files_modified']:
        print(f"\n📝 Files modified:")
        for f in results['files_modified']:
            print(f"   - {f}")

    if results['errors']:
        print(f"\n❌ Errors:")
        for err in results['errors']:
            for f, e in err.items():
                print(f"   - {f}: {e}")

    if results['blocks_removed'] == 0 and results['blocks_marked_stale'] == 0:
        print("\n✅ No expired blocks found.")

    return 0


def cmd_rollback(args) -> int:
    """
    Rollback automation command.
    Applies patterns with auto-rollback protection and reports results.
    """
    config = SoulForgeConfig(overrides={"workspace": args.workspace})
    setup_logging(config.log_level)

    print(f"SoulForge Rollback Auto (workspace: {config.workspace})")
    print("=" * 50)
    print(f"Auto-rollback is {'enabled' if config.rollback_auto_enabled else 'disabled'}")
    print("")
    print("Auto-rollback is applied automatically during 'run'. This command")
    print("is a placeholder for explicit rollback scenarios.")
    print("")
    print("To see rollback-protected evolution:")
    print("  soulforge.py run")
    print("")
    print("To explicitly restore a file from backup:")
    print("  soulforge.py restore SOUL.md --preview")

    return 0


def cmd_config(args) -> int:
    """
    Show or set configuration values.
    Reads from ~/.soulforgerc.json if exists.
    """
    config_path = str(Path.home() / ".soulforgerc.json")
    config = SoulForgeConfig(overrides={"workspace": args.workspace})

    if args.show:
        print(f"SoulForge Config (workspace: {config.workspace})")
        print("=" * 50)
        print(f"Config file: {config_path} ({'exists' if Path(config_path).exists() else 'not found'})")
        print("")
        print("Current values:")
        important_keys = [
            "workspace", "trigger_threshold", "max_token_budget",
            "hawk_bridge_enabled", "rollback_auto_enabled",
            "notify_on_complete", "notify_chat_id",
            "backup_retention_important", "backup_retention_normal",
            "backup_enabled", "log_level",
        ]
        for key in important_keys:
            val = config.get(key)
            if val is not None:
                print(f"  {key}: {val}")
        print("")
        print("All config keys:")
        for key, val in sorted(config.to_dict().items()):
            print(f"  {key}: {val}")
        return 0

    if args.set:
        key_value = args.set
        if "=" not in key_value:
            print("❌ Invalid format. Use: config --set key=value")
            return 1

        key, value = key_value.split("=", 1)

        # Try to parse value as JSON (bool, int, string)
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            parsed = value  # Keep as string

        # Set in config
        config.set(key, parsed)

        # Persist to config file
        config.to_file(config_path)

        print(f"✅ Set {key} = {parsed}")
        print(f"   Saved to {config_path}")
        return 0

    # No subcommand specified
    print("SoulForge Config")
    print("=" * 50)
    print("Usage:")
    print("  soulforge.py config --show          Show current config")
    print("  soulforge.py config --set key=value  Set a config value")
    print("")
    print("Examples:")
    print("  soulforge.py config --set max_token_budget=8192")
    print("  soulforge.py config --set notify_on_complete=true")
    print("  soulforge.py config --set notify_chat_id=oc_xxx")
    return 0


def cmd_help(args) -> int:
    """Show help message."""
    lang = "zh" if args.zh else "en"
    print(_load_help_text(lang))
    return 0


def main() -> int:
    """Main entry point for the SoulForge CLI."""
    import sys

    if "--help-cn" in sys.argv or "--help" in sys.argv:
        help_lang = "zh" if "--help-cn" in sys.argv else "en"
        print(_load_help_text(help_lang))
        return 0

    parser = argparse.ArgumentParser(
        description="SoulForge - AI Agent Memory Evolution System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,
        epilog=__doc__
    )

    # Global arguments
    parser.add_argument("--workspace", default=os.environ.get("SOULFORGE_WORKSPACE", "~/.openclaw/workspace"))
    parser.add_argument("--config", help="Path to config.json")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    parser.add_argument("--help-cn", action="store_true")

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # run
    run_parser = subparsers.add_parser("run", help="Run evolution process")
    run_parser.add_argument("--dry-run", action="store_true")
    run_parser.add_argument("--force", action="store_true")
    run_parser.add_argument("--notify", action="store_true", help="Send Feishu notification on completion")
    run_parser.set_defaults(func=cmd_run)

    # review
    review_parser = subparsers.add_parser("review", help="Review patterns without writing")
    review_parser.set_defaults(func=cmd_review)

    # apply
    apply_parser = subparsers.add_parser("apply", help="Apply patterns from review output")
    apply_parser.add_argument("--confirm", action="store_true")
    apply_parser.set_defaults(func=cmd_apply)

    # backup
    backup_parser = subparsers.add_parser("backup", help="Backup management")
    backup_parser.add_argument("--create", action="store_true")
    backup_parser.set_defaults(func=cmd_backup_create)

    # status
    status_parser = subparsers.add_parser("status", help="Show current status")
    status_parser.set_defaults(func=cmd_status)

    # diff
    diff_parser = subparsers.add_parser("diff", help="Show changes since last run")
    diff_parser.set_defaults(func=cmd_diff)

    # stats
    stats_parser = subparsers.add_parser("stats", help="Show evolution statistics")
    stats_parser.set_defaults(func=cmd_stats)

    # inspect
    inspect_parser = subparsers.add_parser("inspect", help="Inspect patterns for a file")
    inspect_parser.add_argument("file")
    inspect_parser.set_defaults(func=cmd_inspect)

    # restore
    restore_parser = subparsers.add_parser("restore", help="Restore files from backup")
    restore_parser.add_argument("file", nargs="?")
    restore_parser.add_argument("--backup")
    restore_parser.add_argument("--preview", action="store_true")
    restore_parser.add_argument("--all", dest="restore_all", action="store_true")
    restore_parser.set_defaults(func=cmd_restore)

    # reset
    reset_parser = subparsers.add_parser("reset", help="Reset SoulForge state")
    reset_parser.set_defaults(func=cmd_reset)

    # template
    template_parser = subparsers.add_parser("template", help="Generate templates")
    template_parser.add_argument("template", nargs="?")
    template_parser.set_defaults(func=cmd_template)

    # changelog
    changelog_parser = subparsers.add_parser("changelog", help="Show changelog")
    changelog_parser.add_argument("--zh", action="store_true")
    changelog_parser.add_argument("--full", action="store_true")
    changelog_parser.set_defaults(func=cmd_changelog)

    # cron
    cron_parser = subparsers.add_parser("cron", help="Cron setup help")
    cron_parser.add_argument("--every", type=int, metavar="MINUTES")
    cron_parser.set_defaults(func=cmd_cron)

    # cron-set
    cron_set_parser = subparsers.add_parser("cron-set", help="Set cron schedule")
    cron_set_parser.add_argument("--every", type=int, metavar="MINUTES")
    cron_set_parser.add_argument("--show", action="store_true")
    cron_set_parser.add_argument("--remove", action="store_true")
    cron_set_parser.set_defaults(func=cmd_cron_set)

    # clean
    clean_parser = subparsers.add_parser("clean", help="Clean expired pattern blocks")
    clean_parser.add_argument("--expired", action="store_true", help="Clean expired blocks (required)")
    clean_parser.add_argument("--dry-run", action="store_true", help="Preview only")
    clean_parser.set_defaults(func=cmd_clean)

    # rollback
    rollback_parser = subparsers.add_parser("rollback", help="Rollback info")
    rollback_parser.add_argument("--auto", action="store_true", help="Auto-rollback mode")
    rollback_parser.set_defaults(func=cmd_rollback)

    # config
    config_parser = subparsers.add_parser("config", help="Show/set configuration")
    config_parser.add_argument("--show", action="store_true", help="Show current config")
    config_parser.add_argument("--set", help="Set key=value")
    config_parser.set_defaults(func=cmd_config)

    # help
    help_parser = subparsers.add_parser("help", help="Show help message")
    help_parser.add_argument("--zh", action="store_true")
    help_parser.set_defaults(func=cmd_help)

    # Parse
    known, _ = parser.parse_known_args()
    workspace = os.path.expanduser(known.workspace or "~/.openclaw/workspace")

    for subparser in [run_parser, review_parser, apply_parser, backup_parser, status_parser,
                       diff_parser, stats_parser, inspect_parser, restore_parser,
                       reset_parser, template_parser, changelog_parser, cron_parser,
                       cron_set_parser, clean_parser, rollback_parser, config_parser,
                       help_parser]:
        subparser.set_defaults(workspace=workspace)

    args = parser.parse_args()

    if getattr(args, 'help_cn', False):
        print(_load_help_text("zh"))
        return 0

    if not args.command:
        args.func = cmd_run
    else:
        args.func = args.func

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
