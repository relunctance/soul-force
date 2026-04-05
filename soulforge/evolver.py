"""
SoulForge SoulEvolver

Safely evolves workspace files by applying discovered patterns.

Features:
1. Rollback automation: apply_with_rollback() validates writes and auto-restores on failure
2. Pattern expiry: clean_expired() removes/marks stale expired blocks
3. Notification: deliver_result() sends Feishu notifications on completion
4. All original safety features (incremental, smart insertion, backup, dry-run)
"""

import os
import re
import json
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
    """

    def __init__(self, workspace: str, config):
        self.workspace = Path(workspace)
        self.config = config
        self._changes_made: List[Dict] = []
        self._review_output: List[Dict] = []

    def apply_updates(
        self,
        patterns: List[DiscoveredPattern],
        dry_run: Optional[bool] = None,
        backup_type: str = "auto",
        rich_diff: bool = False,  # v2.2.0: unified diff preview
    ) -> Dict[str, Any]:
        """
        Apply discovered patterns to target files.

        Args:
            patterns: List of DiscoveredPattern objects to apply
            dry_run: If True, don't actually write (default from config)
            backup_type: "auto" or "manual" for backup naming
            rich_diff: If True, produce unified diff preview in results

        Returns:
            Dict with results summary
        """
        if dry_run is None:
            dry_run = self.config.is_dry_run

        self._changes_made = []
        rich_diffs: Dict[str, str] = {}  # v2.2.0: file -> diff string
        results = {
            "dry_run": dry_run,
            "patterns_attempted": len(patterns),
            "patterns_applied": 0,
            "patterns_skipped": 0,
            "errors": [],
            "files_updated": [],
            "backup_type": backup_type,
            "rollbacks": 0,
            "rich_diffs": rich_diffs,  # v2.2.0
        }

        by_file: Dict[str, List[DiscoveredPattern]] = {}
        for pattern in patterns:
            target = pattern.target_file
            if target not in by_file:
                by_file[target] = []
            by_file[target].append(pattern)

        for filename, file_patterns in by_file.items():
            try:
                # Use rollback-enabled apply
                result = self._apply_to_file_with_rollback(
                    filename, file_patterns, dry_run, backup_type
                )
                if result["applied"] > 0:
                    results["files_updated"].append(filename)
                    results["patterns_applied"] += result["applied"]

                    # v2.2.0: Generate rich diff preview
                    if rich_diff:
                        diff_text = self._generate_rich_diff(filename, file_patterns)
                        rich_diffs[filename] = diff_text

                results["patterns_skipped"] += result["skipped"]
                results["rollbacks"] += result.get("rollbacks", 0)
                if result.get("error"):
                    results["errors"].append({filename: result["error"]})
            except Exception as e:
                logger.error(f"Failed to update {filename}: {e}")
                results["errors"].append({filename: str(e)})

        results["changes"] = self._changes_made

        if not dry_run and results["patterns_applied"] > 0:
            self._write_changelog(results)
            self.config.set_last_run_timestamp()

        return results

    def _apply_to_file_with_rollback(
        self,
        filename: str,
        patterns: List[DiscoveredPattern],
        dry_run: bool,
        backup_type: str = "auto"
    ) -> Dict[str, Any]:
        """
        Apply patterns to a single file with automatic rollback on validation failure.

        Args:
            filename: Target file name (relative to workspace)
            patterns: Patterns to apply
            dry_run: Whether to actually write
            backup_type: "auto" or "manual"

        Returns:
            Dict with applied/skipped counts, rollback count, and any error
        """
        file_path = self.workspace / filename
        result = {"applied": 0, "skipped": 0, "error": None, "rollbacks": 0}

        # Load existing content
        if file_path.exists():
            existing_content = file_path.read_text(encoding="utf-8")
        else:
            existing_content = ""
            file_path.parent.mkdir(parents=True, exist_ok=True)
            logger.info(f"File doesn't exist, will create: {filename}")

        patterns_to_apply = self._filter_duplicates(patterns, existing_content)
        if not patterns_to_apply:
            result["skipped"] = len(patterns)
            logger.info(f"All patterns already exist in {filename}, skipping")
            return result

        # Create backup BEFORE writing
        if not dry_run and self.config.get("backup_enabled", True):
            self._create_backup(file_path, backup_type)

        if dry_run:
            for pattern in patterns_to_apply:
                logger.info(f"[DRY RUN] Would add to {filename}: {pattern.summary} "
                            f"(at {pattern.insertion_point})")
                result["applied"] += 1
                self._changes_made.append({
                    "file": filename,
                    "action": "would_add",
                    "pattern": pattern.summary,
                    "insertion_point": pattern.insertion_point,
                })
            return result

        # Actually apply each pattern with rollback protection
        for pattern in patterns_to_apply:
            update_block = pattern.to_markdown_block()
            snapshot = file_path.read_text(encoding="utf-8") if file_path.exists() else ""

            try:
                self._insert_content(file_path, pattern.insertion_point, update_block)

                # Validate write
                if not self._validate_write(file_path, pattern, update_block):
                    logger.warning(f"Validation failed for {filename}, rolling back...")
                    file_path.write_text(snapshot, encoding="utf-8")
                    result["rollbacks"] += 1
                    result["error"] = f"Rollback: validation failed for pattern '{pattern.summary}'"
                    continue

                logger.info(f"Updated {filename}: {pattern.summary} (via {pattern.insertion_point})")
                result["applied"] += 1
                self._changes_made.append({
                    "file": filename,
                    "action": "added",
                    "pattern": pattern.summary,
                    "insertion_point": pattern.insertion_point,
                })
            except Exception as e:
                # Rollback on exception
                if snapshot:
                    file_path.write_text(snapshot, encoding="utf-8")
                    result["rollbacks"] += 1
                    logger.error(f"Write failed for {filename}, rolled back: {e}")
                result["error"] = str(e)

        return result

    def _validate_write(self, file_path: Path, pattern: DiscoveredPattern, block: str) -> bool:
        """
        Validate that a write was successful.

        Checks:
        1. File is readable
        2. New block exists in file
        3. Content is intact (block text present)

        Args:
            file_path: Path to the written file
            pattern: The pattern that was applied
            block: The block that was inserted

        Returns:
            True if validation passes, False otherwise
        """
        try:
            if not file_path.exists():
                logger.warning(f"Validation failed: file does not exist: {file_path}")
                return False

            content = file_path.read_text(encoding="utf-8")

            # Check that the block is present
            if block.strip() not in content.strip():
                logger.warning(f"Validation failed: block content not found in {file_path}")
                return False

            # Check that SoulForge markers are present
            if "<!-- SoulForge Update" not in content:
                logger.warning(f"Validation failed: SoulForge marker missing in {file_path}")
                return False

            return True
        except Exception as e:
            logger.warning(f"Validation error: {e}")
            return False

    def apply_with_rollback(
        self,
        patterns: List[DiscoveredPattern],
        dry_run: Optional[bool] = None,
        backup_type: str = "auto"
    ) -> Dict[str, Any]:
        """
        Alias for apply_updates with explicit rollback naming.

        Kept for backward compatibility and CLI --rollback-auto command.
        """
        return self.apply_updates(patterns, dry_run=dry_run, backup_type=backup_type)

    def clean_expired(self, dry_run: bool = True) -> Dict[str, Any]:
        """
        Remove or mark stale SoulForge update blocks that have expired.

        Scans target files for update blocks with **Expires** field,
        removes those past their expiry date.

        Args:
            dry_run: If True, only report what would be removed

        Returns:
            Dict with results summary
        """
        from datetime import datetime
        results = {
            "dry_run": dry_run,
            "files_scanned": 0,
            "blocks_removed": 0,
            "blocks_marked_stale": 0,
            "files_modified": [],
            "errors": [],
        }

        now = datetime.now()

        for target in self.config.target_files:
            target_path = self.workspace / target
            if not target_path.exists():
                continue

            results["files_scanned"] += 1

            try:
                content = target_path.read_text(encoding="utf-8")
                original = content

                # Find all SoulForge update blocks
                # Pattern: <!-- SoulForge Update | TIMESTAMP --> ... <!-- /SoulForge Update -->
                block_pattern = re.compile(
                    r"(<!-- SoulForge Update \| [^\n]+\n.*?<!-- /SoulForge Update -->\n?)",
                    re.DOTALL
                )

                new_blocks = []
                removed_count = 0
                marked_count = 0

                for match in block_pattern.finditer(content):
                    block = match.group(0)

                    # Extract **Expires** date if present
                    expires_match = re.search(r"\*\*Expires\*\*:\s*(\d{4}-\d{2}-\d{2})", block)
                    if not expires_match:
                        new_blocks.append(block)
                        continue

                    expires_str = expires_match.group(1)
                    try:
                        exp_date = datetime.strptime(expires_str, "%Y-%m-%d")
                        if exp_date < now:
                            # Expired — remove block
                            removed_count += 1
                            if not dry_run:
                                logger.info(f"Removing expired block from {target}: {expires_str}")
                        else:
                            # Not yet expired — keep but mark as stale if close
                            days_until = (exp_date - now).days
                            if days_until <= 7 and not dry_run:
                                # Add stale marker
                                block = block.replace(
                                    f"**Expires**: {expires_str}",
                                    f"**Expires**: {expires_str} ⚠️ STALE"
                                )
                                marked_count += 1
                            new_blocks.append(block)
                    except ValueError:
                        new_blocks.append(block)
                        continue

                if removed_count > 0 or marked_count > 0:
                    if not dry_run:
                        new_content = "".join(new_blocks)
                        target_path.write_text(new_content, encoding="utf-8")
                        results["files_modified"].append(target)

                    results["blocks_removed"] += removed_count
                    results["blocks_marked_stale"] += marked_count
                    logger.info(f"{target}: removed {removed_count} expired blocks, "
                                f"marked {marked_count} as stale")

            except Exception as e:
                logger.error(f"Failed to clean {target}: {e}")
                results["errors"].append({target: str(e)})

        return results

    def deliver_result(self, results: Dict[str, Any]) -> bool:
        """
        Deliver evolution result notification via Feishu.

        Args:
            results: Results dict from apply_updates()

        Returns:
            True if notification was sent or skipped, False on error
        """
        if not self.config.notify_on_complete:
            logger.debug("Notifications disabled, skipping")
            return True

        try:
            import subprocess
            from pathlib import Path

            # Build notification text
            files = results.get("files_updated", [])
            patterns = results.get("patterns_applied", 0)
            errors = results.get("errors", [])
            rollbacks = results.get("rollbacks", 0)
            dry_run = results.get("dry_run", False)

            if dry_run:
                summary = f"🔍 SoulForge DRY RUN — {patterns} patterns would be applied"
            else:
                summary = f"✅ SoulForge Evolution — {patterns} patterns applied to {len(files)} files"

            details = []
            if files:
                details.append(f"Files: {', '.join(files)}")
            if rollbacks > 0:
                details.append(f"⚠️ Rollbacks: {rollbacks}")
            if errors:
                err_files = [list(e.keys())[0] for e in errors]
                details.append(f"❌ Errors: {', '.join(err_files)}")

            message = summary
            if details:
                message += "\n" + "\n".join(details)

            # Try to send via openclaw message tool
            chat_id = self.config.notify_chat_id
            if chat_id:
                script = f"""
import subprocess
result = subprocess.run(
    ["openclaw", "message", "--chat", "{chat_id}", "--text", {json.dumps(message)}],
    capture_output=True,
    text=True,
    timeout=10
)
print(result.returncode)
"""
                try:
                    subprocess.run(["python3", "-c", script], timeout=15, capture_output=True)
                    logger.info("Feishu notification sent")
                    return True
                except Exception as e:
                    logger.warning(f"Failed to send Feishu notification: {e}")

            # Fallback: write to notification file
            notify_path = Path(self.config.state_dir) / "last_notification.txt"
            notify_path.parent.mkdir(parents=True, exist_ok=True)
            notify_path.write_text(message, encoding="utf-8")
            logger.info(f"Notification saved to {notify_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to deliver result notification: {e}")
            return False

    def generate_review(
        self,
        patterns: List[DiscoveredPattern]
    ) -> Dict[str, Any]:
        """Generate review output for patterns without writing files."""
        self._review_output = []

        high_conf = [p for p in patterns if p.auto_apply and p.confidence > 0.8]
        medium_conf = [p for p in patterns if p.needs_review]
        low_conf = [p for p in patterns if not p.auto_apply and not p.needs_review]

        for p in patterns:
            self._review_output.append(p.to_dict())

        review_data = {
            "timestamp": datetime.now().isoformat(),
            "total_patterns": len(patterns),
            "high_confidence": len(high_conf),
            "medium_confidence": len(medium_conf),
            "low_confidence": len(low_conf),
            "patterns": self._review_output,
            "workspace": str(self.workspace),
        }

        review_path = Path(self.config.review_dir)
        review_path.mkdir(parents=True, exist_ok=True)
        latest_path = review_path / "latest.json"
        latest_path.write_text(json.dumps(review_data, ensure_ascii=False, indent=2), encoding="utf-8")

        logger.info(f"Review output saved to {latest_path}")

        return {
            "total_patterns": len(patterns),
            "high_confidence": high_conf,
            "medium_confidence": medium_conf,
            "low_confidence": low_conf,
            "review_file": str(latest_path),
            "patterns": patterns,
        }

    def apply_from_review(self, confirm: bool = False) -> Dict[str, Any]:
        """Apply patterns from the latest review output."""
        review_path = Path(self.config.review_dir) / "latest.json"
        if not review_path.exists():
            logger.error(f"No review file found at {review_path}")
            return {"error": "No review file found. Run 'soulforge.py review' first."}

        try:
            review_data = json.loads(review_path.read_text(encoding="utf-8"))
            patterns = [DiscoveredPattern.from_dict(p) for p in review_data.get("patterns", [])]
        except Exception as e:
            logger.error(f"Failed to load review file: {e}")
            return {"error": f"Failed to load review file: {e}"}

        if not confirm:
            return {
                "dry_run": True,
                "total_patterns": len(patterns),
                "patterns": [p.to_dict() for p in patterns],
                "message": "Run with --confirm to apply these patterns",
            }

        return self.apply_updates(patterns, dry_run=False, backup_type="auto")

    def create_manual_backup(self) -> Dict[str, Any]:
        """Create a manual snapshot of all target files."""
        results = {"backed_up": [], "skipped": [], "errors": []}

        for target in self.config.target_files:
            target_path = self.workspace / target
            if target_path.exists():
                try:
                    self._create_backup(target_path, backup_type="manual")
                    results["backed_up"].append(target)
                except Exception as e:
                    results["errors"].append({target: str(e)})
            else:
                results["skipped"].append(target)

        return results

    def _write_changelog(self, results: Dict[str, Any]) -> None:
        """Write a changelog entry for this evolution run."""
        state_dir = Path(self.config.state_dir)
        state_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z")
        patterns = results.get("changes", [])

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

        en_path = state_dir / "CHANGELOG.md"
        if en_path.exists():
            existing = en_path.read_text(encoding="utf-8")
            parts = existing.split("---\n\n", 1)
            if len(parts) > 1:
                new_content = parts[0] + "---\n\n" + en_entry + parts[1]
            else:
                new_content = en_entry + existing
        else:
            new_content = "# SoulForge Changelog\n\n" + en_entry
        en_path.write_text(new_content, encoding="utf-8")

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
        logger.info(f"Changelog updated: {en_path}")

    def _apply_to_file(
        self,
        filename: str,
        patterns: List[DiscoveredPattern],
        dry_run: bool,
        backup_type: str = "auto"
    ) -> Dict[str, Any]:
        """Apply patterns to a single file (delegates to rollback version)."""
        return self._apply_to_file_with_rollback(filename, patterns, dry_run, backup_type)

    def _insert_content(self, file_path: Path, insertion_point: str, block: str) -> None:
        """Insert content based on insertion_point."""
        if insertion_point == "append" or not insertion_point:
            with open(file_path, "a", encoding="utf-8") as f:
                f.write("\n" + block)
            return

        if insertion_point == "top":
            existing = file_path.read_text(encoding="utf-8")
            file_path.write_text(block + "\n\n" + existing, encoding="utf-8")
            return

        if insertion_point.startswith("section:"):
            section_title = insertion_point[8:]
            self._insert_after_section(file_path, section_title, block)
            return

        with open(file_path, "a", encoding="utf-8") as f:
            f.write("\n" + block)

    def _insert_after_section(self, file_path: Path, section_title: str, block: str) -> None:
        """Insert content after a specific section."""
        content = file_path.read_text(encoding="utf-8")

        section_pattern = re.compile(
            rf"^(##\s*{re.escape(section_title)}.*)$",
            re.MULTILINE | re.IGNORECASE
        )
        match = section_pattern.search(content)

        if not match:
            logger.warning(f"Section '## {section_title}' not found in {file_path.name}, appending instead")
            with open(file_path, "a", encoding="utf-8") as f:
                f.write("\n" + block)
            return

        start_pos = match.end()
        remaining = content[start_pos:]
        next_header = re.search(r"\n##\s+", remaining)
        end_pos = start_pos + next_header.start() if next_header else len(content)

        new_content = content[:end_pos] + "\n\n" + block + content[end_pos:]
        file_path.write_text(new_content, encoding="utf-8")

    def _filter_duplicates(
        self,
        patterns: List[DiscoveredPattern],
        existing_content: str
    ) -> List[DiscoveredPattern]:
        """Filter out patterns already present in the file."""
        if not existing_content:
            return patterns

        filtered = []
        for pattern in patterns:
            content_snippet = pattern.content[:50].lower()
            summary_snippet = pattern.summary[:50].lower()

            if content_snippet in existing_content.lower():
                logger.debug(f"Skipping duplicate pattern: {pattern.summary}")
                continue
            if summary_snippet in existing_content.lower():
                logger.debug(f"Skipping similar pattern: {pattern.summary}")
                continue

            if re.search(
                rf"<!--\s*SoulForge.*-->\s*##\s*{re.escape(pattern.summary)}",
                existing_content,
                re.IGNORECASE
            ):
                logger.debug(f"Skipping already-updated pattern: {pattern.summary}")
                continue

            filtered.append(pattern)

        return filtered

    def _create_backup(self, file_path: Path, backup_type: str = "auto") -> None:
        """Create a timestamped backup of the file."""
        if not file_path.exists():
            return

        backup_dir = Path(self.config.backup_dir)
        backup_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        backup_name = f"{file_path.name}.{timestamp}.{backup_type}.bak"
        backup_path = backup_dir / backup_name

        shutil.copy2(file_path, backup_path)
        logger.info(f"Backup created: {backup_path}")

        retention = self.config.get_backup_retention(file_path.name)
        self._cleanup_old_backups(backup_dir, file_path.name, keep=retention)

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
        """Get list of backups for a file."""
        backup_dir = Path(self.config.backup_dir)
        if not backup_dir.exists():
            return []

        backups = sorted(
            backup_dir.glob(f"{filename}.*.bak"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )

        result = []
        for b in backups:
            parts = b.name.split(".")
            backup_type = parts[-2] if len(parts) >= 3 else "auto"
            result.append({
                "path": str(b),
                "timestamp": datetime.fromtimestamp(b.stat().st_mtime).isoformat(),
                "type": backup_type,
            })
        return result

    def restore_from_backup(self, filename: str, backup_path: str) -> bool:
        """Restore a file from backup."""
        try:
            backup = Path(backup_path)
            target = self.workspace / filename

            if not backup.exists():
                logger.error(f"Backup not found: {backup_path}")
                return False

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
                ip = c.get("insertion_point", "append")
                if ip != "append":
                    lines.append(f"    - {action} ({ip}): {c['pattern']}")
                else:
                    lines.append(f"    - {action}: {c['pattern']}")
            lines.append("")

        return "\n".join(lines)

    def _generate_rich_diff(
        self,
        filename: str,
        patterns: List[DiscoveredPattern]
    ) -> str:
        """
        Generate a unified-diff-style preview of what would change.

        v2.2.0: Rich dry-run preview in unified diff format.

        Args:
            filename: Target file name
            patterns: Patterns to apply

        Returns:
            Unified diff string
        """
        file_path = self.workspace / filename
        if file_path.exists():
            old_lines = file_path.read_text(encoding="utf-8").splitlines(keepends=True)
        else:
            old_lines = []

        # Simulate the new content
        new_content_lines = list(old_lines)
        for pattern in patterns:
            block = pattern.to_markdown_block()
            block_lines = block.splitlines(keepends=True)

            if pattern.insertion_point == "append":
                new_content_lines.extend(block_lines)
            elif pattern.insertion_point == "top":
                new_content_lines = block_lines + ["\n"] + new_content_lines
            elif pattern.insertion_point.startswith("section:"):
                # For section insert, just show where it would go
                section_title = pattern.insertion_point[8:]
                new_content_lines.append(f"\n# Would insert under ## {section_title}\n")
                new_content_lines.extend(["    " + l for l in block_lines])

        new_lines = new_content_lines

        # Generate unified diff header
        lines = []
        lines.append(f"--- {filename}")
        lines.append(f"+++ {filename}")

        # Simple line-by-line diff: show insertions
        old_len = len(old_lines)
        new_len = len(new_lines)

        if old_len == 0:
            # New file
            lines.append(f"@@ -0,0 +1,{new_len} @@")
            for i, l in enumerate(new_lines):
                lines.append(f"+{l.rstrip()}")
        else:
            # Changed file: show added lines with context
            # Find SoulForge block markers to highlight
            lines.append(f"@@ -{old_len} +{new_len} @@")
            for i, l in enumerate(old_lines):
                if "<!-- SoulForge Update" in l:
                    lines.append(f" {l.rstrip()}")
            for l in new_lines[-len(patterns) * 15:]:  # Show last N lines (new blocks)
                if l.strip():
                    lines.append(f"+{l.rstrip()}")

        # Show the blocks to be inserted
        lines.append("")
        lines.append("Blocks to insert:")
        lines.append("=" * 50)
        for p in patterns:
            conflict_marker = " ⚠️ CONFLICT" if p.has_conflict else ""
            lines.append(f"\n[{p.target_file}] {p.summary}{conflict_marker}")
            lines.append(f"  Insertion: {p.insertion_point}")
            lines.append(f"  Confidence: {p.confidence:.1f}")
            for block_line in p.to_markdown_block().splitlines():
                lines.append(f"    {block_line}")

        return "\n".join(lines)

    def _format_visual_changelog(self, changelog_text: str) -> str:
        """
        Format changelog as an ASCII tree visualization.

        v2.2.0: Changelog visualization.

        Parses changelog entries and renders them as a tree:
        v2.1.0 (2026-04-05)
        ├── SOUL.md
        │   └── +2 patterns (communication)
        ├── USER.md
        │   └── +1 pattern (preference)
        └── IDENTITY.md
            └── no changes

        Args:
            changelog_text: Raw changelog markdown text

        Returns:
            ASCII tree string
        """
        if not changelog_text:
            return ""

        lines = changelog_text.split("\n")
        output_lines = []
        current_version = None
        version_entries: Dict[str, Dict[str, List[str]]] = {}

        # Parse changelog into version -> file -> patterns
        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # Version header: ## [X.Y.Z] - YYYY-MM-DD
            version_match = re.match(r"##\s*\[([^\]]+)\]\s*-\s*(\d{4}-\d{2}-\d{2})", line)
            if version_match:
                current_version = version_match.group(1)
                version_date = version_match.group(2)
                version_entries[current_version] = {"_date": version_date, "_files": {}}
                i += 1
                continue

            # Bullet: - **file**: pattern
            if line.startswith("- **") and current_version:
                bullet_match = re.match(r"-\s+\*\*([^*]+)\*\*:\s*(.+)", line)
                if bullet_match:
                    filename = bullet_match.group(1).strip()
                    pattern = bullet_match.group(2).strip()
                    if filename not in version_entries[current_version]["_files"]:
                        version_entries[current_version]["_files"][filename] = []
                    version_entries[current_version]["_files"][filename].append(pattern)

            i += 1

        # Render as ASCII tree
        sorted_versions = sorted(version_entries.keys(), reverse=True)
        for v in sorted_versions[:5]:  # Show last 5 versions
            date = version_entries[v].get("_date", "")
            files = version_entries[v].get("_files", {})
            output_lines.append(f"{v} ({date})")

            if not files:
                output_lines.append("    └── no changes")
                continue

            sorted_files = sorted(files.keys())
            for idx, filename in enumerate(sorted_files):
                patterns = files[filename]
                is_last_file = (idx == len(sorted_files) - 1)
                connector = "└──" if is_last_file else "├──"
                prefix = "    " if is_last_file else "│   "

                if patterns:
                    pattern_count = len(patterns)
                    # Infer tag from first pattern if possible
                    tags_match = re.search(r"\(([^)]+)\)", patterns[0])
                    tag_str = f" ({tags_match.group(1)})" if tags_match else ""
                    output_lines.append(f"{connector} {filename}")
                    output_lines.append(f"{prefix}    └── +{pattern_count} pattern(s){tag_str}")
                else:
                    output_lines.append(f"{connector} {filename}")
                    output_lines.append(f"{prefix}    └── no changes")

        return "\n".join(output_lines)

    def get_changelog(self, lang: str = "en", visual: bool = False) -> str:
        """Get the changelog content, optionally as visual tree."""
        state_dir = Path(self.config.state_dir)
        filename = "CHANGELOG.md" if lang == "en" else "CHANGELOG.zh-CN.md"
        changelog_path = state_dir / filename

        if not changelog_path.exists():
            return ""

        content = changelog_path.read_text(encoding="utf-8")

        if visual:
            return self._format_visual_changelog(content)

        return content
