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
    context_budget: int = 120_000
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
            context_budget=int(os.getenv("AGENT_CONTEXT_BUDGET", "120000")),
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


def load_dotenv_key(repo_root: Path = REPO_ROOT) -> None:
    """Populate ANTHROPIC_API_KEY from a .env file when it is not already set.

    Lets the dashboard be launched by double-clicking, with no terminal
    session to export a variable in. An existing environment variable always
    wins, so a shell can still override the file.
    """
    if os.getenv("ANTHROPIC_API_KEY", "").strip():
        return
    env_file = repo_root / ".env"
    if not env_file.is_file():
        return
    for line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
        name, _, value = line.partition("=")
        if name.strip() == "ANTHROPIC_API_KEY" and value.strip():
            os.environ["ANTHROPIC_API_KEY"] = value.strip().strip("\"'")
            return


def require_api_key() -> str:
    """Return the Anthropic API key, or fail with an actionable message."""
    load_dotenv_key()
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Add it to your environment or a .env file."
        )
    return key
