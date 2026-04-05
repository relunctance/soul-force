"""
SoulForge - AI Agent Memory Evolution System
"""

__version__ = "2.1.0"
__author__ = "relunctance"
__license__ = "MIT"

from soulforge.config import SoulForgeConfig
from soulforge.memory_reader import MemoryReader, MemoryEntry
from soulforge.analyzer import PatternAnalyzer, DiscoveredPattern
from soulforge.evolver import SoulEvolver
from soulforge.schema import (
    ProposedUpdate,
    DiscoveredPatternSchema,
    validate_proposed_update,
    validate_proposed_updates_batch,
)

__all__ = [
    "SoulForgeConfig",
    "MemoryReader",
    "MemoryEntry",
    "PatternAnalyzer",
    "DiscoveredPattern",
    "SoulEvolver",
    "ProposedUpdate",
    "DiscoveredPatternSchema",
    "validate_proposed_update",
    "validate_proposed_updates_batch",
]
