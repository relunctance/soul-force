"""
SoulForge Memory Reader

Reads memory entries from multiple sources in the agent's workspace:

1. Daily memory logs (memory/YYYY-MM-DD.md)
2. Learnings directory (.learnings/)
3. hawk-bridge vector store (optional, with incremental sync)

The reader normalizes all sources into a unified MemoryEntry format,
sorts by timestamp, and provides token-budget-aware truncation.

Key design:
- Read-only: Never modifies any source files
- Incremental: hawk-bridge source supports incremental reads via last_hawk_sync
- Token Budget: Truncates entries to stay within max_token_budget
- Safe: Gracefully skips unavailable sources
"""

import os
import json
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# Rough token estimation: ~4 chars per token for mixed Chinese/English
CHARS_PER_TOKEN = 4


def _get_tokenizer(encoding_name: str = "cl100k_base"):
    """
    Get a tiktoken encoding for accurate token counting.

    Falls back to None if tiktoken is not available.
    """
    try:
        import tiktoken
        return tiktoken.get_encoding(encoding_name)
    except ImportError:
        logger.debug("tiktoken not available, using char-based token estimation")
        return None


# Module-level tokenizer instance (lazy-loaded)
_tokenizer = None


def _tokenize_text(text: str) -> int:
    """
    Count tokens in text using tiktoken (real count) or char-based estimation (fallback).

    Args:
        text: Text to count tokens for
        encoding_name: tiktoken encoding name (default: cl100k_base)

    Returns:
        Token count (int)
    """
    global _tokenizer
    if _tokenizer is None:
        _tokenizer = _get_tokenizer()

    if _tokenizer is not None:
        try:
            return len(_tokenizer.encode(text))
        except Exception:
            pass

    # Fallback: char-based estimation
    return len(text) // CHARS_PER_TOKEN


@dataclass
class MemoryEntry:
    """A single memory entry from any source."""
    source: str
    source_type: str     # "daily_log" | "learning" | "error" | "feature_req" | "hawk_bridge"
    category: str        # "correction" | "insight" | "decision" | "preference" | "error" | etc.
    content: str
    timestamp: Optional[str] = None
    importance: float = 0.5
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return f"[{self.source_type}] {self.content[:100]}"

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "source_type": self.source_type,
            "category": self.category,
            "content": self.content,
            "timestamp": self.timestamp,
            "importance": self.importance,
            "metadata": self.metadata,
        }

    def estimated_tokens(self) -> int:
        """Estimate token count for this entry using tiktoken (real) or char-based (fallback)."""
        return _tokenize_text(self.content)


class MemoryReader:
    """
    Reads memory entries from various sources with token budget protection.

    Sources:
    - memory/YYYY-MM-DD.md: Daily conversation logs
    - .learnings/LEARNINGS.md: Corrections, insights, knowledge gaps
    - .learnings/ERRORS.md: Command failures
    - .learnings/FEATURE_REQUESTS.md: User requests
    - hawk-bridge vector store (optional): Semantic memory with incremental sync
    """

    def __init__(self, workspace: str, config):
        """
        Initialize memory reader.

        Args:
            workspace: Path to workspace directory
            config: SoulForgeConfig instance
        """
        self.workspace = Path(workspace)
        self.config = config
        self._entries: List[MemoryEntry] = []
        self._last_run: Optional[str] = None
        self._last_hawk_sync: Optional[str] = None
        self._skipped_count: int = 0
        self._estimated_tokens: int = 0

    def read_all(self, since_timestamp: Optional[str] = None) -> List[MemoryEntry]:
        """
        Read all memory sources and return unified list of entries.

        Args:
            since_timestamp: If provided, only return entries newer than this ISO timestamp.
                            If None, reads all entries (subject to token budget).

        Returns:
            List of MemoryEntry objects sorted by timestamp (newest first),
            truncated to fit within max_token_budget.
        """
        self._entries = []
        self._skipped_count = 0
        self._estimated_tokens = 0

        # Load last_run timestamp from config
        self._last_run = self.config.get_last_run_timestamp()
        if since_timestamp is None and self._last_run:
            since_timestamp = self._last_run

        self._last_hawk_sync = self.config.get_last_hawk_sync()

        # Read daily memory logs
        new_entries = self._read_daily_logs(since_timestamp)
        self._entries.extend(new_entries)

        # Read learnings
        new_entries = self._read_learnings(since_timestamp)
        self._entries.extend(new_entries)

        # Read hawk-bridge with incremental sync
        if self.config.get("hawk_bridge_enabled", True):
            self._read_hawk_bridge()

        # Sort by timestamp (newest first) — prioritize recent entries within budget
        self._entries.sort(
            key=lambda e: e.timestamp or "1970-01-01",
            reverse=True
        )

        # Apply token budget truncation
        self._apply_token_budget()

        logger.info(f"Read {len(self._entries)} memory entries from all sources "
                    f"(~{self._estimated_tokens} tokens, skipped {self._skipped_count})")
        if since_timestamp:
            logger.info(f"  (incremental since {since_timestamp})")

        return self._entries

    def _apply_token_budget(self) -> None:
        """
        Truncate entries to fit within max_token_budget.

        Strategy: Iterate newest-first, keep entries until budget is exhausted.
        Entries that don't fit are skipped (but counted).
        """
        max_tokens = self.config.max_token_budget
        if max_tokens <= 0:
            max_tokens = 4096

        kept = []
        for entry in self._entries:
            entry_tokens = entry.estimated_tokens()
            if self._estimated_tokens + entry_tokens <= max_tokens:
                kept.append(entry)
                self._estimated_tokens += entry_tokens
            else:
                self._skipped_count += 1
                logger.debug(f"Skipped (over budget): {entry.source} "
                             f"(~{entry_tokens} tokens, "
                             f"budget {self._estimated_tokens}/{max_tokens})")

        self._entries = kept

    def _is_newer_than(self, entry_timestamp: Optional[str], since: Optional[str]) -> bool:
        """Check if an entry is newer than the since timestamp."""
        if since is None:
            return True
        if entry_timestamp is None:
            return True
        return entry_timestamp > since

    def _read_daily_logs(self, since: Optional[str] = None) -> List[MemoryEntry]:
        """Read memory/*.md daily logs."""
        entries = []
        memory_dir = self.workspace / "memory"
        if not memory_dir.exists():
            logger.debug(f"Memory directory not found: {memory_dir}")
            return entries

        for md_file in sorted(memory_dir.glob("*.md"), reverse=True):
            if md_file.name in ["BOOTSTRAP.md"]:
                continue

            file_timestamp = md_file.stem  # YYYY-MM-DD

            if since and file_timestamp <= since[:10]:
                logger.debug(f"Skipping older daily log: {md_file.name}")
                continue

            try:
                content = md_file.read_text(encoding="utf-8")
                entry = MemoryEntry(
                    source=str(md_file.relative_to(self.workspace)),
                    source_type="daily_log",
                    category="conversation",
                    content=self._extract_text_content(content),
                    timestamp=file_timestamp,
                    importance=0.6,
                    metadata={"file": str(md_file.name)}
                )
                entries.append(entry)
            except Exception as e:
                logger.warning(f"Failed to read {md_file}: {e}")

        return entries

    def _read_learnings(self, since: Optional[str] = None) -> List[MemoryEntry]:
        """Read .learnings/ directory files."""
        entries = []
        learnings_dir = self.workspace / ".learnings"
        if not learnings_dir.exists():
            logger.debug(f"Learnings directory not found: {learnings_dir}")
            return entries

        for fname, parser in [
            ("LEARNINGS.md", self._parse_learnings_md),
            ("ERRORS.md", self._parse_errors_md),
            ("FEATURE_REQUESTS.md", self._parse_feature_requests_md),
        ]:
            fpath = learnings_dir / fname
            if fpath.exists():
                entries.extend(parser(fpath, since))

        return entries

    def _parse_learnings_md(self, file_path: Path, since: Optional[str] = None) -> List[MemoryEntry]:
        """Parse LEARNINGS.md format."""
        entries = []
        try:
            content = file_path.read_text(encoding="utf-8")
            sections = content.split("\n---\n")
            for section in sections:
                if not section.strip() or section.startswith("#"):
                    continue
                section_timestamp = None
                for line in section.split("\n"):
                    if "**Time**:" in line or "Time:" in line:
                        ts_part = line.split("**Time**:")[-1].split("Time:")[-1].strip()
                        section_timestamp = ts_part[:10] if ts_part else None
                        break

                if since and section_timestamp and section_timestamp <= since[:10]:
                    continue

                lines = section.strip().split("\n")
                category = "insight"
                for line in lines:
                    if line.startswith("## "):
                        header = line[3:].lower()
                        if "correction" in header:
                            category = "correction"
                        elif "knowledge_gap" in header:
                            category = "knowledge_gap"
                        elif "best_practice" in header:
                            category = "best_practice"
                        break

                text_content = self._extract_text_content(section)
                if text_content.strip():
                    entry = MemoryEntry(
                        source=str(file_path.relative_to(self.workspace)),
                        source_type="learning",
                        category=category,
                        content=text_content,
                        timestamp=section_timestamp,
                        importance=0.8 if category == "correction" else 0.6,
                        metadata={}
                    )
                    entries.append(entry)
        except Exception as e:
            logger.warning(f"Failed to parse {file_path}: {e}")
        return entries

    def _parse_errors_md(self, file_path: Path, since: Optional[str] = None) -> List[MemoryEntry]:
        """Parse ERRORS.md format."""
        entries = []
        try:
            content = file_path.read_text(encoding="utf-8")
            sections = content.split("\n---\n")
            for section in sections:
                if not section.strip() or section.startswith("#"):
                    continue
                section_timestamp = None
                for line in section.split("\n"):
                    if "**Time**:" in line or "Time:" in line:
                        ts_part = line.split("**Time**:")[-1].split("Time:")[-1].strip()
                        section_timestamp = ts_part[:10] if ts_part else None
                        break

                if since and section_timestamp and section_timestamp <= since[:10]:
                    continue

                text_content = self._extract_text_content(section)
                if text_content.strip():
                    entry = MemoryEntry(
                        source=str(file_path.relative_to(self.workspace)),
                        source_type="error",
                        category="error",
                        content=text_content,
                        timestamp=section_timestamp,
                        importance=0.9,
                        metadata={}
                    )
                    entries.append(entry)
        except Exception as e:
            logger.warning(f"Failed to parse {file_path}: {e}")
        return entries

    def _parse_feature_requests_md(self, file_path: Path, since: Optional[str] = None) -> List[MemoryEntry]:
        """Parse FEATURE_REQUESTS.md format."""
        entries = []
        try:
            content = file_path.read_text(encoding="utf-8")
            sections = content.split("\n---\n")
            for section in sections:
                if not section.strip() or section.startswith("#"):
                    continue
                section_timestamp = None
                for line in section.split("\n"):
                    if "**Time**:" in line or "Time:" in line:
                        ts_part = line.split("**Time**:")[-1].split("Time:")[-1].strip()
                        section_timestamp = ts_part[:10] if ts_part else None
                        break

                if since and section_timestamp and section_timestamp <= since[:10]:
                    continue

                text_content = self._extract_text_content(section)
                if text_content.strip():
                    entry = MemoryEntry(
                        source=str(file_path.relative_to(self.workspace)),
                        source_type="feature_request",
                        category="feature_request",
                        content=text_content,
                        timestamp=section_timestamp,
                        importance=0.5,
                        metadata={}
                    )
                    entries.append(entry)
        except Exception as e:
            logger.warning(f"Failed to parse {file_path}: {e}")
        return entries

    def _read_hawk_bridge(self) -> None:
        """
        Read from hawk-bridge LanceDB vector store with incremental sync.

        Only fetches entries updated since last_hawk_sync timestamp.
        Updates last_hawk_sync after successful read.
        """
        try:
            import sys
            hawk_path = self.config.get("hawk_bridge_path")
            if not hawk_path:
                for candidate in [
                    self.workspace.parent / "context-hawk" / "hawk",
                    Path("~/.openclaw/workspace/context-hawk/hawk").expanduser(),
                ]:
                    if candidate.exists():
                        hawk_path = str(candidate)
                        break

            if not hawk_path or not Path(hawk_path).exists():
                logger.debug("hawk-bridge path not found, skipping vector memory")
                return

            sys.path.insert(0, hawk_path)

            db_path = self.config.get("hawk_db_path", "~/.hawk/lancedb")
            table_name = self.config.get("hawk_table_name", "hawk_memories")

            import lancedb
            db = lancedb.connect(str(Path(db_path).expanduser()))
            if table_name not in db.table_names():
                return

            table = db.open_table(table_name)

            # Incremental: query only entries updated since last_hawk_sync
            if self._last_hawk_sync:
                try:
                    # Use SQL-like filter for updated_at > last_sync
                    import pyarrow as pa
                    query_vec = table.search().where(
                        f"updated_at > '{self._last_hawk_sync}'"
                    ).limit(50).to_arrow()
                    count = len(query_vec) if hasattr(query_vec, '__len__') else 0
                except Exception:
                    # Fallback: just count total
                    count = min(table.count_rows(), 50)
                    query_vec = table.search().limit(count).to_arrow()
            else:
                # First time: read last 50 entries
                count = min(table.count_rows(), 50)
                query_vec = table.search().limit(count).to_arrow()

            if count > 0:
                logger.info(f"Read {count} entries from hawk-bridge "
                            f"(since={self._last_hawk_sync})")
                try:
                    # Try to convert to dict-like rows
                    if hasattr(query_vec, 'to_pydict'):
                        rows = query_vec.to_pydict()
                        for i in range(len(rows.get("content", []))):
                            row = {k: v[i] if isinstance(v, list) else v for k, v in rows.items()}
                            entry = MemoryEntry(
                                source="hawk-bridge",
                                source_type="hawk_bridge",
                                category=row.get("category", "semantic"),
                                content=row.get("content", str(row)),
                                timestamp=row.get("updated_at") or row.get("created_at"),
                                importance=row.get("importance", 0.6),
                                metadata=row.get("metadata", {})
                            )
                            self._entries.append(entry)
                    elif hasattr(query_vec, '__iter__'):
                        for row in query_vec:
                            entry = MemoryEntry(
                                source="hawk-bridge",
                                source_type="hawk_bridge",
                                category="semantic",
                                content=str(row),
                                timestamp=None,
                                importance=0.6,
                                metadata={}
                            )
                            self._entries.append(entry)
                except Exception as e:
                    logger.warning(f"Failed to parse hawk-bridge rows: {e}")

                # Update last_hawk_sync timestamp
                self.config.set_last_hawk_sync(datetime.now().isoformat())

        except ImportError:
            logger.debug("lancedb not available, skipping hawk-bridge vector store")
        except Exception as e:
            logger.warning(f"Failed to read hawk-bridge: {e}")

    def _extract_text_content(self, markdown_text: str) -> str:
        """Extract plain text content from markdown."""
        lines = markdown_text.split("\n")
        result_lines = []
        in_code_block = False

        for line in lines:
            if line.strip().startswith("```"):
                in_code_block = not in_code_block
                continue
            if in_code_block:
                continue
            if line.strip().startswith("#"):
                continue
            stripped = line.strip()
            if stripped.startswith("- ") or stripped.startswith("* "):
                stripped = stripped[2:]
            elif stripped.startswith("##") or stripped.startswith("**"):
                continue
            stripped = stripped.replace("**", "").replace("*", "").replace("__", "")
            if ":" in stripped and len(stripped) <= 100:
                if any(stripped.startswith(k) for k in ["Source:", "Tags:", "Area:", "Pattern-Key:", "Time:"]):
                    continue
            if stripped.strip():
                result_lines.append(stripped.strip())

        return " ".join(result_lines)

    def get_entries_by_category(self, category: str) -> List[MemoryEntry]:
        """Get all entries matching a specific category."""
        return [e for e in self._entries if e.category == category]

    def get_recent_entries(self, days: int = 7) -> List[MemoryEntry]:
        """Get entries from the last N days."""
        cutoff = (datetime.now() - __import__("datetime").timedelta(days=days)).strftime("%Y-%m-%d")
        return [e for e in self._entries if e.timestamp and e.timestamp >= cutoff]

    def summarize(self) -> Dict[str, Any]:
        """Get a summary of all memory sources."""
        return {
            "total_entries": len(self._entries),
            "by_source_type": self._count_by("source_type"),
            "by_category": self._count_by("category"),
            "sources": list(set(e.source for e in self._entries)),
            "is_incremental": self._last_run is not None,
            "last_run": self._last_run,
            "last_hawk_sync": self._last_hawk_sync,
            "estimated_tokens": self._estimated_tokens,
            "max_token_budget": self.config.max_token_budget,
            "skipped_entries": self._skipped_count,
        }

    def _count_by(self, attr: str) -> Dict[str, int]:
        """Count entries by a specific attribute."""
        counts = {}
        for entry in self._entries:
            key = getattr(entry, attr, "unknown")
            counts[key] = counts.get(key, 0) + 1
        return counts
