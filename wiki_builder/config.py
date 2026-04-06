import json
import os
from pathlib import Path

CONFIG_DIR = Path.home() / ".wiki-builder"
CONFIG_FILE = CONFIG_DIR / "config.json"


def load_config() -> dict:
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}


def save_config(data: dict):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_provider_config(provider: str | None = None) -> dict:
    """
    Returns {"provider": str, "api_key": str, "model": str | None}.
    Resolution order: CLI flag > env vars > saved config.
    """
    cfg = load_config()

    # Determine provider
    resolved_provider = (
        provider
        or os.environ.get("WIKI_PROVIDER")
        or cfg.get("provider")
        or "anthropic"
    )

    # Determine API key for that provider
    if resolved_provider == "anthropic":
        api_key = (
            os.environ.get("ANTHROPIC_API_KEY")
            or cfg.get("anthropic_api_key")
            or cfg.get("api_key")  # legacy key name
            or ""
        )
        if not api_key:
            raise ValueError(
                "No Anthropic API key found. Set ANTHROPIC_API_KEY env var "
                "or run: wiki config --provider anthropic --api-key <key>"
            )
    elif resolved_provider == "openai":
        api_key = (
            os.environ.get("OPENAI_API_KEY")
            or cfg.get("openai_api_key")
            or ""
        )
        if not api_key:
            raise ValueError(
                "No OpenAI API key found. Set OPENAI_API_KEY env var "
                "or run: wiki config --provider openai --api-key <key>"
            )
    else:
        raise ValueError(f"Unknown provider: {resolved_provider!r}. Use 'anthropic' or 'openai'.")

    return {
        "provider": resolved_provider,
        "api_key": api_key,
        "model": cfg.get("model"),
    }


def find_wiki_root(start: Path) -> Path | None:
    """Walk up from start looking for a directory containing schema.md."""
    current = start.resolve()
    for _ in range(10):
        if (current / "schema.md").exists():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None
