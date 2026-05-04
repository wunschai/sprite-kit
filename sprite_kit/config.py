"""Configuration loader with priority CLI > env > .env > defaults."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dotenv import dotenv_values

DEFAULTS: dict[str, Any] = {
    "model": "gpt-image-2",
    "quality": "medium",
    "size": "1536x1024",
    "chroma_key": "#FF00FF",
    "chroma_fuzz": 15,
    "output_dir": "./output",
}

_ENV_VAR_MAP: dict[str, str] = {
    "model": "SPRITE_KIT_MODEL",
    "quality": "SPRITE_KIT_QUALITY",
    "size": "SPRITE_KIT_SIZE",
    "chroma_key": "SPRITE_KIT_CHROMA_KEY",
    "chroma_fuzz": "SPRITE_KIT_CHROMA_FUZZ",
    "output_dir": "SPRITE_KIT_OUTPUT_DIR",
}

_INT_KEYS: frozenset[str] = frozenset({"chroma_fuzz"})

_DEFAULT_DOTENV_PATH = Path(".env")


class ConfigError(Exception):
    """Raised for user-facing configuration problems (missing keys, etc.)."""


def load_config(
    cli_args: dict[str, Any] | None = None,
    env_file: str | Path | None = None,
) -> dict[str, Any]:
    """Load merged config with priority CLI > env > .env > defaults.

    Args:
        cli_args: Optional dict of CLI overrides. Missing keys and ``None``
            values are ignored so callers can pass argparse namespaces directly.
        env_file: Optional path to a ``.env`` file. Defaults to ``./.env`` if
            present; missing files are silently skipped.

    Returns:
        Dict containing ``openai_api_key`` plus every key in :data:`DEFAULTS`.
        ``openai_api_key`` is ``None`` when not supplied — callers should use
        :func:`require_api_key` to enforce its presence with a friendly error.
    """
    dotenv_map = _read_dotenv(env_file)
    cfg: dict[str, Any] = dict(DEFAULTS)

    for key, env_name in _ENV_VAR_MAP.items():
        raw = _resolve(key, env_name, cli_args, dotenv_map)
        if raw is None:
            continue
        cfg[key] = _coerce(key, raw)

    cfg["openai_api_key"] = _resolve_api_key(cli_args, dotenv_map)
    return cfg


def require_api_key(cfg: dict[str, Any]) -> str:
    """Return ``cfg['openai_api_key']`` or raise :class:`ConfigError`.

    Raises:
        ConfigError: When the key is missing or empty, with guidance on how to
            set it.
    """
    key = cfg.get("openai_api_key")
    if not key:
        raise ConfigError(
            "OPENAI_API_KEY is required. "
            "Set it via environment variable or .env file. See .env.example."
        )
    return key


def _read_dotenv(env_file: str | Path | None) -> dict[str, str]:
    path = Path(env_file) if env_file is not None else _DEFAULT_DOTENV_PATH
    if not path.is_file():
        return {}
    return {k: v for k, v in dotenv_values(path).items() if v is not None}


def _resolve(
    key: str,
    env_name: str,
    cli_args: dict[str, Any] | None,
    dotenv_map: dict[str, str],
) -> Any:
    if cli_args is not None:
        cli_value = cli_args.get(key)
        if cli_value is not None:
            return cli_value
    env_value = os.environ.get(env_name)
    if env_value is not None:
        return env_value
    return dotenv_map.get(env_name)


def _resolve_api_key(
    cli_args: dict[str, Any] | None,
    dotenv_map: dict[str, str],
) -> str | None:
    if cli_args is not None:
        cli_value = cli_args.get("openai_api_key")
        if cli_value:
            return cli_value
    env_value = os.environ.get("OPENAI_API_KEY")
    if env_value:
        return env_value
    dotenv_value = dotenv_map.get("OPENAI_API_KEY")
    return dotenv_value or None


def _coerce(key: str, raw: Any) -> Any:
    if key not in _INT_KEYS:
        return raw
    if isinstance(raw, int) and not isinstance(raw, bool):
        return raw
    try:
        return int(str(raw))
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{_ENV_VAR_MAP[key]} must be an integer, got {raw!r}.") from exc
