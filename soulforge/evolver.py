"""
SoulForge SoulEvolver

Safely evolves workspace files by applying discovered patterns.

Safety features:
1. Incremental updates: Appends update blocks, never overwrites existing content
2. Backup before write: Every modification creates a timestamped backup
3. Duplicate detection: Skips patterns already present in the target file
4. Dry-run mode: Preview changes without writing
5. Per-agent isolation: Each agent has its own backup/state directories

Update block format:
    <!-- SoulForge Update | 2026-04-05T12:00:00+08:00 -->
    ## Pattern Summary

    **Source**: memory/2026-04-05.md
    **Pattern Type**: behavior
    **Confidence**: High (observed 4 times)

    **Content**:
    Pattern content here.

    <!-- /SoulForge Update -->

Multi-agent isolation:
    - main workspace:      .soulforge-main/backups/
    - wukong workspace:    .soulforge-wukong/backups/
    - tseng workspace:     .soulforge-tseng/backups/

Backup management:
    - Keeps last 10 backups per file
    - Timestamped with ISO format: FILENAME.YYYYMMDD_HHMMSS.bak
    - Old backups auto-cleaned on each write
"""

import os
import re
import logging
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Any

from soulforge.analyzer import DiscoveredPattern

logger = logging.getLogger(__name__)


class SoulEvolver:
    """
    Safely evolves workspace files by applying discovered patterns.

    Safety features:
    - Incremental updates (appends, never overwrites)
    - Backup before write
    - Provenance tracking
    - Dry-run mode
    """

    def __init__(self, workspace: str, config):
        """
        Initialize the evolver.

        Args:
            workspace: Path to workspace directory
            config: SoulForgeConfig instance
        """
        self.workspace = Path(workspace)
        self.config = config
        self._changes_made: List[Dict] = []

    def apply_updates(
        self,
        patterns: List[DiscoveredPattern],
        dry_run: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Apply discovered patterns to target files.

        Args:
            patterns: List of DiscoveredPattern objects to apply
            dry_run: If True, don't actually write (default from config)

        Returns:
            Dict with results summary
        """
        if dry_run is None:
            dry_run = self.config.is_dry_run

        self._changes_made = []
        results = {
            "dry_run": dry_run,
            "patterns_attempted": len(patterns),
            "patterns_applied": 0,
            "patterns_skipped": 0,
            "errors": [],
            "files_updated": [],
        }

        # Group patterns by target file
        by_file: Dict[str, List[DiscoveredPattern]] = {}
        for pattern in patterns:
            target = pattern.target_file
            if target not in by_file:
                by_file[target] = []
            by_file[target].append(pattern)

        # Process each target file
        for filename, file_patterns in by_file.items():
            try:
                result = self._apply_to_file(filename, file_patterns, dry_run)
                if result["applied"] > 0:
                    results["files_updated"].append(filename)
                    results["patterns_applied"] += result["applied"]
                results["patterns_skipped"] += result["skipped"]
                if result.get("error"):
                    results["errors"].append({filename: result["error"]})
            except Exception as e:
                logger.error(f"Failed to update {filename}: {e}")
                results["errors"].append({filename: str(e)})

        results["changes"] = self._changes_made

        # Write changelog (only if not dry-run and changes were made)
        if not dry_run and results["patterns_applied"] > 0:
            self._write_changelog(results)

        return results

    def _write_changelog(self, results: Dict[str, Any]) -> None:
        """
        Write a changelog entry for this evolution run.
        
        Creates or appends to CHANGELOG.md and CHANGELOG.zh-CN.md in the
        agent's state directory.
        
        Args:
            results: Results dict from apply_updates()
        """
        state_dir = Path(self.config.state_dir)
        state_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z")
        patterns = results.get("changes", [])

        # Build English changelog entry
        en_entry = f"""## {timestamp}

### Files Updated: {len(results.get("files_updated", []))}
{", ".join(results.get("files_updated", []))}

### Patterns Applied: {results["patterns_applied"]}
"""
        for change in patterns:
            en_entry += f"- **{change['file']}**: {change['pattern']}\n"

        if results.get("errors"):
            en_entry += "\n### Errors:\n"
            for err in results["errors"]:
                for file, error in err.items():
                    en_entry += f"- {file}: {error}\n"

        en_entry += "---\n\n"

        # Build Chinese changelog entry
        zh_entry = f"""## {timestamp}

### 更新的文件：{len(results.get("files_updated", []))}
{", ".join(results.get("files_updated", []))}

### 应用的模式：{results["patterns_applied"]}
"""
        for change in patterns:
            zh_entry += f"- **{change['file']}**: {change['pattern']}\n"

        if results.get("errors"):
            zh_entry += "\n### 错误：\n"
            for err in results["errors"]:
                for file, error in err.items():
                    zh_entry += f"- {file}: {error}\n"

        zh_entry += "---\n\n"

        # Write English changelog
        en_path = state_dir / "CHANGELOG.md"
        if en_path.exists():
            existing = en_path.read_text(encoding="utf-8")
            # Find the last "---" separator and insert after it
            parts = existing.split("---\n\n", 1)
            if len(parts) > 1:
                new_content = parts[0] + "---\n\n" + en_entry + parts[1]
            else:
                new_content = en_entry + existing
        else:
            new_content = "# SoulForge Changelog\n\n" + en_entry

        en_path.write_text(new_content, encoding="utf-8")
        logger.info(f"Changelog updated: {en_path}")

        # Write Chinese changelog
        zh_path = state_dir / "CHANGELOG.zh-CN.md"
        if zh_path.exists():
            existing = zh_path.read_text(encoding="utf-8")
            parts = existing.split("---\n\n", 1)
            if len(parts) > 1:
                new_content = parts[0] + "---\n\n" + zh_entry + parts[1]
            else:
                new_content = zh_entry + existing
        else:
            new_content = "# SoulForge 更新日志\n\n" + zh_entry

        zh_path.write_text(new_content, encoding="utf-8")
        logger.info(f"Changelog updated: {zh_path}")

    def _apply_to_file(
        self,
        filename: str,
        patterns: List[DiscoveredPattern],
        dry_run: bool
    ) -> Dict[str, Any]:
        """
        Apply patterns to a single file.

        Args:
            filename: Target file name (relative to workspace)
            patterns: Patterns to apply
            dry_run: Whether to actually write

        Returns:
            Dict with applied/skipped counts and any error
        """
        file_path = self.workspace / filename
        result = {"applied": 0, "skipped": 0, "error": None}

        # Load existing content
        if file_path.exists():
            existing_content = file_path.read_text(encoding="utf-8")
        else:
            existing_content = ""
            # Create empty file with basic structure
            file_path.parent.mkdir(parents=True, exist_ok=True)
            logger.info(f"File doesn't exist, will create: {filename}")

        # Check for duplicates
        patterns_to_apply = self._filter_duplicates(patterns, existing_content)

        if not patterns_to_apply:
            result["skipped"] = len(patterns)
            logger.info(f"All patterns already exist in {filename}, skipping")
            return result

        # Create backup
        if not dry_run and self.config.get("backup_enabled", True):
            self._create_backup(file_path)

        # Apply each pattern
        for pattern in patterns_to_apply:
            update_block = pattern.to_markdown_block()

            if dry_run:
                logger.info(f"[DRY RUN] Would add to {filename}: {pattern.summary}")
                result["applied"] += 1
                self._changes_made.append({
                    "file": filename,
                    "action": "would_add",
                    "pattern": pattern.summary,
                    "content_preview": pattern.content[:100],
                })
            else:
                # Append to file
                try:
                    with open(file_path, "a", encoding="utf-8") as f:
                        f.write("\n" + update_block)

                    logger.info(f"Updated {filename}: {pattern.summary}")
                    result["applied"] += 1
                    self._changes_made.append({
                        "file": filename,
                        "action": "added",
                        "pattern": pattern.summary,
                    })
                except Exception as e:
                    result["error"] = str(e)
                    logger.error(f"Failed to write to {filename}: {e}")

        return result

    def _filter_duplicates(
        self,
        patterns: List[DiscoveredPattern],
        existing_content: str
    ) -> List[DiscoveredPattern]:
        """
        Filter out patterns that are already present in the file.

        Args:
            patterns: Patterns to check
            existing_content: Current file content

        Returns:
            Patterns that should be applied (not duplicates)
        """
        if not existing_content:
            return patterns

        filtered = []
        for pattern in patterns:
            # Check if similar content already exists
            content_snippet = pattern.content[:50].lower()
            summary_snippet = pattern.summary[:50].lower()

            # Look for the summary or content in existing file
            if content_snippet in existing_content.lower():
                logger.debug(f"Skipping duplicate pattern: {pattern.summary}")
                continue
            if summary_snippet in existing_content.lower():
                logger.debug(f"Skipping similar pattern: {pattern.summary}")
                continue

            # Check for SoulForge update blocks with same summary
            if re.search(
                rf"<!--\s*SoulForge.*-->\s*##\s*{re.escape(pattern.summary)}",
                existing_content,
                re.IGNORECASE
            ):
                logger.debug(f"Skipping already-updated pattern: {pattern.summary}")
                continue

            filtered.append(pattern)

        return filtered

    def _create_backup(self, file_path: Path) -> None:
        """
        Create a timestamped backup of the file.

        Args:
            file_path: Path to file to backup
        """
        if not file_path.exists():
            return

        backup_dir = Path(self.config.backup_dir)
        backup_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{file_path.name}.{timestamp}.bak"
        backup_path = backup_dir / backup_name

        shutil.copy2(file_path, backup_path)
        logger.info(f"Backup created: {backup_path}")

        # Clean up old backups (keep last 10)
        self._cleanup_old_backups(backup_dir, file_path.name, keep=10)

    def _cleanup_old_backups(self, backup_dir: Path, original_name: str, keep: int = 10) -> None:
        """Remove old backups, keeping only the most recent N."""
        backups = sorted(
            backup_dir.glob(f"{original_name}.*.bak"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )

        for old_backup in backups[keep:]:
            old_backup.unlink()
            logger.debug(f"Removed old backup: {old_backup}")

    def get_backup_list(self, filename: str) -> List[Dict[str, str]]:
        """
        Get list of backups for a file.

        Args:
            filename: Original file name

        Returns:
            List of dicts with path and timestamp
        """
        backup_dir = Path(self.config.backup_dir)
        if not backup_dir.exists():
            return []

        backups = sorted(
            backup_dir.glob(f"{filename}.*.bak"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )

        return [
            {
                "path": str(b),
                "timestamp": datetime.fromtimestamp(b.stat().st_mtime).isoformat(),
            }
            for b in backups
        ]

    def restore_from_backup(self, filename: str, backup_path: str) -> bool:
        """
        Restore a file from backup.

        Args:
            filename: Target file name
            backup_path: Path to backup file

        Returns:
            True if successful
        """
        try:
            backup = Path(backup_path)
            target = self.workspace / filename

            if not backup.exists():
                logger.error(f"Backup not found: {backup_path}")
                return False

            # Create backup of current file before restoring
            if target.exists():
                self._create_backup(target)

            shutil.copy2(backup, target)
            logger.info(f"Restored {filename} from {backup_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to restore: {e}")
            return False

    def summarize_changes(self) -> str:
        """Generate a human-readable summary of changes made."""
        if not self._changes_made:
            return "No changes made."

        lines = ["SoulForge Update Summary:", ""]
        by_file: Dict[str, List] = {}
        for change in self._changes_made:
            f = change["file"]
            if f not in by_file:
                by_file[f] = []
            by_file[f].append(change)

        for filename, changes in by_file.items():
            lines.append(f"  {filename}:")
            for c in changes:
                action = "Added" if c["action"] == "added" else c["action"]
                lines.append(f"    - {action}: {c['pattern']}")
            lines.append("")

        return "\n".join(lines)

    def get_changelog(self, lang: str = "en") -> str:
        """
        Get the changelog content.

        Args:
            lang: Language code, 'en' or 'zh-CN'

        Returns:
            Changelog content as string, empty if not found
        """
        state_dir = Path(self.config.state_dir)
        filename = "CHANGELOG.md" if lang == "en" else "CHANGELOG.zh-CN.md"
        changelog_path = state_dir / filename

        if not changelog_path.exists():
            return ""

        return changelog_path.read_text(encoding="utf-8")
