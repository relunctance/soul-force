#!/usr/bin/env python3
"""
SoulForge CLI - AI Agent Memory Evolution System

Usage:
    python3 soulforge.py run [--workspace PATH] [--dry-run] [--force] [--notify]
    python3 soulforge.py review [--workspace PATH] [--tag TAG] [--confidence LEVEL] [--interactive]
    python3 soulforge.py apply --confirm [--workspace PATH] [--interactive]
    python3 soulforge.py backup --create [--workspace PATH]
    python3 soulforge.py status [--workspace PATH]
    python3 soulforge.py diff [--workspace PATH]
    python3 soulforge.py stats [--workspace PATH]
    python3 soulforge.py inspect FILE [--workspace PATH]
    python3 soulforge.py restore [FILE] [--backup PATH] [--preview] [--all]
    python3 soulforge.py reset [--workspace PATH]
    python3 soulforge.py template [--workspace PATH]
    python3 soulforge.py changelog [--zh] [--full] [--visual]
    python3 soulforge.py cron [--every MINUTES]
    python3 soulforge.py clean --expired [--workspace PATH] [--dry-run]
    python3 soulforge.py rollback --auto [--workspace PATH]
    python3 soulforge.py config --show [--workspace PATH]
    python3 soulforge.py config --set KEY=VALUE [--workspace PATH]
    python3 soulforge.py ask "question" [--workspace PATH]
    python3 soulforge.py help

Examples:
    python3 soulforge.py run
    python3 soulforge.py run --dry-run
    python3 soulforge.py run --force --notify
    python3 soulforge.py review
    python3 soulforge.py review --tag preference
    python3 soulforge.py review --tag error --confidence high
    python3 soulforge.py review --interactive
    python3 soulforge.py apply --confirm
    python3 soulforge.py apply --interactive
    python3 soulforge.py backup --create
    python3 soulforge.py status
    python3 soulforge.py clean --expired
    python3 soulforge.py rollback --auto
    python3 soulforge.py config --show
    python3 soulforge.py config --set max_token_budget=8192
    python3 soulforge.py ask "What is my communication style?"
    python3 soulforge.py changelog --visual
    python3 soulforge.py help
"""

import argparse
import logging
import sys
import os
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from soulforge import SoulForgeConfig, MemoryReader, PatternAnalyzer, SoulEvolver
from soulforge.analyzer import DiscoveredPattern


# Constants
DEFAULT_WORKSPACE = "~/.openclaw/workspace"
CONFIG_PATH = str(Path.home() / ".soulforgerc.json")


def _load_help_text(lang: str = "en") -> str:
    """Load help text from references/ directory."""
    skill_dir = Path(__file__).parent.parent
    help_path = skill_dir / "references" / f"help-{lang}.md"
    if help_path.exists():
        return help_path.read_text(encoding="utf-8")
    return f"Help file not found: {help_path}"


def _get_workspace(args) -> str:
    """Expand workspace path from args or environment."""
    workspace = getattr(args, 'workspace', None) or os.environ.get("SOULFORGE_WORKSPACE", DEFAULT_WORKSPACE)
    return os.path.expanduser(workspace)


def setup_logging(level: str = "INFO") -> None:
    """Configure logging for the CLI."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _setup_command(args) -> tuple:
    """Common setup for all commands: create config and setup logging. Returns (config, logger_name)."""
    workspace = _get_workspace(args)
    config = SoulForgeConfig(overrides={"workspace": workspace})
    setup_logging(config.log_level)
    return config


def _load_existing_content(config) -> Dict[str, str]:
    """Load existing content from all target files."""
    existing_content = {}
    for target in config.target_files:
        target_path = Path(config.workspace) / target
        if target_path.exists():
            existing_content[target] = target_path.read_text(encoding="utf-8")
    return existing_content


def _log_startup_info(config, logger) -> None:
    """Log startup information and mode selection."""
    logger.info(f"SoulForge starting (workspace: {config.workspace})")

    last_run = config.get_last_run_timestamp()
    if last_run:
        print(f"📊 Incremental mode: analyzing entries since {last_run}")
    else:
        print("📊 Full analysis mode: no previous run found")

    print(f"📊 Token budget: {config.max_token_budget} max")


def _read_memory_sources(config) -> tuple:
    """Read memory sources and return entries with summary."""
    print("📖 Reading memory sources...")
    reader = MemoryReader(config.workspace, config)
    entries = reader.read_all()

    if not entries:
        print("⚠️  No memory entries found. Nothing to analyze.")
        return None, None

    summary = reader.summarize()
    print(f"   ✓ Read {summary['total_entries']} entries from {len(summary['sources'])} sources")
    print(f"   ✓ Estimated tokens: ~{summary['estimated_tokens']} / {summary['max_token_budget']}")
    if summary.get("skipped_entries", 0) > 0:
        print(f"   ⚠️  Skipped {summary['skipped_entries']} entries (over token budget)")
    if summary.get("last_hawk_sync"):
        print(f"   ✓ hawk-bridge last sync: {summary['last_hawk_sync']}")

    return entries, reader


def _analyze_patterns(config, entries, existing_content, force: bool) -> Optional[List[DiscoveredPattern]]:
    """Analyze patterns from entries and existing content."""
    print("🔍 Analyzing patterns with configured LLM...")
    analyzer = PatternAnalyzer(config, force_apply=force)
    patterns = analyzer.analyze(entries, existing_content)

    if not patterns:
        print("   ⚠️  No significant patterns found.")
        return None

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

    return filtered


def _filter_patterns_for_application(config, filtered_patterns, force: bool) -> tuple:
    """Filter patterns into auto-apply and review categories."""
    analyzer = PatternAnalyzer(config, force_apply=force)
    auto_patterns = filtered_patterns if force else analyzer.filter_auto_apply(filtered_patterns)
    review_patterns = analyzer.filter_needs_review(filtered_patterns)
    return auto_patterns, review_patterns


def _apply_updates(config, auto_patterns, is_dry_run: bool) -> Dict[str, Any]:
    """Apply pattern updates with rollback protection."""
    print("✏️  Applying updates (with rollback protection)...")
    evolver = SoulEvolver(config.workspace, config)
    results = evolver.apply_updates(
        auto_patterns,
        rich_diff=is_dry_run
    )
    return results


def _display_dry_run_results(results: Dict[str, Any]) -> None:
    """Display dry run results with rich diff preview."""
    print(f"   ⚠️  DRY RUN - no files were written")
    print("")

    rich_diffs = results.get("rich_diffs", {})
    if rich_diffs:
        print("=" * 60)
        print(" UNIFIED DIFF PREVIEW")
        print("=" * 60)
        for filename, diff_text in rich_diffs.items():
            print(f"\n--- {filename}")
            print(f"+++ {filename}")
            print(diff_text)
    else:
        print("   Would update:")
        for filename in results["files_updated"]:
            print(f"     - {filename}")


def _display_apply_results(results: Dict[str, Any]) -> None:
    """Display results of applying updates."""
    print(f"   ✓ Updated {len(results['files_updated'])} files")
    print(f"   ✓ Applied {results['patterns_applied']} patterns")
    if results.get("rollbacks", 0) > 0:
        print(f"   ⚠️  Rollbacks performed: {results['rollbacks']}")


def _display_errors_and_review(results: Dict[str, Any], review_patterns) -> None:
    """Display errors and pending review patterns."""
    if review_patterns:
        print(f"\n   ⚠️  {len(review_patterns)} medium-confidence patterns need review.")

    if results["errors"]:
        print(f"   ⚠️  Errors encountered:")
        for err in results["errors"]:
            for file, error in err.items():
                print(f"     - {file}: {error}")


def _handle_notifications_and_summary(args, results, evolver) -> None:
    """Send notifications and display summary if configured."""
    if args.notify and not results["dry_run"]:
        print("\n📬 Sending notification...")
        evolver.deliver_result(results)

    if results.get("changes"):
        print("")
        print(evolver.summarize_changes())


def cmd_run(args) -> int:
    """
    Run the evolution process - the main command.
    """
    config = _setup_command(args)
    logger = logging.getLogger("soulforge.run")

    _log_startup_info(config, logger)

    # Step 1: Read memory sources
    entries, reader = _read_memory_sources(config)
    if entries is None:
        return 0

    # Step 2: Read existing content
    print("📄 Checking existing file content...")
    existing_content = _load_existing_content(config)

    # Step 3: Analyze patterns
    filtered_patterns = _analyze_patterns(config, entries, existing_content, args.force)
    if filtered_patterns is None:
        return 0

    auto_patterns, review_patterns = _filter_patterns_for_application(
        config, filtered_patterns, args.force
    )

    if not auto_patterns and not args.force:
        print("\n⚠️  No high-confidence patterns to auto-apply.")
        print("   Run 'soulforge.py review' to see medium-confidence patterns.")
        print("   Or use 'soulforge.py run --force' to apply all patterns.")
        return 0

    # Step 4: Apply updates with rollback
    results = _apply_updates(config, auto_patterns, args.dry_run)

    if results["dry_run"]:
        _display_dry_run_results(results)
    else:
        _display_apply_results(results)

    _display_errors_and_review(results, review_patterns)

    # Step 5: Notifications and summary
    evolver = SoulEvolver(config.workspace, config)
    _handle_notifications_and_summary(args, results, evolver)

    print("")
    if results["dry_run"]:
        print("🔍 DRY RUN complete. Run without --dry-run to write changes.")
    else:
        print("✅ SoulForge evolution complete!")

    return 0


def _print_pattern_details(patterns: List[DiscoveredPattern], confidence_level: str, prefix: str) -> None:
    """Print details for patterns of a given confidence level."""
    if not patterns:
        return

    confidence_labels = {
        "high": ("🔵", "High confidence (>0.8)", "will auto-apply"),
        "medium": ("🟡", "Medium confidence (0.5-0.8)", "need review"),
        "low": ("🔴", "Low confidence (<0.5)", "ignored"),
    }
    symbol, label, action = confidence_labels.get(confidence_level, ("", "", ""))

    print(f"\n{label} PATTERNS ({action}):")
    print("-" * 40)
    for p in patterns:
        conflict_flag = " ⚠️ CONFLICT" if p.has_conflict else ""
        tags_str = f" [Tags: {', '.join(p.tags)}]" if p.tags else ""
        print(f"  [{p.target_file}] {p.summary}{conflict_flag}{tags_str}")
        print(f"    Confidence: {p.confidence:.1f}, Evidence: {p.evidence_count}")
        print(f"    Insertion: {p.insertion_point}")
        if p.expires_at:
            print(f"    Expires: {p.expires_at}")
        if p.tags and confidence_level != "low":
            print(f"    Tags: {', '.join(p.tags)}")
        if confidence_level != "low":
            print(f"    Content: {p.content[:100]}...")
        print("")


def cmd_review(args) -> int:
    """Review mode: generate pattern analysis without writing files."""
    config = _setup_command(args)

    # v2.2.0: Interactive review mode
    if getattr(args, "interactive", False):
        return _cmd_review_interactive(args, config)

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

    existing_content = _load_existing_content(config)

    print("🔍 Analyzing patterns...")
    analyzer = PatternAnalyzer(config, force_apply=True)
    patterns = analyzer.analyze(entries, existing_content)

    if not patterns:
        print("   ⚠️  No patterns found.")
        return 0