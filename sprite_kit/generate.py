"""Sprite-sheet generation: prompt assembly, YAML template loading, OpenAI call.

Covers AC-5 (template loading + auto-injected chroma/consistency directives) and
AC-7 (friendly error when ``OPENAI_API_KEY`` is missing).
"""

from __future__ import annotations

import base64
import binascii
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .config import load_config, require_api_key

_PACKAGE_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


class TemplateError(Exception):
    """Raised when a template file is missing, malformed, or extends a missing base."""


class GenerateError(Exception):
    """Raised when the OpenAI image API returns an unusable payload."""


# ---------------------------------------------------------------------------
# Template loading
# ---------------------------------------------------------------------------


def load_template(
    name: str,
    templates_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Load a YAML template by name, resolving ``extends: base`` inheritance.

    Args:
        name: Template name without ``.yaml`` extension (e.g. ``"pixel_art"``).
        templates_dir: Directory to search. Defaults to the repo-level
            ``templates/`` directory.

    Returns:
        Merged dict with keys ``version``, ``base``, ``style``, ``variables``.

    Raises:
        TemplateError: If the named template (or its ``extends`` parent) is missing.
    """
    search_dir = Path(templates_dir) if templates_dir is not None else _PACKAGE_TEMPLATES_DIR
    raw = _read_yaml(name, search_dir)
    parent_name = raw.get("extends")
    if parent_name is None:
        return raw
    parent = _read_yaml(parent_name, search_dir)
    return _merge_template(parent, raw)


def _read_yaml(name: str, search_dir: Path) -> dict[str, Any]:
    path = search_dir / f"{name}.yaml"
    if not path.is_file():
        available = sorted(p.stem for p in search_dir.glob("*.yaml"))
        listed = ", ".join(available) if available else "(none)"
        raise TemplateError(
            f"Template '{name}' not found in {search_dir}. Available templates: {listed}."
        )
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise TemplateError(f"Template '{name}' must be a YAML mapping, got {type(data).__name__}.")
    return data


def _merge_template(parent: dict[str, Any], child: dict[str, Any]) -> dict[str, Any]:
    """Shallow-merge child onto parent; nested dicts are merged one level deep."""
    merged: dict[str, Any] = dict(parent)
    for key, value in child.items():
        if key == "extends":
            continue
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            inner = dict(merged[key])
            inner.update(value)
            merged[key] = inner
        else:
            merged[key] = value
    return merged


# ---------------------------------------------------------------------------
# Prompt assembly
# ---------------------------------------------------------------------------


def assemble_prompt(
    user_prompt: str,
    template: dict[str, Any],
    frame_count: int = 3,
    layout: str = "1x3",
    view: str = "side-view",
) -> str:
    """Assemble the final prompt string sent to the image API.

    The output always contains the chroma-key background and frame-consistency
    directives (AC-5).
    """
    style = template.get("style") or {}
    base = template.get("base") or {}

    prefix = style.get("prompt_prefix", "Create a 2D sprite sheet")
    keywords = style.get("style_keywords") or []
    keywords_line = "Style: " + "; ".join(keywords) + "." if keywords else ""

    lines = [
        f"{prefix} of {user_prompt}.",
    ]
    if keywords_line:
        lines.append(keywords_line)
    lines.append(f"View: {view}. Frame count: {frame_count} in a {layout} layout.")
    for key in ("background", "consistency", "margin", "separation"):
        value = base.get(key)
        if value:
            lines.append(value)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# OpenAI call
# ---------------------------------------------------------------------------


def generate_sprite(
    prompt: str,
    template: str = "pixel_art",
    frames: int = 3,
    layout: str = "1x3",
    size: str | None = None,
    quality: str | None = None,
    *,
    cli_args: dict | None = None,
    client: Any = None,
) -> tuple[bytes, str, dict]:
    """Generate a sprite-sheet PNG via the OpenAI image API.

    Args:
        prompt: User-supplied subject/action description.
        template: Template name (default ``"pixel_art"``).
        frames: Number of frames the sheet should depict.
        layout: Layout string like ``"1x3"`` / ``"2x2"``.
        size: Override the template's ``size_recommendation``.
        quality: Override the template's ``quality_recommendation``.
        cli_args: Optional CLI overrides forwarded to :func:`load_config`.
        client: Optional pre-built OpenAI client (used by tests). When ``None``
            an :class:`openai.OpenAI` instance is constructed from the resolved
            API key.

    Returns:
        ``(raw_png_bytes, used_prompt, metadata)``. ``metadata`` includes
        ``model``, ``quality``, ``size``, ``template``, ``frames``, ``layout``,
        ``prompt`` and ``timestamp``.

    Raises:
        ConfigError: When ``OPENAI_API_KEY`` is missing.
        TemplateError: When ``template`` is unknown.
        GenerateError: When the API response cannot be decoded into PNG bytes.
    """
    cfg = load_config(cli_args=cli_args)
    api_key = require_api_key(cfg)

    tpl = load_template(template)
    final_prompt = assemble_prompt(prompt, tpl, frame_count=frames, layout=layout)

    style = tpl.get("style") or {}
    effective_size = size or style.get("size_recommendation") or cfg["size"]
    effective_quality = quality or style.get("quality_recommendation") or cfg["quality"]
    model = cfg["model"]

    api_client = client if client is not None else _build_openai_client(api_key)

    try:
        response = api_client.images.generate(
            model=model,
            prompt=final_prompt,
            size=effective_size,
            quality=effective_quality,
            output_format="png",
            n=1,
        )
    except Exception as exc:  # noqa: BLE001 — wrap any SDK error with an actionable message
        raise GenerateError(
            f"OpenAI image API call failed: {exc}. "
            "Check network access, API key validity, and request parameters."
        ) from exc

    image_bytes = _decode_png(response)

    metadata = {
        "model": model,
        "quality": effective_quality,
        "size": effective_size,
        "template": template,
        "frames": frames,
        "layout": layout,
        "prompt": final_prompt,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return image_bytes, final_prompt, metadata


def _build_openai_client(api_key: str) -> Any:
    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover — declared in pyproject deps
        raise GenerateError(
            "openai package is not installed. Run `pip install openai>=1.30`."
        ) from exc
    return OpenAI(api_key=api_key)


def _decode_png(response: Any) -> bytes:
    data = getattr(response, "data", None)
    if not data:
        raise GenerateError(
            "OpenAI response contained no image data. "
            "The request may have been filtered or truncated; retry with a simpler prompt."
        )
    b64 = getattr(data[0], "b64_json", None)
    if not b64:
        raise GenerateError("OpenAI response had an empty b64_json field (no image returned).")
    try:
        return base64.b64decode(b64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise GenerateError(
            f"Failed to decode base64 image payload: {exc}. The API response was malformed."
        ) from exc
