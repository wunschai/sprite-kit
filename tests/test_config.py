"""Tests for sprite_kit.config — covers AC-7 priority order + missing-key error."""

import pytest

from sprite_kit.config import DEFAULTS, ConfigError, load_config, require_api_key

SPRITE_KIT_ENV_KEYS = (
    "OPENAI_API_KEY",
    "SPRITE_KIT_MODEL",
    "SPRITE_KIT_QUALITY",
    "SPRITE_KIT_SIZE",
    "SPRITE_KIT_CHROMA_KEY",
    "SPRITE_KIT_CHROMA_FUZZ",
    "SPRITE_KIT_OUTPUT_DIR",
)


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch):
    """Strip every relevant env var before each test for hermetic runs."""
    for key in SPRITE_KIT_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_defaults_returned_when_no_overrides(tmp_path):
    missing_env = tmp_path / "no-such.env"

    cfg = load_config(cli_args=None, env_file=missing_env)

    assert cfg["model"] == DEFAULTS["model"]
    assert cfg["quality"] == DEFAULTS["quality"]
    assert cfg["size"] == DEFAULTS["size"]
    assert cfg["chroma_key"] == DEFAULTS["chroma_key"]
    assert cfg["chroma_fuzz"] == DEFAULTS["chroma_fuzz"]
    assert cfg["output_dir"] == DEFAULTS["output_dir"]
    assert cfg["openai_api_key"] is None


def test_env_overrides_defaults(monkeypatch):
    monkeypatch.setenv("SPRITE_KIT_MODEL", "test-model")

    cfg = load_config()

    assert cfg["model"] == "test-model"


def test_dotenv_overrides_defaults_but_below_env(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("SPRITE_KIT_MODEL=from-dotenv\n")
    monkeypatch.setenv("SPRITE_KIT_MODEL", "from-env")

    cfg = load_config(env_file=env_file)

    assert cfg["model"] == "from-env"


def test_dotenv_used_when_env_unset(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("SPRITE_KIT_MODEL=from-dotenv\n")

    cfg = load_config(env_file=env_file)

    assert cfg["model"] == "from-dotenv"


def test_cli_overrides_all(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("SPRITE_KIT_MODEL=from-dotenv\n")
    monkeypatch.setenv("SPRITE_KIT_MODEL", "from-env")

    cfg = load_config(cli_args={"model": "from-cli"}, env_file=env_file)

    assert cfg["model"] == "from-cli"


def test_chroma_fuzz_cast_to_int(monkeypatch):
    monkeypatch.setenv("SPRITE_KIT_CHROMA_FUZZ", "20")

    cfg = load_config()

    assert cfg["chroma_fuzz"] == 20
    assert isinstance(cfg["chroma_fuzz"], int)


def test_chroma_fuzz_from_dotenv_cast_to_int(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("SPRITE_KIT_CHROMA_FUZZ=42\n")

    cfg = load_config(env_file=env_file)

    assert cfg["chroma_fuzz"] == 42
    assert isinstance(cfg["chroma_fuzz"], int)


def test_load_config_does_not_raise_when_key_missing():
    cfg = load_config()

    assert cfg["openai_api_key"] is None


def test_require_api_key_raises_when_missing():
    cfg = load_config()

    with pytest.raises(ConfigError) as exc_info:
        require_api_key(cfg)

    assert "OPENAI_API_KEY" in str(exc_info.value)
    assert ".env" in str(exc_info.value)


def test_require_api_key_returns_when_present(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-123")

    cfg = load_config()
    key = require_api_key(cfg)

    assert key == "sk-test-123"


def test_cli_args_with_none_values_are_ignored(monkeypatch):
    monkeypatch.setenv("SPRITE_KIT_MODEL", "from-env")

    cfg = load_config(cli_args={"model": None, "quality": None})

    assert cfg["model"] == "from-env"
    assert cfg["quality"] == DEFAULTS["quality"]


def test_cli_args_missing_keys_do_not_override(monkeypatch):
    monkeypatch.setenv("SPRITE_KIT_MODEL", "from-env")

    cfg = load_config(cli_args={"quality": "high"})

    assert cfg["model"] == "from-env"
    assert cfg["quality"] == "high"


def test_openai_api_key_from_env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env-key")

    cfg = load_config()

    assert cfg["openai_api_key"] == "sk-env-key"


def test_openai_api_key_from_dotenv(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_API_KEY=sk-dotenv-key\n")

    cfg = load_config(env_file=env_file)

    assert cfg["openai_api_key"] == "sk-dotenv-key"


def test_dotenv_does_not_pollute_os_environ(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("SPRITE_KIT_MODEL=from-dotenv\n")

    load_config(env_file=env_file)

    import os

    assert "SPRITE_KIT_MODEL" not in os.environ
