"""
Settings loader for the Daily News Aggregator.
Loads configuration from environment variables and preset files.
"""

import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")


class Settings:
    """Configuration settings loaded from environment and config files."""

    def __init__(self):
        # Telegram settings
        self.telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")

        # GitHub settings
        self.github_token: str = os.getenv("GITHUB_TOKEN", "")
        self.github_repo: str = os.getenv("GITHUB_REPO", "")
        self.github_branch: str = os.getenv("GITHUB_BRANCH", "main")

        # Claude settings
        self.claude_model: str = os.getenv("CLAUDE_MODEL", "sonnet")

        # News settings
        self.news_preset: str = os.getenv("NEWS_PRESET", "ai_tech")

        # Git user settings
        self.git_user_name: str = os.getenv("GIT_USER_NAME", "Daily News Bot")
        self.git_user_email: str = os.getenv("GIT_USER_EMAIL", "bot@example.com")

        # Paths
        self.project_root = PROJECT_ROOT
        self.news_dir = PROJECT_ROOT / "news"
        self.presets_file = PROJECT_ROOT / "config" / "presets.json"

    def validate_telegram(self) -> tuple[bool, str]:
        """Validate Telegram configuration."""
        if not self.telegram_bot_token or self.telegram_bot_token == "your_bot_token_here":
            return False, "TELEGRAM_BOT_TOKEN is not configured"
        if not self.telegram_chat_id or self.telegram_chat_id == "your_chat_id_here":
            return False, "TELEGRAM_CHAT_ID is not configured"
        return True, ""

    def validate_github(self) -> tuple[bool, str]:
        """Validate GitHub configuration."""
        if not self.github_token or self.github_token.startswith("ghp_your"):
            return False, "GITHUB_TOKEN is not configured"
        if not self.github_repo or "/" not in self.github_repo:
            return False, "GITHUB_REPO is not configured properly (should be 'username/repo')"
        return True, ""

    def load_presets(self) -> dict:
        """Load news presets from JSON file."""
        if not self.presets_file.exists():
            return {}
        with open(self.presets_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_preset(self, preset_name: str | None = None) -> dict | None:
        """Get a specific preset by name."""
        presets = self.load_presets()
        name = preset_name or self.news_preset
        return presets.get(name)

    def list_presets(self) -> list[str]:
        """List all available preset names."""
        return list(self.load_presets().keys())


# Global settings instance
settings = Settings()
