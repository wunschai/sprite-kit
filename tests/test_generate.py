"""Tests for sprite_kit.generate — covers AC-5 (template loading + auto-injection)
and AC-7 (missing API key error message)."""

from __future__ import annotations

import base64
from unittest.mock import MagicMock

import pytest

from sprite_kit.config import ConfigError
from sprite_kit.generate import (
    GenerateError,
    TemplateError,
    assemble_prompt,
    generate_sprite,
    load_template,
)

SPRITE_KIT_ENV_KEYS = (
    "OPENAI_API_KEY",
    "SPRITE_KIT_MODEL",
    "SPRITE_KIT_QUALITY",
    "SPRITE_KIT_SIZE",
    "SPRITE_KIT_CHROMA_KEY",
    "SPRITE_KIT_CHROMA_FUZZ",
    "SPRITE_KIT_OUTPUT_DIR",
)

# --- a tiny PNG (1x1 magenta) for fake API responses -----------------------
_FAKE_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xfc\xcf"
    b"\xc0\xc0\xc0\x00\x00\x00\x05\x00\x01\xa5\xf6E@\x00\x00\x00\x00IEND"
    b"\xaeB`\x82"
)
_FAKE_B64 = base64.b64encode(_FAKE_PNG_BYTES).decode("ascii")


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch):
    """Strip env vars for hermetic tests."""
    for key in SPRITE_KIT_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def _build_mock_client(b64_payload: str | None = _FAKE_B64) -> MagicMock:
    """Return a MagicMock that mimics the OpenAI client images.generate shape."""
    client = MagicMock()
    datum = MagicMock()
    datum.b64_json = b64_payload
    response = MagicMock()
    response.data = [datum]
    client.images.generate.return_value = response
    return client


# ---------------------------------------------------------------------------
# load_template — Task 2.C.1
# ---------------------------------------------------------------------------


def test_load_template_loads_base_yaml_directly():
    tpl = load_template("base")

    assert tpl["version"] == 1
    assert tpl["base"]["background"] == "Solid #FF00FF magenta background."
    assert "Consistent" in tpl["base"]["consistency"]
    assert tpl["base"]["margin"].startswith("Each frame")
    assert tpl["base"]["separation"].startswith("No overlap")
    assert tpl["variables"]["frame_count"] == 3
    assert tpl["variables"]["layout"] == "1x3"


def test_load_template_resolves_extends_base_for_pixel_art():
    tpl = load_template("pixel_art")

    # base keys merged in
    assert tpl["base"]["background"] == "Solid #FF00FF magenta background."
    assert "consistency" in tpl["base"]
    # style block intact
    assert tpl["style"]["name"] == "pixel_art"
    assert tpl["style"]["prompt_prefix"].startswith("Create a 2D pixel art")
    assert any("16-bit" in kw for kw in tpl["style"]["style_keywords"])
    assert tpl["style"]["size_recommendation"] == "1536x1024"
    assert tpl["style"]["quality_recommendation"] == "medium"
    assert tpl["style"]["post_process"]["resize_method"] == "nearest"


def test_load_template_for_all_four_builtin_templates():
    for name in ("pixel_art", "brutalism", "retro_futurism", "tech_futurism"):
        tpl = load_template(name)
        assert tpl["style"]["name"] == name
        assert tpl["base"]["background"] == "Solid #FF00FF magenta background."
        assert isinstance(tpl["style"]["style_keywords"], list)
        assert tpl["style"]["style_keywords"], f"{name} has empty style_keywords"


def test_load_template_supports_custom_dir(tmp_path):
    base_yaml = tmp_path / "base.yaml"
    base_yaml.write_text(
        "version: 1\n"
        "base:\n"
        "  background: 'BG'\n"
        "  consistency: 'CON'\n"
        "  margin: 'MAR'\n"
        "  separation: 'SEP'\n"
        "variables:\n"
        "  frame_count: 4\n"
        "  layout: '2x2'\n"
        "  view: 'front-view'\n",
        encoding="utf-8",
    )
    custom = tmp_path / "my_style.yaml"
    custom.write_text(
        "extends: base\n"
        "style:\n"
        "  name: 'my_style'\n"
        "  prompt_prefix: 'Custom prefix'\n"
        "  style_keywords: ['flat', 'bold']\n"
        "  size_recommendation: '1024x1024'\n"
        "  quality_recommendation: 'low'\n"
        "  post_process: {resize_method: 'lanczos'}\n",
        encoding="utf-8",
    )

    tpl = load_template("my_style", templates_dir=tmp_path)

    assert tpl["style"]["name"] == "my_style"
    assert tpl["base"]["background"] == "BG"
    assert tpl["variables"]["layout"] == "2x2"


def test_load_template_missing_lists_available(tmp_path):
    (tmp_path / "base.yaml").write_text(
        "version: 1\nbase: {background: x, consistency: x, margin: x, separation: x}\n"
        "variables: {}\n",
        encoding="utf-8",
    )
    (tmp_path / "alpha.yaml").write_text("extends: base\nstyle: {name: alpha}\n", encoding="utf-8")
    (tmp_path / "beta.yaml").write_text("extends: base\nstyle: {name: beta}\n", encoding="utf-8")

    with pytest.raises(TemplateError) as exc_info:
        load_template("nope", templates_dir=tmp_path)

    msg = str(exc_info.value)
    assert "nope" in msg
    assert "alpha" in msg
    assert "beta" in msg


def test_load_template_extends_missing_base_raises(tmp_path):
    bad = tmp_path / "broken.yaml"
    bad.write_text("extends: ghost\nstyle: {name: broken}\n", encoding="utf-8")

    with pytest.raises(TemplateError) as exc_info:
        load_template("broken", templates_dir=tmp_path)

    assert "ghost" in str(exc_info.value)


# ---------------------------------------------------------------------------
# assemble_prompt — Task 2.C.3
# ---------------------------------------------------------------------------


def test_assemble_prompt_injects_chroma_background_line():
    tpl = load_template("pixel_art")

    prompt = assemble_prompt("warrior idle", tpl)

    assert "#FF00FF" in prompt
    assert "Solid #FF00FF magenta background." in prompt


def test_assemble_prompt_injects_consistency_line():
    tpl = load_template("pixel_art")

    prompt = assemble_prompt("warrior idle", tpl)

    assert tpl["base"]["consistency"] in prompt


def test_assemble_prompt_includes_user_subject_and_prefix():
    tpl = load_template("tech_futurism")

    prompt = assemble_prompt("fire mage cast animation", tpl)

    assert "fire mage cast animation" in prompt
    assert tpl["style"]["prompt_prefix"] in prompt


def test_assemble_prompt_includes_all_style_keywords():
    tpl = load_template("brutalism")

    prompt = assemble_prompt("statue", tpl)

    for keyword in tpl["style"]["style_keywords"]:
        assert keyword in prompt


def test_assemble_prompt_substitutes_frame_count_and_layout():
    tpl = load_template("pixel_art")

    prompt = assemble_prompt("hero run", tpl, frame_count=4, layout="2x2", view="front-view")

    assert "4" in prompt
    assert "2x2" in prompt
    assert "front-view" in prompt


def test_assemble_prompt_includes_margin_and_separation_lines():
    tpl = load_template("pixel_art")

    prompt = assemble_prompt("hero", tpl)

    assert tpl["base"]["margin"] in prompt
    assert tpl["base"]["separation"] in prompt


# ---------------------------------------------------------------------------
# generate_sprite — Task 2.C.5
# ---------------------------------------------------------------------------


def test_generate_sprite_returns_tuple(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-123")
    client = _build_mock_client()

    result = generate_sprite("hero idle", template="pixel_art", client=client)

    assert isinstance(result, tuple)
    assert len(result) == 3
    image_bytes, used_prompt, metadata = result
    assert isinstance(image_bytes, bytes)
    assert image_bytes == _FAKE_PNG_BYTES
    assert isinstance(used_prompt, str)
    assert "hero idle" in used_prompt
    assert isinstance(metadata, dict)


def test_generate_sprite_metadata_has_required_keys(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-123")
    client = _build_mock_client()

    _, _, metadata = generate_sprite(
        "hero idle",
        template="pixel_art",
        frames=4,
        layout="2x2",
        client=client,
    )

    for key in ("model", "quality", "size", "template", "frames", "layout", "prompt", "timestamp"):
        assert key in metadata, f"metadata missing key: {key}"
    assert metadata["template"] == "pixel_art"
    assert metadata["frames"] == 4
    assert metadata["layout"] == "2x2"


def test_generate_sprite_calls_client_with_assembled_prompt(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-123")
    client = _build_mock_client()

    generate_sprite("phoenix flap", template="tech_futurism", client=client)

    client.images.generate.assert_called_once()
    kwargs = client.images.generate.call_args.kwargs
    assert "phoenix flap" in kwargs["prompt"]
    assert "#FF00FF" in kwargs["prompt"]
    assert kwargs["model"] == "gpt-image-2"
    assert kwargs["n"] == 1


def test_generate_sprite_uses_template_size_and_quality_by_default(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-123")
    client = _build_mock_client()

    generate_sprite("statue", template="brutalism", client=client)

    kwargs = client.images.generate.call_args.kwargs
    # brutalism recommends 1024x1024
    assert kwargs["size"] == "1024x1024"
    assert kwargs["quality"] == "medium"


def test_generate_sprite_cli_size_overrides_template(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-123")
    client = _build_mock_client()

    generate_sprite(
        "statue",
        template="brutalism",
        size="1536x1024",
        quality="high",
        client=client,
    )

    kwargs = client.images.generate.call_args.kwargs
    assert kwargs["size"] == "1536x1024"
    assert kwargs["quality"] == "high"


def test_generate_sprite_missing_api_key_raises_config_error():
    client = _build_mock_client()

    with pytest.raises(ConfigError) as exc_info:
        generate_sprite("hero", template="pixel_art", client=client)

    assert "OPENAI_API_KEY" in str(exc_info.value)


def test_generate_sprite_unknown_template_raises_template_error(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-123")
    client = _build_mock_client()

    with pytest.raises(TemplateError):
        generate_sprite("hero", template="does_not_exist", client=client)


def test_generate_sprite_empty_b64_raises_generate_error(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-123")
    client = _build_mock_client(b64_payload=None)

    with pytest.raises(GenerateError) as exc_info:
        generate_sprite("hero", template="pixel_art", client=client)

    assert "empty" in str(exc_info.value).lower() or "no image" in str(exc_info.value).lower()


def test_generate_sprite_invalid_b64_raises_generate_error(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-123")
    client = _build_mock_client(b64_payload="!!!not-base64!!!")

    with pytest.raises(GenerateError):
        generate_sprite("hero", template="pixel_art", client=client)


def test_generate_sprite_passes_cli_args_to_config(monkeypatch):
    """CLI api key override should let generate proceed without env key."""
    client = _build_mock_client()

    image_bytes, _, _ = generate_sprite(
        "hero",
        template="pixel_art",
        cli_args={"openai_api_key": "sk-cli-key"},
        client=client,
    )

    assert image_bytes == _FAKE_PNG_BYTES


def test_generate_sprite_used_prompt_matches_metadata_prompt(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-123")
    client = _build_mock_client()

    _, used_prompt, metadata = generate_sprite("hero", template="pixel_art", client=client)

    assert used_prompt == metadata["prompt"]


def test_generate_sprite_includes_status_code_and_request_id_in_error(monkeypatch):
    """SDK exceptions should surface status_code / request_id to aid diagnosis."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-123")

    fake_api_error = type("FakeAPIError", (Exception,), {})
    raised = fake_api_error("rate limited")
    raised.status_code = 429
    raised.request_id = "req_abc123"

    client = MagicMock()
    client.images.generate.side_effect = raised

    with pytest.raises(GenerateError) as exc_info:
        generate_sprite("hero", template="pixel_art", client=client)

    msg = str(exc_info.value)
    assert "status=429" in msg
    assert "request_id=req_abc123" in msg


def test_generate_sprite_omits_diagnostic_fields_when_absent(monkeypatch):
    """Plain exceptions without status_code/request_id should not crash error path."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-123")

    client = MagicMock()
    client.images.generate.side_effect = RuntimeError("network down")

    with pytest.raises(GenerateError) as exc_info:
        generate_sprite("hero", template="pixel_art", client=client)

    msg = str(exc_info.value)
    assert "network down" in msg
    assert "status=" not in msg
    assert "request_id=" not in msg
