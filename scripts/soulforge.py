#!/usr/bin/env python3
"""
SoulForge CLI - AI Agent Memory Evolution System

A command-line tool that automatically evolves your OpenClaw agent's identity files
(SOUL.md, USER.md, IDENTITY.md, MEMORY.md, etc.) by analyzing memory patterns.

Usage:
    python3 soulforge.py run [--workspace PATH] [--dry-run]
    python3 soulforge.py status [--workspace PATH]
    python3 soulforge.py diff [--workspace PATH]
    python3 soulforge.py stats [--workspace PATH]
    python3 soulforge.py inspect FILE [--workspace PATH]
    python3 soulforge.py rollback FILE [--backup PATH] [--workspace PATH]
    python3 soulforge.py reset [--workspace PATH]
    python3 soulforge.py template [--workspace PATH]
    python3 soulforge.py cron [--every MINUTES]

Examples:
    python3 soulforge.py run
    python3 soulforge.py run --dry-run
    python3 soulforge.py status
    python3 soulforge.py diff
    python3 soulforge.py stats
    python3 soulforge.py inspect SOUL.md
    python3 soulforge.py rollback SOUL.md --backup .soulforge-backups/SOUL.md.20260405_120000.bak
    python3 soulforge.py reset
    python3 soulforge.py template
"""

import argparse
import logging
import sys
import os
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from soulforge import SoulForgeConfig, MemoryReader, PatternAnalyzer, SoulEvolver


def setup_logging(level: str = "INFO") -> None:
    """
    Configure logging for the CLI.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
    """
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def cmd_run(args) -> int:
    """
    Run the evolution process - the main command.
    
    Reads memory sources, analyzes patterns, and updates target files.
    
    Args:
        args: Parsed command-line arguments
        
    Returns:
        Exit code (0 = success, 1 = error)
    """
    config = SoulForgeConfig(
        config_path=args.config,
        overrides={
            "dry_run": args.dry_run,
            "workspace": args.workspace,
        }
    )
    setup_logging(config.log_level)

    logger = logging.getLogger("soulforge.run")
    logger.info(f"SoulForge starting (workspace: {config.workspace})")

    # Step 1: Read memory sources
    print("📖 Reading memory sources...")
    reader = MemoryReader(config.workspace, config)
    entries = reader.read_all()

    if not entries:
        print("⚠️  No memory entries found. Nothing to analyze.")
        print("   Make sure you have:")
        print("   - memory/*.md daily files")
        print("   - .learnings/ directory")
        print("   - hawk-bridge vector store")
        return 0

    summary = reader.summarize()
    print(f"   ✓ Read {summary['total_entries']} entries from {len(summary['sources'])} sources")

    # Step 2: Read existing content of target files
    print("📄 Checking existing file content...")
    existing_content = {}
    for target in config.target_files:
        target_path = Path(config.workspace) / target
        if target_path.exists():
            existing_content[target] = target_path.read_text(encoding="utf-8")
            print(f"   ✓ {target} exists ({len(existing_content[target])} chars)")
        else:
            print(f"   - {target} does not exist yet (will create)")

    # Step 3: Analyze patterns
    print("🔍 Analyzing patterns with configured LLM...")
    analyzer = PatternAnalyzer(config)
    patterns = analyzer.analyze(entries, existing_content)

    if not patterns:
        print("   ⚠️  No significant patterns found.")
        return 0

    # Filter by threshold
    filtered = analyzer.filter_by_threshold(patterns)
    print(f"   ✓ Found {len(filtered)} patterns above threshold")

    # Step 4: Apply updates
    print("✏️  Applying updates...")
    evolver = SoulEvolver(config.workspace, config)
    results = evolver.apply_updates(filtered)

    if results["dry_run"]:
        print(f"   ⚠️  DRY RUN - no files were written")
        print("")
        print("   Would update:")
        for filename in results["files_updated"]:
            print(f"     - {filename}")
    else:
        print(f"   ✓ Updated {len(results['files_updated'])} files")
        print(f"   ✓ Applied {results['patterns_applied']} patterns")

    if results["errors"]:
        print(f"   ⚠️  Errors encountered:")
        for err in results["errors"]:
            for file, error in err.items():
                print(f"     - {file}: {error}")

    # Print summary
    if results.get("changes"):
        print("")
        print(evolver.summarize_changes())

    print("")
    if results["dry_run"]:
        print("🔍 DRY RUN complete. Run without --dry-run to write changes.")
    else:
        print("✅ SoulForge evolution complete!")

    return 0


def cmd_status(args) -> int:
    """
    Show current status - memory overview and target file states.
    
    Args:
        args: Parsed command-line arguments
        
    Returns:
        Exit code (0 = success)
    """
    config = SoulForgeConfig(overrides={"workspace": args.workspace})
    setup_logging(config.log_level)

    logger = logging.getLogger("soulforge.status")
    print(f"SoulForge Status (workspace: {config.workspace})")
    print("=" * 50)

    # Read memory
    reader = MemoryReader(config.workspace, config)
    entries = reader.read_all()
    summary = reader.summarize()

    print(f"\n📊 Memory Overview:")
    print(f"   Total entries: {summary['total_entries']}")
    print(f"   Sources: {len(summary['sources'])}")

    print(f"\n   By source type:")
    for source_type, count in summary.get("by_source_type", {}).items():
        print(f"     - {source_type}: {count}")

    print(f"\n   By category:")
    for category, count in summary.get("by_category", {}).items():
        print(f"     - {category}: {count}")

    # Check target files
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

    # Check backups
    backup_dir = Path(config.backup_dir)
    if backup_dir.exists():
        backups = list(backup_dir.glob("*.bak"))
        print(f"\n💾 Backups: {len(backups)} files in {backup_dir}")

    return 0


def cmd_diff(args) -> int:
    """
    Show what changed since last evolution run.
    
    Compares current target file content with the latest backup.
    
    Args:
        args: Parsed command-line arguments
        
    Returns:
        Exit code (0 = success, 1 = no backups found)
    """
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
        print(f"   Latest backup: {backups[0]['timestamp']}")

        if current_path.exists():
            current_content = current_path.read_text(encoding="utf-8")
            backup_content = Path(latest_backup).read_text(encoding="utf-8")

            if current_content == backup_content:
                print(f"   Status: No changes since backup")
            else:
                print(f"   Status: ⚠️  Changed (use 'rollback' to restore)")
        else:
            print(f"   Status: File does not exist")

    return 0


def cmd_stats(args) -> int:
    """
    Show evolution statistics.
    
    Displays counts of evolutions, patterns, and trends.
    
    Args:
        args: Parsed command-line arguments
        
    Returns:
        Exit code (0 = success)
    """
    config = SoulForgeConfig(overrides={"workspace": args.workspace})
    setup_logging(config.log_level)

    print(f"SoulForge Stats (workspace: {config.workspace})")
    print("=" * 50)

    reader = MemoryReader(config.workspace, config)
    entries = reader.read_all()
    summary = reader.summarize()

    # Count SoulForge update blocks in target files
    update_counts = {}
    for target in config.target_files:
        target_path = Path(config.workspace) / target
        if target_path.exists():
            content = target_path.read_text(encoding="utf-8")
            count = content.count("<!-- SoulForge Update")
            update_counts[target] = count

    print(f"\n📊 Evolution Statistics:")
    print(f"   Total memory entries: {summary['total_entries']}")
    print(f"   SoulForge updates per file:")
    for target, count in update_counts.items():
        print(f"     - {target}: {count} updates")

    # Backups count
    backup_dir = Path(config.backup_dir)
    if backup_dir.exists():
        backups = list(backup_dir.glob("*.bak"))
        print(f"\n💾 Total backups: {len(backups)}")

    return 0


def cmd_inspect(args) -> int:
    """
    Inspect what would be evolved for a specific file.
    
    Analyzes patterns specifically for one target file without writing.
    
    Args:
        args: Parsed command-line arguments
        
    Returns:
        Exit code (0 = success)
    """
    config = SoulForgeConfig(overrides={"workspace": args.workspace})
    setup_logging(config.log_level)

    target_file = args.file
    if not target_file.endswith(".md"):
        target_file += ".md"

    print(f"SoulForge Inspect: {target_file} (workspace: {config.workspace})")
    print("=" * 50)

    # Check if file exists
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

    # Analyze patterns for this specific file
    print(f"\n🔍 Analyzing patterns for {target_file}...")
    reader = MemoryReader(config.workspace, config)
    entries = reader.read_all()

    analyzer = PatternAnalyzer(config)
    existing_content = {target_file: target_path.read_text()} if target_path.exists() else {}
    patterns = analyzer.analyze(entries, existing_content)

    # Filter to only this file
    file_patterns = [p for p in patterns if p.target_file == target_file]
    filtered = analyzer.filter_by_threshold(file_patterns)

    if filtered:
        print(f"\n   ✓ Found {len(filtered)} patterns for {target_file}:")
        for p in filtered:
            print(f"     - [{p.category}] {p.summary}")
            print(f"       Confidence: {p.confidence}, Evidence: {p.evidence_count}")
    else:
        print(f"\n   ⚠️  No patterns found for {target_file}")

    return 0


def cmd_restore(args) -> int:
    """
    Restore files from backup.

    Features:
    - List all backups for a file or all files
    - Preview what will change (diff between current and backup)
    - Restore single file or all files
    - Confirm before destructive action

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 = success, 1 = error)
    """
    config = SoulForgeConfig(overrides={"workspace": args.workspace})
    setup_logging(config.log_level)

    logger = logging.getLogger("soulforge.restore")

    evolver = SoulEvolver(config.workspace, config)

    # Handle restore all
    if args.restore_all:
        return _restore_all(evolver, config, args)

    # Handle single file restore
    target_file = args.file
    if not target_file.endswith(".md"):
        target_file += ".md"

    # List available backups
    if not args.backup and not args.preview:
        print(f"Available backups for {target_file}:")
        print("=" * 50)
        backups = evolver.get_backup_list(target_file)
        if not backups:
            print("No backups found")
            return 1
        for i, b in enumerate(backups[:10]):
            print(f"  [{i+1}] {b['path']}")
            print(f"      {b['timestamp']}")
        if len(backups) > 10:
            print(f"\n  ... and {len(backups) - 10} more (use --backup INDEX to select)")
        print("")
        print("Usage:")
        print(f"  soulforge.py restore {args.file} --preview          # Preview changes")
        print(f"  soulforge.py restore {args.file} --backup 1        # Restore backup #1")
        print(f"  soulforge.py restore --all --preview               # Preview all")
        print(f"  soulforge.py restore --all                        # Restore all files")
        return 0

    # Determine which backup to use
    backup_path = args.backup
    backups = evolver.get_backup_list(target_file)

    if backup_path is not None:
        # Allow numeric index
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

    # Preview mode
    if args.preview:
        return _preview_restore(target_file, backup_path, config)

    # Confirm restore
    print(f"SoulForge Restore: {target_file}")
    print("=" * 50)
    print(f"Restore from: {backup_path}")
    print("")
    print("⚠️  This will REPLACE current content with backup content.")
    print("")
    print("Changes:")
    current_path = Path(config.workspace) / target_file
    if current_path.exists():
        current_size = len(current_path.read_text(encoding="utf-8"))
        backup_size = len(Path(backup_path).read_text(encoding="utf-8"))
        print(f"  Current: {current_size} chars")
        print(f"  Backup:  {backup_size} chars")
        print(f"  Change: {backup_size - current_size:+d} chars")
    else:
        print(f"  File does not exist, will be created from backup")

    print("")
    confirm = input("Type 'yes' to confirm: ")
    if confirm.lower() != "yes":
        print("Cancelled.")
        return 0

    # Restore
    success = evolver.restore_from_backup(target_file, backup_path)
    if success:
        print(f"✅ Restored {target_file} from {backup_path}")
        return 0
    else:
        print(f"❌ Restore failed")
        return 1


def _preview_restore(target_file: str, backup_path: str, config) -> int:
    """
    Show a preview of what will change when restoring.

    Args:
        target_file: File to restore
        backup_path: Path to backup file
        config: SoulForgeConfig

    Returns:
        Exit code (0 = success)
    """
    print(f"Preview: Restore {target_file}")
    print("=" * 50)
    print(f"Backup: {backup_path}")
    print("")

    current_path = Path(config.workspace) / target_file

    print("Current content:")
    print("-" * 40)
    if current_path.exists():
        current = current_path.read_text(encoding="utf-8")
        print(f"  {len(current)} chars")
        print(current[:500])
        if len(current) > 500:
            print("  ...(truncated)")
    else:
        print("  (file does not exist)")

    print("")
    print("Backup content:")
    print("-" * 40)
    backup = Path(backup_path).read_text(encoding="utf-8")
    print(f"  {len(backup)} chars")
    print(backup[:500])
    if len(backup) > 500:
        print("  ...(truncated)")

    return 0


def _restore_all(evolver, config, args) -> int:
    """
    Restore all files from their latest backups.

    Args:
        evolver: SoulEvolver instance
        config: SoulForgeConfig
        args: Parsed command-line arguments

    Returns:
        Exit code (0 = success)
    """
    print(f"SoulForge Restore All (workspace: {config.workspace})")
    print("=" * 50)

    # Get all backups for all target files
    all_backups = {}
    for target in config.target_files:
        backups = evolver.get_backup_list(target)
        if backups:
            all_backups[target] = backups[0]  # Latest backup

    if not all_backups:
        print("No backups found for any file")
        return 1

    print(f"Files with backups: {len(all_backups)}")
    for target, backup_info in all_backups.items():
        print(f"  - {target}: {backup_info['path']}")

    print("")
    print("⚠️  This will REPLACE current content of ALL listed files.")
    print("⚠️  SoulForge evolution history will NOT be deleted (changelog preserved).")
    print("")

    if args.preview:
        print("Preview mode - no changes will be made")
        print("")
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
                    print(f"  Change: {len(backup) - len(current):+d} chars")
            else:
                print(f"  File does not exist, will be created")
        return 0

    confirm = input("Type 'yes' to restore ALL files: ")
    if confirm.lower() != "yes":
        print("Cancelled.")
        return 0

    # Restore all files
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
    """
    Reset all SoulForge state for this workspace.
    
    Removes all backups and state files. Target files are NOT modified.
    
    Args:
        args: Parsed command-line arguments
        
    Returns:
        Exit code (0 = success)
    """
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

    # Remove backup directory
    backup_dir = Path(config.backup_dir)
    if backup_dir.exists():
        import shutil
        shutil.rmtree(backup_dir)
        print(f"✅ Removed {backup_dir}")

    # Remove state directory
    state_dir = Path(config.state_dir)
    if state_dir.exists():
        import shutil
        shutil.rmtree(state_dir)
        print(f"✅ Removed {state_dir}")

    print("\n✅ Reset complete. Run 'soulforge.py run' to start fresh.")
    return 0


def cmd_template(args) -> int:
    """
    Generate standard templates for target files.
    
    Prints template content that can be used as a starting point.
    
    Args:
        args: Parsed command-line arguments
        
    Returns:
        Exit code (0 = success)
    """
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
    """
    Show the evolution changelog.

    Displays all evolution changes chronologically, newest first.
    Supports both English and Chinese versions.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 = success, 1 = no changelog found)
    """
    config = SoulForgeConfig(overrides={"workspace": args.workspace})
    setup_logging(config.log_level)

    # Determine language
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

    # Show first N characters as preview
    preview_lines = content.split("\n")[:50]
    print("\n".join(preview_lines))

    if len(content.split("\n")) > 50:
        print("\n... (truncated, use --full to see all)")

    print(f"\n📄 Full changelog: {Path(config.state_dir) / ('CHANGELOG.' + lang + '.md')}")
    return 0


def cmd_cron(args) -> int:
    """
    Show how to set up cron scheduling.
    
    Args:
        args: Parsed command-line arguments
        
    Returns:
        Exit code (0 = success)
    """
    if args.every:
        print(f"To schedule SoulForge every {args.every} minutes, add this to your crontab:")
        print("")
        print(f"*/{args.every} * * * * cd {os.getcwd()} && python3 {__file__} run >> /var/log/soulforge.log 2>&1")
        print("")
        print("Or with OpenClaw cron:")
        print(f"  openclaw cron add --name soulforce-evolve --every {args.every}m \\")
        print(f"    --message 'exec python3 {__file__} run'")
    return 0


def main() -> int:
    """
    Main entry point for the SoulForge CLI.
    
    Parses arguments and dispatches to the appropriate command.
    
    Returns:
        Exit code from the dispatched command
    """
    parser = argparse.ArgumentParser(
        description="SoulForge - AI Agent Memory Evolution System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    # Global arguments
    parser.add_argument(
        "--workspace",
        default=os.environ.get("SOULFORGE_WORKSPACE", "~/.openclaw/workspace"),
        help="Workspace directory (default: ~/.openclaw/workspace)"
    )
    parser.add_argument(
        "--config",
        help="Path to config.json"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing"
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level"
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # run command - main evolution
    run_parser = subparsers.add_parser("run", help="Run evolution process")
    run_parser.add_argument("--dry-run", action="store_true", help="Preview only")
    run_parser.set_defaults(func=cmd_run)

    # status command - current state
    status_parser = subparsers.add_parser("status", help="Show current status")
    status_parser.set_defaults(func=cmd_status)

    # diff command - show changes
    diff_parser = subparsers.add_parser("diff", help="Show changes since last run")
    diff_parser.set_defaults(func=cmd_diff)

    # stats command - show statistics
    stats_parser = subparsers.add_parser("stats", help="Show evolution statistics")
    stats_parser.set_defaults(func=cmd_stats)

    # inspect command - check specific file
    inspect_parser = subparsers.add_parser("inspect", help="Inspect patterns for a specific file")
    inspect_parser.add_argument("file", help="File to inspect (e.g., SOUL.md)")
    inspect_parser.set_defaults(func=cmd_inspect)

    # restore command - restore from backup
    restore_parser = subparsers.add_parser("restore", help="Restore files from backup")
    restore_parser.add_argument("file", nargs="?", help="File to restore (e.g., SOUL.md)")
    restore_parser.add_argument("--backup", help="Backup path or index number")
    restore_parser.add_argument("--preview", action="store_true", help="Preview what will change without restoring")
    restore_parser.add_argument("--all", dest="restore_all", action="store_true", help="Restore all files")
    restore_parser.set_defaults(func=cmd_restore)

    # reset command - reset all state
    reset_parser = subparsers.add_parser("reset", help="Reset all SoulForge state")
    reset_parser.set_defaults(func=cmd_reset)

    # template command - generate templates
    template_parser = subparsers.add_parser("template", help="Generate file templates")
    template_parser.add_argument("template", nargs="?", help="Specific template to show")
    template_parser.set_defaults(func=cmd_template)

    # changelog command - show evolution history
    changelog_parser = subparsers.add_parser("changelog", help="Show evolution changelog")
    changelog_parser.add_argument("--zh", action="store_true", help="Show Chinese version")
    changelog_parser.add_argument("--full", action="store_true", help="Show full changelog")
    changelog_parser.set_defaults(func=cmd_changelog)

    # cron command - cron setup help
    cron_parser = subparsers.add_parser("cron", help="Cron setup help")
    cron_parser.add_argument("--every", type=int, metavar="MINUTES", help="Run every N minutes")
    cron_parser.set_defaults(func=cmd_cron)

    # Parse known args to get workspace first
    known, _ = parser.parse_known_args()
    workspace = os.path.expanduser(known.workspace or "~/.openclaw/workspace")

    # Set workspace on all subparsers
    for subparser in [run_parser, status_parser, diff_parser, stats_parser,
                      inspect_parser, restore_parser, reset_parser, template_parser,
                      changelog_parser, cron_parser]:
        subparser.set_defaults(workspace=workspace)

    args = parser.parse_args()

    # Default to run if no command specified
    if not args.command:
        args.func = cmd_run
    else:
        args.func = args.func

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
