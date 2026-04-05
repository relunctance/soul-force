"""
SoulForge Pattern Analyzer

Uses the configured LLM to analyze memory entries and discover patterns.
Features:
- Schema validation via pydantic (ProposedUpdate, DiscoveredPattern)
- Graceful degradation: on schema failure, saves raw output to review/failed/
- Pattern expiry: DiscoveredPattern.expires_at field
- Retry logic: one retry on schema validation failure
"""

import json
import logging
import re
import subprocess
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from soulforge.memory_reader import MemoryEntry
from soulforge.schema import validate_proposed_updates_batch, ProposedUpdate

logger = logging.getLogger(__name__)

CONFIDENCE_HIGH = 0.8
CONFIDENCE_MEDIUM = 0.5
CONFIDENCE_LOW = 0.5


@dataclass
class DiscoveredPattern:
    """A pattern discovered from memory analysis."""
    pattern_id: str
    target_file: str
    update_type: str
    category: str
    summary: str
    content: str
    confidence: float
    evidence_count: int
    source_entries: List[str]
    suggested_section: Optional[str] = None
    insertion_point: str = "append"
    auto_apply: bool = False
    needs_review: bool = False
    expires_at: Optional[str] = None  # ISO timestamp when pattern expires
    tags: List[str] = field(default_factory=list)  # v2.2.0: pattern tags for filtering
    conflict_with: Optional[str] = None  # v2.2.0: ID of conflicting pattern
    has_conflict: bool = False  # v2.2.0: whether this pattern conflicts with another

    def __post_init__(self):
        if self.confidence > CONFIDENCE_HIGH:
            self.auto_apply = True
            self.needs_review = False
        elif self.confidence >= CONFIDENCE_MEDIUM:
            self.auto_apply = False
            self.needs_review = True
        else:
            self.auto_apply = False
            self.needs_review = False

    def to_markdown_block(self) -> str:
        """Format as a SoulForge update block for insertion."""
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00")
        sources = ", ".join(self.source_entries[:3])
        if len(self.source_entries) > 3:
            sources += f" (+{len(self.source_entries) - 3} more)"

        conf_label = "High" if self.confidence > 0.7 else "Medium" if self.confidence > 0.4 else "Low"

        expires_line = ""
        if self.expires_at:
            expires_line = f"\n**Expires**: {self.expires_at[:10]}"

        tags_line = ""
        if self.tags:
            tags_line = f"\n**Tags**: {', '.join(self.tags)}"

        conflict_line = ""
        if self.has_conflict:
            conflict_line = "\n**⚠️ CONFLICT**: This pattern conflicts with another pattern in the review."

        return f"""
<!-- SoulForge Update | {timestamp} -->
## {self.summary}

**Source**: {sources}
**Pattern Type**: {self.category}
**Confidence**: {conf_label} (observed {self.evidence_count} times)
**Insertion**: {self.insertion_point}{expires_line}{tags_line}{conflict_line}

**Content**:
{self.content}

<!-- /SoulForge Update -->"""

    def to_dict(self) -> dict:
        return {
            "pattern_id": self.pattern_id,
            "target_file": self.target_file,
            "update_type": self.update_type,
            "category": self.category,
            "summary": self.summary,
            "content": self.content,
            "confidence": self.confidence,
            "evidence_count": self.evidence_count,
            "source_entries": self.source_entries,
            "suggested_section": self.suggested_section,
            "insertion_point": self.insertion_point,
            "auto_apply": self.auto_apply,
            "needs_review": self.needs_review,
            "expires_at": self.expires_at,
            "tags": self.tags,
            "conflict_with": self.conflict_with,
            "has_conflict": self.has_conflict,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DiscoveredPattern":
        return cls(
            pattern_id=data.get("pattern_id", ""),
            target_file=data.get("target_file", ""),
            update_type=data.get("update_type", ""),
            category=data.get("category", "general"),
            summary=data.get("summary", "Untitled pattern"),
            content=data.get("content", ""),
            confidence=data.get("confidence", 0.5),
            evidence_count=data.get("evidence_count", 1),
            source_entries=data.get("source_entries", []),
            suggested_section=data.get("suggested_section"),
            insertion_point=data.get("insertion_point", "append"),
            auto_apply=data.get("auto_apply", False),
            needs_review=data.get("needs_review", False),
            expires_at=data.get("expires_at"),
            tags=data.get("tags", []),
            conflict_with=data.get("conflict_with"),
            has_conflict=data.get("has_conflict", False),
        )

    @classmethod
    def from_proposed_update(cls, update: ProposedUpdate) -> "DiscoveredPattern":
        """Create a DiscoveredPattern from a validated ProposedUpdate."""
        insertion_point = update.insertion_point
        if (not insertion_point or insertion_point == "append") and update.suggested_section:
            insertion_point = f"section:{update.suggested_section}"

        return cls(
            pattern_id=cls._generate_pattern_id(),
            target_file=update.target_file,
            update_type=update.update_type,
            category=update.category,
            summary=update.summary,
            content=update.content,
            confidence=update.confidence,
            evidence_count=update.evidence_count,
            source_entries=update.source_entries,
            suggested_section=update.suggested_section,
            insertion_point=insertion_point,
            tags=update.tags,
            conflict_with=update.conflict_with,
        )

    @staticmethod
    def _generate_pattern_id() -> str:
        import uuid
        return f"pattern_{uuid.uuid4().hex[:8]}"


class PatternAnalyzer:
    """
    Analyzes memory entries to discover patterns.

    Features:
    - Schema validation via pydantic ProposedUpdate
    - One retry on validation failure
    - Falls back to raw output in review/failed/ on persistent failure
    """

    SYSTEM_PROMPT = """You are SoulForge, an AI agent memory evolution analyzer.
Your task is to analyze memory entries and identify patterns that should be promoted to identity files.

You examine:
- Daily conversation logs (what the user said, how they reacted)
- Learning records (corrections, insights, knowledge gaps)
- Error records (what went wrong)
- Feature requests (what the user wanted)

For each pattern you find, you determine:
1. WHICH file to update (SOUL.md, USER.md, IDENTITY.md, MEMORY.md, AGENTS.md, TOOLS.md)
2. WHAT content to add
3. WHERE in the file it should go (insertion_point: "append", "section:{title}", or "top")
4. HOW confident you are (based on evidence count and clarity)
5. WHEN (if ever) this pattern should expire (expires_at in ISO format, e.g. "2026-06-01" or null)

Update target guidelines:
- SOUL.md: Behavioral patterns, communication style, principles, boundaries
- USER.md: User preferences, projects, habits, working style
- IDENTITY.md: Role changes, team structure, responsibilities
- MEMORY.md: Important decisions, milestones, lessons learned
- AGENTS.md: Team workflow patterns, delegation rules
- TOOLS.md: Tool usage心得, integration patterns, workarounds

Insertion point rules:
- "append": Add to end of file (default for most updates)
- "section:{title}": Insert under the ## {title} section in the file
- "top": Insert at the very beginning of the file

Expiry rules:
- Set expires_at to null for permanent patterns
- Set expires_at to an ISO date (YYYY-MM-DD) for time-limited patterns
- e.g., a project that ends in June 2026: expires_at="2026-06-30"
- Patterns should NOT expire unless there's a specific reason

Rules:
- Only report patterns with 2+ occurrences (high confidence)
- Report in JSON format (one "proposed_updates" array)
- If no significant patterns found, return empty updates array
- Always write in the language that matches existing content (detect from target file)
- Content should be concise, actionable, and specific (max 500 chars)
- Set confidence: >0.8 for strong patterns (2+ clear occurrences), 0.5-0.8 for partial, <0.5 for weak
- Determine insertion_point based on where content logically belongs
"""

    USER_PROMPT_TEMPLATE = """Analyze these memory entries and find patterns worth promoting to identity files.

## Memory Entries (last 7 days)

{memory_entries_text}

## Existing Content in Target Files

Check what already exists to avoid duplication:

{existing_content}

## Instructions

1. Find patterns that appear 2+ times
2. Check if similar content already exists in target files
3. Generate concise, specific updates (not generic statements)
4. Determine appropriate insertion_point for each pattern
5. Set expires_at for time-limited patterns (null for permanent)
6. Format output as JSON

## Output Format

Return a JSON object with this structure:
{{
  "proposed_updates": [
    {{
      "target_file": "SOUL.md",
      "update_type": "SOUL",
      "category": "behavior",
      "summary": "Brief one-line description",
      "content": "The content to add (2-4 sentences)",
      "confidence": 0.8,
      "evidence_count": 4,
      "source_entries": ["memory/2026-04-04.md", ".learnings/LEARNINGS.md"],
      "suggested_section": "沟通方式",
      "insertion_point": "section:沟通方式",
      "expires_at": null
    }}
  ],
  "analysis_summary": "Brief explanation of what you found",
  "patterns_declined": [
    {{"reason": "already exists in SOUL.md as...", "entries": [...]}}
  ]
}}

Return ONLY JSON, no other text."""

    def __init__(self, config, force_apply: bool = False):
        self.config = config
        self.force_apply = force_apply
        self._model = config.get("model") or "MiniMax-M2"
        self._schema_retry_count = 0

    def analyze(
        self,
        entries: List[MemoryEntry],
        existing_content: Dict[str, str]
    ) -> List[DiscoveredPattern]:
        """Analyze memory entries and return patterns to update."""
        if not entries:
            logger.info("No entries to analyze")
            return []

        memory_text = self._prepare_entries_text(entries)
        user_prompt = self.USER_PROMPT_TEMPLATE.format(
            memory_entries_text=memory_text,
            existing_content=self._format_existing_content(existing_content)
        )

        response = self._call_llm(self.SYSTEM_PROMPT, user_prompt)

        # Parse with schema validation + retry
        patterns = self._parse_with_validation(response)

        if not self.force_apply:
            patterns = self._filter_by_confidence(patterns)

        # v2.2.0: Detect conflicts between patterns
        patterns = self._detect_conflicts(patterns)

        logger.info(f"Analysis complete: {len(patterns)} patterns discovered")
        return patterns

    def _parse_with_validation(self, response_text: str) -> List[DiscoveredPattern]:
        """
        Parse LLM response with schema validation.

        1. Try to parse JSON and validate against ProposedUpdate schema
        2. On validation failure, retry once
        3. On persistent failure, save raw output to review/failed/ and return empty

        Args:
            response_text: Raw LLM response text

        Returns:
            List of DiscoveredPattern objects
        """
        # First parse attempt
        parsed, raw_data = self._try_parse(response_text)
        if parsed is None:
            return []

        # Validate proposed_updates against schema
        valid_updates, invalid_items = validate_proposed_updates_batch(parsed)

        if invalid_items and self._schema_retry_count == 0:
            logger.warning(f"Schema validation failed for {len(invalid_items)} items, retrying...")
            self._schema_retry_count += 1
            # Retry once more with same raw text
            return self._parse_with_validation(response_text)

        if invalid_items:
            # Persistent failure: save raw output
            self._save_failed_output(response_text, invalid_items)
            logger.warning(f"Schema validation failed for {len(invalid_items)} items "
                           f"after retry. Raw output saved to review/failed/")

        # Convert valid ProposedUpdate → DiscoveredPattern
        patterns = [DiscoveredPattern.from_proposed_update(u) for u in valid_updates]
        return patterns

    def _try_parse(self, response_text: str) -> tuple[Optional[dict], str]:
        """Try to extract JSON from response text."""
        try:
            json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                start = response_text.find("{")
                end = response_text.rfind("}") + 1
                if start != -1 and end > start:
                    json_str = response_text[start:end]
                else:
                    json_str = response_text
            return json.loads(json_str), json_str
        except json.JSONDecodeError as e:
            logger.warning(f"JSON decode error: {e}")
            self._save_failed_output(response_text, [{"error": str(e)}])
            return None, response_text

    def _save_failed_output(self, response_text: str, errors: list) -> None:
        """Save failed LLM output to review/failed/ for manual review."""
        try:
            from pathlib import Path
            failed_dir = Path(self.config.review_failed_dir)
            failed_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            failed_file = failed_dir / f"failed_{timestamp}.txt"
            content = (
                f"# SoulForge Schema Validation Failed\n"
                f"# Timestamp: {datetime.now().isoformat()}\n"
                f"# Errors: {json.dumps(errors, ensure_ascii=False)}\n\n"
                f"# Raw LLM Response:\n"
                f"{response_text}"
            )
            failed_file.write_text(content, encoding="utf-8")
            logger.info(f"Failed output saved to {failed_file}")
        except Exception as e:
            logger.error(f"Failed to save failed output: {e}")

    def _prepare_entries_text(self, entries: List[MemoryEntry]) -> str:
        """Prepare memory entries as text for the prompt."""
        lines = []
        for i, entry in enumerate(entries[:100]):
            lines.append(f"[{i+1}] Source: {entry.source} | Type: {entry.source_type} | Category: {entry.category}")
            lines.append(f"    Content: {entry.content[:300]}")
            if entry.timestamp:
                lines.append(f"    Time: {entry.timestamp}")
            lines.append("")
        return "\n".join(lines)

    def _format_existing_content(self, existing_content: Dict[str, str]) -> str:
        """Format existing content for the prompt."""
        if not existing_content:
            return "No existing content found."
        lines = []
        for filename, content in existing_content.items():
            lines.append(f"\n### {filename}")
            lines.append(content[:1500])
            if len(content) > 1500:
                lines.append("...(truncated)...")
        return "\n".join(lines)

    def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """Call the configured LLM via OpenClaw exec tool."""
        import tempfile, os as _os
        from pathlib import Path as _Path

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        model = self._model

        # Write messages to a temp file to avoid quoting issues
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False
        ) as msg_file:
            json.dump(messages, msg_file, ensure_ascii=False)
            msg_path = msg_file.name

        try:
            script = """
import json, sys, urllib.request, urllib.error
from pathlib import Path

with open('%s') as f:
    messages = json.load(f)
model = '%s'

openclaw_cfg = Path.home() / ".openclaw" / "openclaw.json"
api_key, base_url = "", "https://api.minimax.chat/v1"

if openclaw_cfg.exists():
    try:
        with open(openclaw_cfg) as f:
            cfg = json.load(f)
        providers = cfg.get("providers", {})
        for nm, p in providers.items():
            if isinstance(p, dict):
                k = p.get("apiKey") or p.get("api_key")
                u = p.get("baseUrl") or p.get("base_url")
                if k: api_key = k
                if u: base_url = u.rstrip("/")
    except Exception:
        pass

import os as _e
if not api_key:
    api_key = _e.environ.get("OPENAI_API_KEY", _e.environ.get("MINIMAX_API_KEY", ""))

if not api_key:
    print('{"proposed_updates": [], "analysis_summary": "No API key configured"}')
    sys.exit(0)

url = base_url + "/chat/completions"
payload = json.dumps({"messages": messages, "model": model, "temperature": 0.3, "max_tokens": 4096}).encode("utf-8")
headers = {"Authorization": "Bearer " + api_key, "Content-Type": "application/json"}
req = urllib.request.Request(url, data=payload, headers=headers, method="POST")

try:
    with urllib.request.urlopen(req, timeout=90) as resp:
        rd = json.loads(resp.read().decode("utf-8"))
        content = rd.get("choices", [{}])[0].get("message", {}).get("content", "")
        print(content)
except urllib.error.HTTPError as e:
    print('{"proposed_updates": [], "analysis_summary": "API error: " + str(e.code)}')
except Exception as e:
    print('{"proposed_updates": [], "analysis_summary": "Request failed: " + str(e)}')
""" % (msg_path, model)

            result = subprocess.run(
                ["python3", "-c", script],
                capture_output=True,
                text=True,
                timeout=90,
                cwd=str(_Path.home())
            )
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                logger.error(f"LLM call script failed: {result.stderr}")
                return '{"proposed_updates": [], "analysis_summary": "Script execution failed"}'
        except subprocess.TimeoutExpired:
            logger.error("LLM call timed out")
            return '{"proposed_updates": [], "analysis_summary": "Request timed out"}'
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return '{"proposed_updates": [], "analysis_summary": "Request failed"}'
        finally:
            try:
                _os.unlink(msg_path)
            except Exception:
                pass

    def _filter_by_confidence(self, patterns: List[DiscoveredPattern]) -> List[DiscoveredPattern]:
        """Filter patterns by confidence threshold."""
        filtered = []
        for p in patterns:
            if p.confidence >= CONFIDENCE_LOW:
                filtered.append(p)
            else:
                logger.debug(f"Dropping low-confidence pattern: {p.summary} ({p.confidence})")
        return filtered

    def filter_by_threshold(
        self,
        patterns: List[DiscoveredPattern],
        threshold: Optional[int] = None
    ) -> List[DiscoveredPattern]:
        if threshold is None:
            threshold = self.config.trigger_threshold
        return [p for p in patterns if p.evidence_count >= threshold]

    def filter_auto_apply(self, patterns: List[DiscoveredPattern]) -> List[DiscoveredPattern]:
        return [p for p in patterns if p.auto_apply]

    def filter_needs_review(self, patterns: List[DiscoveredPattern]) -> List[DiscoveredPattern]:
        return [p for p in patterns if p.needs_review]

    def separate_by_confidence(
        self,
        patterns: List[DiscoveredPattern]
    ) -> Dict[str, List[DiscoveredPattern]]:
        result = {"high": [], "medium": [], "low": []}
        for p in patterns:
            if p.confidence > CONFIDENCE_HIGH:
                result["high"].append(p)
            elif p.confidence >= CONFIDENCE_MEDIUM:
                result["medium"].append(p)
            else:
                result["low"].append(p)
        return result

    def filter_expired(self, patterns: List[DiscoveredPattern]) -> List[DiscoveredPattern]:
        """Remove patterns that have expired (expires_at < now)."""
        from datetime import datetime
        now = datetime.now()
        active = []
        for p in patterns:
            if p.expires_at is None:
                active.append(p)
                continue
            try:
                exp_date = datetime.fromisoformat(p.expires_at.replace("Z", "+00:00"))
                if exp_date > now:
                    active.append(p)
                else:
                    logger.debug(f"Dropping expired pattern: {p.summary} (expired {p.expires_at})")
            except ValueError:
                # Can't parse expiry date, keep it
                active.append(p)
        return active

    def _detect_conflicts(self, patterns: List[DiscoveredPattern]) -> List[DiscoveredPattern]:
        """
        Detect conflicting patterns: same target, opposite advice.

        Two patterns conflict if:
        1. They target the same file
        2. Their content or advice is semantically opposite

        Uses simple heuristics:
        - Same target_file AND same suggested_section (or same insertion_point)
        - One says positive about X, another says negative about X (keyword-based)
        - Content similarity but with negation keywords

        Args:
            patterns: List of DiscoveredPattern objects

        Returns:
            List with conflict flags set on conflicting patterns
        """
        # Group by target file
        by_file: Dict[str, List[DiscoveredPattern]] = {}
        for p in patterns:
            key = f"{p.target_file}::{p.insertion_point}"
            if key not in by_file:
                by_file[key] = []
            by_file[key].append(p)

        negation_keywords = [
            "not ", "don't ", "don't ", "never ", "no ", "avoid ",
            "shouldn't ", "couldn't ", "won't ", "can't ",
            "stop ", "quit ", "禁止", "不要", "别", "从不", "不能",
        ]

        for key, file_patterns in by_file.items():
            if len(file_patterns) < 2:
                continue

            for i, p1 in enumerate(file_patterns):
                for p2 in file_patterns[i + 1:]:
                    # Check if content is contradictory
                    c1_lower = p1.content.lower()
                    c2_lower = p2.content.lower()

                    # Find negation keywords in content
                    p1_has_neg = any(kw in c1_lower for kw in negation_keywords)
                    p2_has_neg = any(kw in c2_lower for kw in negation_keywords)

                    # If one has negation and they're about similar topics, potential conflict
                    content_words1 = set(c1_lower.split()) & set(c2_lower.split())
                    overlap = len(content_words1) / max(len(set(c1_lower.split())), 1)

                    if overlap > 0.3 and p1_has_neg != p2_has_neg:
                        # Mark both as conflicting
                        p1.has_conflict = True
                        p2.has_conflict = True
                        p1.conflict_with = p2.pattern_id
                        p2.conflict_with = p1.pattern_id
                        logger.warning(
                            f"Conflict detected: '{p1.summary}' <-> '{p2.summary}' "
                            f"(target: {p1.target_file}, overlap: {overlap:.1%})"
                        )

        return patterns

    def filter_by_tag(self, patterns: List[DiscoveredPattern], tag: str) -> List[DiscoveredPattern]:
        """Filter patterns by tag."""
        return [p for p in patterns if tag in p.tags]

    def filter_by_tags(self, patterns: List[DiscoveredPattern], tags: List[str], match_all: bool = False) -> List[DiscoveredPattern]:
        """
        Filter patterns by multiple tags.

        Args:
            patterns: List of patterns
            tags: Tags to filter by
            match_all: If True, pattern must have all tags; if False, any tag matches
        """
        if match_all:
            return [p for p in patterns if all(t in p.tags for t in tags)]
        return [p for p in patterns if any(t in p.tags for t in tags)]

    def filter_conflicts(self, patterns: List[DiscoveredPattern], include: bool = True) -> List[DiscoveredPattern]:
        """Filter patterns by conflict status."""
        if include:
            return [p for p in patterns if p.has_conflict]
        return [p for p in patterns if not p.has_conflict]

    def ask(
        self,
        question: str,
        patterns: List[DiscoveredPattern],
        memories: List[MemoryEntry],
    ) -> str:
        """
        Answer a natural language question about the agent's identity/memory.

        Uses the LLM to synthesize an answer from existing patterns and memories.
        Does NOT write any files.

        Args:
            question: Natural language question
            patterns: List of DiscoveredPattern from recent analysis
            memories: List of MemoryEntry for additional context

        Returns:
            Natural language answer string
        """
        # Build context from patterns
        patterns_text = []
        for p in patterns:
            tags_str = f" [Tags: {', '.join(p.tags)}]" if p.tags else ""
            conflict_str = " ⚠️ CONFLICT" if p.has_conflict else ""
            patterns_text.append(
                f"- [{p.target_file}] {p.summary}{tags_str}{conflict_str}\n"
                f"  Content: {p.content[:200]}\n"
                f"  Confidence: {p.confidence:.1f} | Insertion: {p.insertion_point}"
            )

        patterns_context = "\n".join(patterns_text) if patterns_text else "No patterns found."

        # Build context from memories (limited)
        memories_text = []
        for m in memories[:20]:
            memories_text.append(f"- [{m.source_type}] {m.content[:150]}")
        memories_context = "\n".join(memories_text) if memories_text else "No memory entries found."

        system_prompt = """You are SoulForge, an AI identity analyst. Your task is to answer
questions about an AI agent's identity, behavior patterns, and memory by synthesizing
information from provided patterns and memory entries.

Answer based ONLY on the provided context. Do not make up information.
If the answer is not in the context, say "I don't have enough information to answer that."
Be concise and helpful. Respond in the same language as the question."""

        user_prompt = f"""Question: {question}

## Known Patterns (from recent SoulForge analysis):

{patterns_context}

## Recent Memory Entries:

{memories_context}

Answer the question based on the context above."""

        response = self._call_llm(system_prompt, user_prompt)
        return response.strip()
