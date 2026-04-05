"""
SoulForge Schema Validation Layer

Uses pydantic to validate LLM-generated patterns before applying them.
Ensures structural integrity and provides graceful degradation on parse failure.

Schema:
- ProposedUpdate: Validates a single proposed file update from LLM
- DiscoveredPatternSchema: Validates a discovered pattern with metadata
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from datetime import datetime


class ProposedUpdate(BaseModel):
    """Schema for an LLM-proposed file update."""
    target_file: str = Field(..., description="Target file path (e.g., SOUL.md)")
    update_type: str = Field(..., description="Update category: SOUL|USER|IDENTITY|MEMORY|AGENTS|TOOLS")
    category: str = Field(..., description="Pattern category: behavior|preference|decision|error|general")
    summary: str = Field(..., description="One-line pattern summary")
    content: str = Field(..., max_length=500, description="Update content (max 500 chars)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score 0.0-1.0")
    evidence_count: int = Field(..., ge=1, description="How many times pattern was observed")
    source_entries: List[str] = Field(default_factory=list, description="Source file references")
    suggested_section: Optional[str] = Field(None, description="Suggested section title")
    insertion_point: Optional[str] = Field("append", description="Where to insert: append|section:{title}|top")

    @field_validator("insertion_point", mode="before")
    @classmethod
    def normalize_insertion_point(cls, v):
        """Normalize insertion_point: upgrade 'append' to 'section:{title}' if suggested_section provided."""
        if not v or v == "append":
            return "append"
        return v

    @field_validator("update_type", mode="before")
    @classmethod
    def normalize_update_type(cls, v):
        """Normalize update_type to uppercase."""
        if isinstance(v, str):
            return v.upper()
        return v


class DiscoveredPatternSchema(BaseModel):
    """Schema for a fully-formed discovered pattern."""
    pattern_id: str = Field(..., description="Unique pattern identifier")
    target_file: str = Field(..., description="Target file path")
    update_type: str = Field(..., description="Update category")
    category: str = Field(..., description="Pattern category")
    summary: str = Field(..., description="One-line summary")
    content: str = Field(..., max_length=500)
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence_count: int = Field(..., ge=1)
    source_entries: List[str] = Field(default_factory=list)
    suggested_section: Optional[str] = None
    insertion_point: str = "append"
    expires_at: Optional[str] = Field(None, description="ISO timestamp for pattern expiry")
    auto_apply: bool = False
    needs_review: bool = False


def validate_proposed_update(data: dict) -> tuple[Optional[ProposedUpdate], Optional[str]]:
    """
    Validate a dict as ProposedUpdate.

    Args:
        data: Raw dict from LLM response

    Returns:
        (validated ProposedUpdate or None, error_message or None)
    """
    try:
        update = ProposedUpdate(**data)
        return update, None
    except Exception as e:
        return None, str(e)


def validate_proposed_updates_batch(data: dict) -> tuple[List[ProposedUpdate], List[dict]]:
    """
    Validate the 'proposed_updates' array from LLM response.

    Args:
        data: Parsed JSON dict from LLM response

    Returns:
        (list of valid ProposedUpdate, list of invalid items with error info)
    """
    valid = []
    invalid = []
    for item in data.get("proposed_updates", []):
        update, err = validate_proposed_update(item)
        if update:
            valid.append(update)
        else:
            invalid.append({"item": item, "error": err})
    return valid, invalid
