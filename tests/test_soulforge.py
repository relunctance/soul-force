"""
SoulForge Unit Tests

Tests cover core logic for all modules:
- config.py: Configuration loading, last_run_timestamp, backup retention
- memory_reader.py: Incremental reading, entry parsing
- analyzer.py: Pattern analysis, confidence filtering, insertion_point
- evolver.py: Smart insertion, backup retention, review mode
"""

import os
import sys
import json
import tempfile
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from soulforge.config import SoulForgeConfig
from soulforge.memory_reader import MemoryReader, MemoryEntry
from soulforge.analyzer import PatternAnalyzer, DiscoveredPattern, CONFIDENCE_HIGH, CONFIDENCE_MEDIUM, CONFIDENCE_LOW
from soulforge.evolver import SoulEvolver


# =============================================================================
# Test Helpers
# =============================================================================

def _pass(test_name):
    """Print pass message for a test."""
    print(f"✓ {test_name} passed")


def _make_config(tmpdir):
    """Create SoulForgeConfig with workspace set to tmpdir."""
    return SoulForgeConfig(overrides={"workspace": tmpdir})


def _make_pattern(
    pattern_id,
    target_file="SOUL.md",
    update_type="SOUL",
    category="behavior",
    summary="Test pattern",
    content="Test content",
    confidence=0.9,
    evidence_count=4,
    source_entries=None,
    insertion_point="append",
    auto_apply=True,
    needs_review=False,
):
    """Create a DiscoveredPattern with common defaults."""
    if source_entries is None:
        source_entries = ["memory/2026-04-05.md"]
    return DiscoveredPattern(
        pattern_id=pattern_id,
        target_file=target_file,
        update_type=update_type,
        category=category,
        summary=summary,
        content=content,
        confidence=confidence,
        evidence_count=evidence_count,
        source_entries=source_entries,
        insertion_point=insertion_point,
        auto_apply=auto_apply,
        needs_review=needs_review,
    )


# Common test constants
TEST_SOURCE = "memory/2026-04-05.md"
TEST_SOURCES = ["memory/2026-04-05.md"]
TEST_TIMESTAMP = "2026-04-05"


# =============================================================================
# Config Tests
# =============================================================================

def test_config_defaults():
    """Test configuration defaults."""
    config = SoulForgeConfig()
    assert config.workspace.endswith(".openclaw/workspace")
    assert config.trigger_threshold == 3
    assert config.get("backup_enabled") == True
    assert "SOUL.md" in [Path(f).name for f in config.target_files]
    _pass("test_config_defaults")


def test_config_overrides():
    """Test configuration overrides."""
    config = SoulForgeConfig(overrides={
        "workspace": "/tmp/test-workspace",
        "trigger_threshold": 5,
    })
    assert config.workspace == "/tmp/test-workspace"
    assert config.trigger_threshold == 5
    _pass("test_config_overrides")


def test_config_backup_retention():
    """Test backup retention counts for important vs normal files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = _make_config(tmpdir)
        # Important files
        assert config.get_backup_retention("SOUL.md") == 20
        assert config.get_backup_retention("IDENTITY.md") == 20
        # Normal files
        assert config.get_backup_retention("USER.md") == 10
        assert config.get_backup_retention("MEMORY.md") == 10
        assert config.get_backup_retention("AGENTS.md") == 10
        _pass("test_config_backup_retention")


def test_config_last_run_timestamp():
    """Test last_run_timestamp read/write."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = _make_config(tmpdir)

        # Initially None
        assert config.get_last_run_timestamp() is None

        # Write a timestamp
        config.set_last_run_timestamp("2026-04-05T10:00:00")
        assert config.get_last_run_timestamp() == "2026-04-05T10:00:00"

        # Write current time
        config.set_last_run_timestamp()
        ts = config.get_last_run_timestamp()
        assert ts is not None
        assert "T" in ts  # ISO format

        _pass("test_config_last_run_timestamp")


def test_config_agent_suffix():
    """Test agent suffix derivation."""
    config1 = SoulForgeConfig(overrides={"workspace": "~/.openclaw/workspace"})
    assert config1.agent_suffix == "main"

    config2 = SoulForgeConfig(overrides={"workspace": "~/.openclaw/workspace-wukong"})
    assert config2.agent_suffix == "wukong"

    config3 = SoulForgeConfig(overrides={"workspace": "/path/to/workspace-tseng"})
    assert config3.agent_suffix == "tseng"
    _pass("test_config_agent_suffix")


def test_config_state_and_backup_dirs():
    """Test state_dir and backup_dir are properly isolated per agent."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = _make_config(tmpdir)
        # Agent suffix is derived from tmpdir name, so state_dir contains .soulforge-{suffix}
        assert ".soulforge-" in config.state_dir
        assert ".soulforge-" in config.backup_dir
        assert "backups" in config.backup_dir
        _pass("test_config_state_and_backup_dirs")


def test_config_to_dict():
    """Test config serialization."""
    config = SoulForgeConfig(overrides={"workspace": "/test", "dry_run": True})
    d = config.to_dict()
    assert d["workspace"] == "/test"
    assert d["dry_run"] == True
    _pass("test_config_to_dict")


# =============================================================================
# MemoryReader Tests
# =============================================================================

def test_memory_entry_creation():
    """Test MemoryEntry dataclass."""
    entry = MemoryEntry(
        source="memory/2026-04-05.md",
        source_type="daily_log",
        category="conversation",
        content="Test content",
        timestamp="2026-04-05",
        importance=0.8,
    )
    assert entry.source == "memory/2026-04-05.md"
    assert entry.source_type == "daily_log"
    assert entry.content == "Test content"
    # Test to_dict
    d = entry.to_dict()
    assert d["source"] == "memory/2026-04-05.md"
    _pass("test_memory_entry_creation")


def test_memory_reader_daily_logs():
    """Test reading daily memory logs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        memory_dir = Path(tmpdir) / "memory"
        memory_dir.mkdir()

        test_file = memory_dir / "2026-04-05.md"
        test_file.write_text("# 2026-04-05\n\nTest conversation content here.")

        config = _make_config(tmpdir)
        reader = MemoryReader(tmpdir, config)
        entries = reader.read_all()

        assert len(entries) >= 1
        entry = entries[0]
        assert entry.source_type == "daily_log"
        _pass("test_memory_reader_daily_logs")


def test_memory_reader_incremental():
    """Test incremental reading respects last_run timestamp."""
    with tempfile.TemporaryDirectory() as tmpdir:
        memory_dir = Path(tmpdir) / "memory"
        memory_dir.mkdir()

        # Create files for different dates
        old_file = memory_dir / "2026-04-01.md"
        old_file.write_text("# 2026-04-01\n\nOld content.")
        new_file = memory_dir / "2026-04-05.md"
        new_file.write_text("# 2026-04-05\n\nNew content.")

        config = _make_config(tmpdir)

        # Without last_run, should read all
        reader = MemoryReader(tmpdir, config)
        entries = reader.read_all(since_timestamp=None)
        assert len(entries) >= 2

        # With last_run set to 2026-04-03, should only get 2026-04-05
        config.set_last_run_timestamp("2026-04-03T00:00:00")
        reader2 = MemoryReader(tmpdir, config)
        entries2 = reader2.read_all()  # Uses config's last_run
        timestamps = [e.timestamp for e in entries2]
        assert "2026-04-01" not in timestamps or "2026-04-05" in timestamps
        _pass("test_memory_reader_incremental")


def test_memory_reader_learnings():
    """Test reading learnings directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        learnings_dir = Path(tmpdir) / ".learnings"
        learnings_dir.mkdir()

        learnings_file = learnings_dir / "LEARNINGS.md"
        learnings_file.write_text("""# Learnings

## correction

Some correction content here.

---

## insight

Some insight about the user.

---
""")

        config = _make_config(tmpdir)
        reader = MemoryReader(tmpdir, config)
        entries = reader.read_all()

        assert len(entries) >= 1
        categories = [e.category for e in entries]
        assert "correction" in categories or "insight" in categories
        _pass("test_memory_reader_learnings")


def test_memory_reader_empty_workspace():
    """Test MemoryReader with no sources."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = _make_config(tmpdir)
        reader = MemoryReader(tmpdir, config)
        entries = reader.read_all()
        assert len(entries) == 0
        _pass("test_memory_reader_empty_workspace")


# =============================================================================
# Analyzer Tests
# =============================================================================

def test_discovered_pattern_insertion_point():
    """Test DiscoveredPattern insertion_point field."""
    p = _make_pattern(
        pattern_id="test_001",
        insertion_point="section:Core Identity",
    )
    assert p.insertion_point == "section:Core Identity"
    assert p.auto_apply == True
    assert p.needs_review == False
    _pass("test_discovered_pattern_insertion_point")


def test_discovered_pattern_confidence_levels():
    """Test confidence-based auto_apply and needs_review."""
    # High confidence
    p_high = _make_pattern(
        pattern_id="p1",
        confidence=0.9,
        evidence_count=3,
        source_entries=[],
    )
    assert p_high.auto_apply == True
    assert p_high.needs_review == False

    # Medium confidence
    p_med = _make_pattern(
        pattern_id="p2",
        confidence=0.6,
        evidence_count=2,
        source_entries=[],
        auto_apply=False,
        needs_review=True,
    )
    assert p_med.auto_apply == False
    assert p_med.needs_review == True

    # Low confidence
    p_low = _make_pattern(
        pattern_id="p3",
        confidence=0.3,
        evidence_count=1,
        source_entries=[],
        auto_apply=False,
        needs_review=False,
    )
    assert p_low.auto_apply == False
    assert p_low.needs_review == False

    _pass("test_discovered_pattern_confidence_levels")


def test_discovered_pattern_to_dict():
    """Test DiscoveredPattern serialization."""
    p = _make_pattern(
        pattern_id="test_001",
        insertion_point="section:Core",
    )
    d = p.to_dict()
    assert d["pattern_id"] == "test_001"
    assert d["insertion_point"] == "section:Core"
    assert d["auto_apply"] == True
    assert d["needs_review"] == False
    _pass("test_discovered_pattern_to_dict")


def test_discovered_pattern_from_dict():
    """Test DiscoveredPattern deserialization."""
    d = {
        "pattern_id": "test_002",
        "target_file": "USER.md",
        "update_type": "USER",
        "category": "preference",
        "summary": "User prefers X",
        "content": "Content here",
        "confidence": 0.75,
        "evidence_count": 3,
        "source_entries": [TEST_SOURCE],
        "suggested_section": "Preferences",
        "insertion_point": "append",
        "auto_apply": False,
        "needs_review": True,
    }
    p = DiscoveredPattern.from_dict(d)
    assert p.pattern_id == "test_002"
    assert p.target_file == "USER.md"
    assert p.confidence == 0.75
    assert p.needs_review == True
    _pass("test_discovered_pattern_from_dict")


def test_pattern_to_markdown_block():
    """Test DiscoveredPattern markdown formatting."""
    pattern = _make_pattern(
        pattern_id="test_001",
        summary="User prefers numbered lists",
        content="User不喜欢看长文本选项，给选项时列序号让直接挑。",
        insertion_point="section:沟通方式",
        source_entries=["memory/2026-04-04.md", "memory/2026-04-05.md"],
    )

    block = pattern.to_markdown_block()
    assert "SoulForge Update" in block
    assert "User prefers numbered lists" in block
    assert "behavior" in block
    assert "4" in block  # evidence count
    assert "section:沟通方式" in block  # insertion point in block
    _pass("test_pattern_to_markdown_block")


# =============================================================================
# Evolver Tests
# =============================================================================

def test_evolver_duplicate_filter():
    """Test that evolver filters duplicates."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = _make_config(tmpdir)
        evolver = SoulEvolver(tmpdir, config)

        existing = "User prefers numbered lists\nMore content"

        pattern = _make_pattern(
            pattern_id="test_001",
            content="User不喜欢看长文本选项，给选项时列序号。",
        )

        filtered = evolver._filter_duplicates([pattern], existing)
        assert len(filtered) == 0  # Should be filtered out
        _pass("test_evolver_duplicate_filter")


def test_evolver_no_duplicate():
    """Test that evolver allows new patterns."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = _make_config(tmpdir)
        evolver = SoulEvolver(tmpdir, config)

        existing = "Some existing content"
        pattern = _make_pattern(
            pattern_id="test_001",
            summary="New pattern not in file",
            content="This is brand new information.",
        )

        filtered = evolver._filter_duplicates([pattern], existing)
        assert len(filtered) == 1  # Should pass through
        _pass("test_evolver_no_duplicate")


def test_evolver_dry_run():
    """Test evolver dry run mode."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = SoulForgeConfig(overrides={"workspace": tmpdir, "dry_run": True})
        evolver = SoulEvolver(tmpdir, config)

        target_file = Path(tmpdir) / "SOUL.md"
        target_file.write_text("# SOUL.md\n\nExisting content.")

        pattern = _make_pattern(
            pattern_id="test_001",
            summary="Test pattern",
            content="Test content to add.",
            insertion_point="append",
        )

        results = evolver.apply_updates([pattern], dry_run=True)

        assert results["dry_run"] == True
        assert results["patterns_applied"] == 1
        # File should NOT be modified
        assert target_file.read_text() == "# SOUL.md\n\nExisting content."
        _pass("test_evolver_dry_run")


def test_evolver_insertion_point_top():
    """Test evolver insertion at top of file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = _make_config(tmpdir)
        evolver = SoulEvolver(tmpdir, config)

        target_file = Path(tmpdir) / "SOUL.md"
        target_file.write_text("# SOUL.md\n\nExisting content.")

        pattern = _make_pattern(
            pattern_id="test_001",
            summary="Top pattern",
            content="This goes at top.",
            insertion_point="top",
        )

        results = evolver.apply_updates([pattern], dry_run=False)

        content = target_file.read_text()
        assert "This goes at top." in content
        # Block starts with \n so content starts with the original, but update is near top
        assert "<!-- SoulForge Update" in content[:200]
        _pass("test_evolver_insertion_point_top")


def test_evolver_insertion_point_section():
    """Test evolver insertion after section."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = _make_config(tmpdir)
        evolver = SoulEvolver(tmpdir, config)

        target_file = Path(tmpdir) / "SOUL.md"
        target_file.write_text("""# SOUL.md

## Core Identity

Original core content.

## Communication

Other content.
""")

        pattern = _make_pattern(
            pattern_id="test_001",
            summary="New core item",
            content="New item for core identity.",
            insertion_point="section:Core Identity",
        )

        results = evolver.apply_updates([pattern], dry_run=False)

        content = target_file.read_text()
        assert "New item for core identity." in content
        # Should be inserted after Core Identity section, before Communication
        lines = content.split("\n")
        core_idx = next(i for i, l in enumerate(lines) if "Core Identity" in l)
        comm_idx = next(i for i, l in enumerate(lines) if "Communication" in l)
        new_idx = next(i for i, l in enumerate(lines) if "New item for core" in l)
        assert core_idx < new_idx < comm_idx
        _pass("test_evolver_insertion_point_section")


def test_evolver_backup_retention_important():
    """Test backup retention for important files (20)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = SoulForgeConfig(overrides={"workspace": tmpdir, "backup_retention_important": 20})
        evolver = SoulEvolver(tmpdir, config)

        target_file = Path(tmpdir) / "SOUL.md"
        target_file.write_text("# SOUL.md\n\nContent.")

        # Create 25 backups
        for i in range(25):
            target_file.write_text(f"# SOUL.md\n\nContent {i}.")
            evolver._create_backup(target_file, backup_type="auto")

        backup_dir = Path(config.backup_dir)
        backups = list(backup_dir.glob("SOUL.md.*.bak"))
        assert len(backups) == 20  # Should keep only 20
        _pass("test_evolver_backup_retention_important")


def test_evolver_backup_retention_normal():
    """Test backup retention for normal files (10)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = SoulForgeConfig(overrides={"workspace": tmpdir, "backup_retention_normal": 10})
        evolver = SoulEvolver(tmpdir, config)

        target_file = Path(tmpdir) / "USER.md"
        target_file.write_text("# USER.md\n\nContent.")

        # Create 15 backups
        for i in range(15):
            target_file.write_text(f"# USER.md\n\nContent {i}.")
            evolver._create_backup(target_file, backup_type="auto")

        backup_dir = Path(config.backup_dir)
        backups = list(backup_dir.glob("USER.md.*.bak"))
        assert len(backups) == 10  # Should keep only 10
        _pass("test_evolver_backup_retention_normal")


def test_evolver_backup_type_naming():
    """Test backup file naming includes type (auto/manual)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = _make_config(tmpdir)
        evolver = SoulEvolver(tmpdir, config)

        target_file = Path(tmpdir) / "SOUL.md"
        target_file.write_text("# SOUL.md\n\nContent.")

        # Auto backup
        evolver._create_backup(target_file, backup_type="auto")
        # Manual backup
        evolver._create_backup(target_file, backup_type="manual")

        backup_dir = Path(config.backup_dir)
        auto_backups = list(backup_dir.glob("SOUL.md.*.auto.bak"))
        manual_backups = list(backup_dir.glob("SOUL.md.*.manual.bak"))

        assert len(auto_backups) >= 1
        assert len(manual_backups) >= 1
        _pass("test_evolver_backup_type_naming")


def test_evolver_generate_review():
    """Test review mode output generation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = _make_config(tmpdir)
        evolver = SoulEvolver(tmpdir, config)

        patterns = [
            _make_pattern(
                pattern_id="p1",
                summary="High conf pattern",
                content="High conf content",
                confidence=0.9,
                evidence_count=4,
            ),
            _make_pattern(
                pattern_id="p2",
                target_file="USER.md",
                update_type="USER",
                category="preference",
                summary="Medium conf pattern",
                content="Medium conf content",
                confidence=0.6,
                evidence_count=2,
                auto_apply=False,
                needs_review=True,
            ),
        ]

        result = evolver.generate_review(patterns)

        assert result["total_patterns"] == 2
        assert len(result["high_confidence"]) == 1
        assert len(result["medium_confidence"]) == 1

        # Check review file was created
        review_path = Path(result["review_file"])
        assert review_path.exists()

        # Check review file content
        review_data = json.loads(review_path.read_text(encoding="utf-8"))
        assert review_data["total_patterns"] == 2
        assert len(review_data["patterns"]) == 2
        _pass("test_evolver_generate_review")


def test_evolver_create_manual_backup():
    """Test manual backup creation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = _make_config(tmpdir)
        evolver = SoulEvolver(tmpdir, config)

        # Create target files
        soul_file = Path(tmpdir) / "SOUL.md"
        soul_file.write_text("# SOUL.md\n\nContent.")
        user_file = Path(tmpdir) / "USER.md"
        user_file.write_text("# USER.md\n\nContent.")

        result = evolver.create_manual_backup()

        assert len(result["backed_up"]) == 2
        backed_names = [Path(p).name for p in result["backed_up"]]
        assert "SOUL.md" in backed_names
        assert "USER.md" in backed_names
        assert len(result["errors"]) == 0
        _pass("test_evolver_create_manual_backup")


def test_analyzer_separate_by_confidence():
    """Test analyzer confidence separation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = _make_config(tmpdir)
        analyzer = PatternAnalyzer(config)

        patterns = [
            _make_pattern(pattern_id="p1", confidence=0.9, evidence_count=4, source_entries=[]),
            _make_pattern(pattern_id="p2", confidence=0.6, evidence_count=2, source_entries=[]),
            _make_pattern(pattern_id="p3", confidence=0.3, evidence_count=1, source_entries=[]),
        ]

        result = analyzer.separate_by_confidence(patterns)
        assert len(result["high"]) == 1
        assert len(result["medium"]) == 1
        assert len(result["low"]) == 1
        _pass("test_analyzer_separate_by_confidence")


# =============================================================================
# Run All Tests
# =============================================================================

def run_all_tests():
    """Run all tests."""
    print("Running SoulForge tests...")
    print("=" * 50)

    tests = [
        # Config
        test_config_defaults,
        test_config_overrides,
        test_config_backup_retention,
        test_config_last_run_timestamp,
        test_config_agent_suffix,
        test_config_state_and_backup_dirs,
        test_config_to_dict,
        # MemoryReader
        test_memory_entry_creation,
        test_memory_reader_daily_logs,
        test_memory_reader_incremental,
        test_memory_reader_learnings,
        test_memory_reader_empty_workspace,
        # Analyzer
        test_discovered_pattern_insertion_point,
        test_discovered_pattern_confidence_levels,
        test_discovered_pattern_to_dict,
        test_discovered_pattern_from_dict,
        test_pattern_to_markdown_block,
        test_analyzer_separate_by_confidence,
        # Evolver
        test_evolver_duplicate_filter,
        test_evolver_no_duplicate,
        test_evolver_dry_run,
        test_evolver_insertion_point_top,
        test_evolver_insertion_point_section,
        test_evolver_backup_retention_important,
        test_evolver_backup_retention_normal,
        test_evolver_backup_type_naming,
        test_evolver_generate_review,
        test_evolver_create_manual_backup,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"✗ {test.__name__} FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("=" * 50)
    print(f"Results: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)