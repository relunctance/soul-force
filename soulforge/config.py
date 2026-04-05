"""
SoulForge Configuration Management

This module handles all configuration for SoulForge, including:
- Loading settings from config files (~/.soulforgerc.json)
- Reading OpenClaw's built-in API settings (zero-config)
- Environment variable overrides
- last_run_timestamp management for incremental analysis

Priority order:
    1. Runtime overrides (CLI args)
    2. Environment variables
    3. Config file (~/.soulforgerc.json or soulforge/config.json)
    4. OpenClaw config (~/.openclaw/openclaw.json)
    5. DEFAULT_CONFIG values
"""

import os
import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime


class SoulForgeConfig:
    """Configuration for SoulForge memory evolution system."""

    DEFAULT_CONFIG: Dict[str, Any] = {
        "workspace": "~/.openclaw/workspace",
        "memory_paths": [
            "memory/",
            ".learnings/",
        ],
        "target_files": [
            "SOUL.md",
            "USER.md",
            "IDENTITY.md",
            "MEMORY.md",
            "AGENTS.md",
            "TOOLS.md",
        ],
        "trigger_threshold": 3,
        "backup_enabled": True,
        "backup_dir": None,  # Derived from workspace
        "state_dir": None,   # Derived from workspace
        "openai_api_key_env": "OPENAI_API_KEY",
        "minimax_api_key_env": "MINIMAX_API_KEY",
        "openai_base_url_env": "OPENAI_BASE_URL",
        "model": None,  # Use OpenClaw's default model
        "log_level": "INFO",
        "dry_run": False,
        # hawk-bridge
        "hawk_bridge_enabled": True,
        "hawk_db_path": "~/.hawk/lancedb",
        "hawk_table_name": "hawk_memories",
        "hawk_sync_interval_hours": 24,
        # Token budget protection
        "max_token_budget": 4096,
        # Backup retention
        "backup_retention_important": 20,
        "backup_retention_normal": 10,
        # Rollback
        "rollback_auto_enabled": True,
        # Notifications
        "notify_on_complete": False,
        "notify_chat_id": None,
    }

    def __init__(self, config_path: Optional[str] = None, overrides: Optional[dict] = None):
        """
        Initialize configuration.

        Priority: CLI overrides > env vars > config file > defaults.
        """
        self._config = self.DEFAULT_CONFIG.copy()

        # Search for config file
        if config_path:
            self._load_from_file(config_path)
        else:
            for candidate in [
                Path("soulforge/config.json"),
                Path("~/.openclaw/skills/soul-forge/soulforge/config.json").expanduser(),
                Path("~/.soulforgerc.json").expanduser(),
            ]:
                if candidate.exists():
                    self._load_from_file(str(candidate))
                    break

        # Environment variable overrides
        self._apply_env_overrides()

        # Runtime overrides
        if overrides:
            self._config.update(overrides)

        # Expand workspace path
        self.workspace = str(Path(self._config["workspace"]).expanduser().resolve())

        # Derive agent suffix for isolation
        self._agent_suffix = self._derive_agent_suffix()

    def _derive_agent_suffix(self) -> str:
        """Derive agent-specific suffix from workspace path."""
        base = Path(self.workspace)
        workspace_name = base.name
        if workspace_name == "workspace":
            return "main"
        return workspace_name.replace("workspace-", "")

    def _load_from_file(self, path: str) -> None:
        """Load configuration from JSON file, merging with defaults."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            self._config.update(loaded)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Failed to load config from {path}: {e}")

    def _apply_env_overrides(self) -> None:
        """Apply environment variable overrides, then fall back to OpenClaw config."""
        # API key: try OPENAI_API_KEY first, then MINIMAX_API_KEY
        openai_key_env = self._config.get("openai_api_key_env", "OPENAI_API_KEY")
        minimax_key_env = self._config.get("minimax_api_key_env", "MINIMAX_API_KEY")
        if openai_key_env in os.environ:
            self._config["api_key"] = os.environ[openai_key_env]
        elif minimax_key_env in os.environ:
            self._config["api_key"] = os.environ[minimax_key_env]
        else:
            self._config["api_key"] = self._get_openclaw_api_key()

        # Base URL
        openai_url_env = self._config.get("openai_base_url_env", "OPENAI_BASE_URL")
        if openai_url_env in os.environ:
            self._config["base_url"] = os.environ[openai_url_env]
        else:
            self._config["base_url"] = self._get_openclaw_base_url()

        # Workspace override
        if "SOULFORGE_WORKSPACE" in os.environ:
            self._config["workspace"] = os.environ["SOULFORGE_WORKSPACE"]

    def _get_openclaw_api_key(self) -> str:
        """Read API key from OpenClaw's config file."""
        openclaw_config = Path.home() / ".openclaw" / "openclaw.json"
        if not openclaw_config.exists():
            return ""
        try:
            with open(openclaw_config, "r") as f:
                cfg = json.load(f)
            providers = cfg.get("providers", {})
            for name, p in providers.items():
                if isinstance(p, dict):
                    key = p.get("apiKey") or p.get("api_key")
                    if key:
                        return key
            return ""
        except Exception:
            return ""

    def _get_openclaw_base_url(self) -> str:
        """Read base URL from OpenClaw's config file."""
        openclaw_config = Path.home() / ".openclaw" / "openclaw.json"
        if not openclaw_config.exists():
            return "https://api.minimax.chat/v1"
        try:
            with open(openclaw_config, "r") as f:
                cfg = json.load(f)
            providers = cfg.get("providers", {})
            for name, p in providers.items():
                if isinstance(p, dict):
                    url = p.get("baseUrl") or p.get("base_url")
                    if url:
                        return url.rstrip("/")
            return "https://api.minimax.chat/v1"
        except Exception:
            return "https://api.minimax.chat/v1"

    def get(self, key: str, default=None):
        """Get a configuration value."""
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value (runtime only)."""
        self._config[key] = value

    @property
    def agent_suffix(self) -> str:
        """Get agent-specific suffix for path isolation."""
        return self._agent_suffix

    @property
    def memory_paths(self) -> List[str]:
        """Get list of memory source paths (relative to workspace)."""
        base = Path(self.workspace)
        return [str(base / p) for p in self._config["memory_paths"]]

    @property
    def target_files(self) -> List[str]:
        """Get list of target files (relative to workspace)."""
        base = Path(self.workspace)
        return [str(base / f) for f in self._config["target_files"]]

    @property
    def backup_dir(self) -> str:
        """Backup directory path, isolated per agent."""
        base = Path(self.workspace)
        agent_dir = f".soulforge-{self._agent_suffix}"
        return str(base / agent_dir / "backups")

    @property
    def state_dir(self) -> str:
        """State directory path, isolated per agent."""
        base = Path(self.workspace)
        agent_dir = f".soulforge-{self._agent_suffix}"
        return str(base / agent_dir)

    @property
    def review_dir(self) -> str:
        """Review output directory."""
        return str(Path(self.state_dir) / "review")

    @property
    def review_failed_dir(self) -> str:
        """Directory for failed/rejected pattern reviews."""
        return str(Path(self.state_dir) / "review" / "failed")

    @property
    def last_run_path(self) -> str:
        """Path to the last_run timestamp file."""
        return str(Path(self.state_dir) / "last_run")

    @property
    def hawk_sync_path(self) -> str:
        """Path to the hawk-bridge last sync timestamp file."""
        return str(Path(self.state_dir) / "last_hawk_sync")

    @property
    def api_key(self) -> str:
        """Get API key."""
        return self._config.get("api_key", "")

    @property
    def base_url(self) -> str:
        """Get API base URL."""
        return self._config.get("base_url", "https://api.minimax.chat/v1")

    @property
    def trigger_threshold(self) -> int:
        """Get pattern trigger threshold."""
        return self._config.get("trigger_threshold", 3)

    @property
    def is_dry_run(self) -> bool:
        """Check if running in dry-run mode."""
        return self._config.get("dry_run", False)

    @property
    def log_level(self) -> str:
        """Get logging level."""
        return self._config.get("log_level", "INFO")

    @property
    def max_token_budget(self) -> int:
        """Get maximum token budget for memory reads."""
        return self._config.get("max_token_budget", 4096)

    @property
    def rollback_auto_enabled(self) -> bool:
        """Check if auto-rollback is enabled."""
        return self._config.get("rollback_auto_enabled", True)

    @property
    def notify_on_complete(self) -> bool:
        """Check if notifications are enabled."""
        return self._config.get("notify_on_complete", False)

    @property
    def notify_chat_id(self) -> Optional[str]:
        """Get notification chat ID."""
        return self._config.get("notify_chat_id")

    @property
    def backup_retention_important(self) -> int:
        """Get backup retention count for important files."""
        return self._config.get("backup_retention_important", 20)

    @property
    def backup_retention_normal(self) -> int:
        """Get backup retention count for normal files."""
        return self._config.get("backup_retention_normal", 10)

    def get_backup_retention(self, filename: str) -> int:
        """Get backup retention count for a specific file."""
        important_files = {"SOUL.md", "IDENTITY.md"}
        if filename in important_files:
            return self.backup_retention_important
        return self.backup_retention_normal

    def get_last_run_timestamp(self) -> Optional[str]:
        """Read last_run timestamp from state file."""
        path = Path(self.last_run_path)
        if not path.exists():
            return None
        try:
            return path.read_text(encoding="utf-8").strip()
        except Exception:
            return None

    def set_last_run_timestamp(self, timestamp: Optional[str] = None) -> None:
        """Write last_run timestamp to state file."""
        if timestamp is None:
            timestamp = datetime.now().isoformat()
        path = Path(self.last_run_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(timestamp, encoding="utf-8")

    def get_last_hawk_sync(self) -> Optional[str]:
        """Read last_hawk_sync timestamp from state file."""
        path = Path(self.hawk_sync_path)
        if not path.exists():
            return None
        try:
            return path.read_text(encoding="utf-8").strip()
        except Exception:
            return None

    def set_last_hawk_sync(self, timestamp: Optional[str] = None) -> None:
        """Write last_hawk_sync timestamp to state file."""
        if timestamp is None:
            timestamp = datetime.now().isoformat()
        path = Path(self.hawk_sync_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(timestamp, encoding="utf-8")

    def to_dict(self) -> dict:
        """Export configuration as dict."""
        return self._config.copy()

    def to_file(self, path: Optional[str] = None) -> None:
        """Save current config to a JSON file."""
        if path is None:
            path = str(Path.home() / ".soulforgerc.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._config, f, ensure_ascii=False, indent=2)

    def __repr__(self) -> str:
        return f"SoulForgeConfig(workspace={self.workspace}, threshold={self.trigger_threshold})"
