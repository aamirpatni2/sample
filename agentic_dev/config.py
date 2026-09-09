"""Configuration for the Agentic AI Developer. All settings come from env."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parent
DEFAULT_PROMPT_PATH = REPO_ROOT / "prompts" / "agentic-ai-developer.md"

DEFAULT_MODEL = "claude-opus-5"


@dataclass
class Settings:
    """Runtime settings. Secrets are read from the environment, never stored here."""

    workspace: Path = field(default_factory=Path.cwd)
    model: str = DEFAULT_MODEL
    max_tokens: int = 8_000
    max_turns: int = 40
    command_timeout: int = 120
    prompt_path: Path = DEFAULT_PROMPT_PATH

    @classmethod
    def from_env(cls, workspace: Path | None = None) -> "Settings":
        """Build settings from environment variables, falling back to defaults."""
        return cls(
            workspace=(workspace or Path(os.getenv("AGENT_WORKSPACE", "."))).resolve(),
            model=os.getenv("AGENT_MODEL", DEFAULT_MODEL),
            max_tokens=int(os.getenv("AGENT_MAX_TOKENS", "8000")),
            max_turns=int(os.getenv("AGENT_MAX_TURNS", "40")),
            command_timeout=int(os.getenv("AGENT_COMMAND_TIMEOUT", "120")),
            prompt_path=Path(os.getenv("AGENT_PROMPT_PATH", str(DEFAULT_PROMPT_PATH))),
        )


def load_system_prompt(path: Path = DEFAULT_PROMPT_PATH) -> str:
    """Load the master system prompt from disk.

    The prompt is a file, not a string literal, so it can be edited and
    version-controlled without touching code.
    """
    if not path.is_file():
        raise FileNotFoundError(
            f"Master prompt not found at {path}. Set AGENT_PROMPT_PATH to override."
        )
    return path.read_text(encoding="utf-8")


def require_api_key() -> str:
    """Return the Anthropic API key, or fail with an actionable message."""
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Add it to your environment or a .env file."
        )
    return key
