"""End-to-end pipeline smoke tests.

These tests mock the OpenAI API call (so no real network / API key needed)
but execute the *real* process + export pipeline. They are NOT marked with
``@pytest.mark.integration`` because the marker is reserved for tests that
hit the real OpenAI endpoint. Those live as commented stubs at the bottom
of this file and must be run manually with ``pytest -m integration``.
"""

from __future__ import annotations

import base64
import json
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PIL import Image, ImageDraw

from sprite_kit.cli import main


def _build_fire_mage_sheet() -> bytes:
    """Build a fire-mage-like 1x3 sheet on #FF00FF magenta background.

    Three cells with three different shapes so QC sees real, distinct content:
      - cell 0: solid red square (mage body)
      - cell 1: orange flame triangle
      - cell 2: yellow projectile circle
    """
    cell = 64
    cols = 3
    img = Image.new("RGB", (cell * cols, cell), (255, 0, 255))
    draw = ImageDraw.Draw(img)

    # cell 0 — mage body
    draw.rectangle((10, 14, 50, 54), fill=(200, 30, 30))
    # cell 1 — flame triangle
    draw.polygon([(64 + 32, 10), (64 + 10, 54), (64 + 54, 54)], fill=(255, 140, 0))
    # cell 2 — projectile circle
    draw.ellipse((128 + 18, 18, 128 + 46, 46), fill=(255, 230, 60))

    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _patch_generate(monkeypatch, raw_bytes: bytes) -> MagicMock:
    client = MagicMock()
    datum = MagicMock()
    datum.b64_json = base64.b64encode(raw_bytes).decode("ascii")
    response = MagicMock()
    response.data = [datum]
    client.images.generate.return_value = response

    monkeypatch.setattr("sprite_kit.generate._build_openai_client", lambda api_key: client)
    return client


@pytest.fixture
def fake_api_key(monkeypatch):
    """Provide a fake OPENAI_API_KEY for mocked-pipeline tests only.

    Not autouse — the real-API smoke tests at the bottom must keep the
    user's actual environment intact.
    """
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake")
    for k in (
        "SPRITE_KIT_MODEL",
        "SPRITE_KIT_QUALITY",
        "SPRITE_KIT_SIZE",
        "SPRITE_KIT_CHROMA_KEY",
        "SPRITE_KIT_CHROMA_FUZZ",
        "SPRITE_KIT_OUTPUT_DIR",
    ):
        monkeypatch.delenv(k, raising=False)


def test_pipeline_smoke_fire_mage_writes_all_formats(tmp_path: Path, monkeypatch, fake_api_key):
    """Mock generate, run real process + export end-to-end. AC-1 + AC-4."""
    sheet_bytes = _build_fire_mage_sheet()
    _patch_generate(monkeypatch, sheet_bytes)

    rc = main(
        [
            "pipeline",
            "--prompt",
            "fire mage cast animation with projectile and impact",
            "--template",
            "pixel_art",
            "--frames",
            "3",
            "--layout",
            "1x3",
            "--format",
            "png",
            "sheet",
            "gif",
            "atlas",
            "--output",
            str(tmp_path),
        ]
    )

    assert rc == 0, "pipeline should exit 0 on success"

    # Individual frames
    frame_files = sorted(tmp_path.glob("frame_*.png"))
    assert len(frame_files) == 3, f"expected 3 frame PNGs, got {frame_files}"
    assert [p.name for p in frame_files] == [
        "frame_001.png",
        "frame_002.png",
        "frame_003.png",
    ]

    # Sheet PNG (any *.png besides frame_*)
    sheets = [p for p in tmp_path.glob("*.png") if not p.name.startswith("frame_")]
    assert len(sheets) >= 1, "sprite sheet PNG missing"

    # GIF
    gifs = list(tmp_path.glob("*.gif"))
    assert len(gifs) == 1, f"expected exactly one GIF, got {gifs}"

    # Atlas JSON + metadata JSON
    json_files = {p.name for p in tmp_path.glob("*.json")}
    assert "metadata.json" in json_files, f"metadata.json missing from {json_files}"
    atlas_jsons = [p for p in tmp_path.glob("*.json") if p.name != "metadata.json"]
    assert len(atlas_jsons) >= 1, "atlas JSON missing"

    # Validate atlas schema
    atlas = json.loads(atlas_jsons[0].read_text())
    assert "frames" in atlas and "meta" in atlas
    assert len(atlas["frames"]) == 3
    meta = atlas["meta"]
    assert {"image", "size", "scale", "format"} <= set(meta.keys())
    assert {"w", "h"} <= set(meta["size"].keys())

    # Validate metadata content
    meta_payload = json.loads((tmp_path / "metadata.json").read_text())
    assert meta_payload["template"] == "pixel_art"
    assert meta_payload["frames"] == 3
    assert meta_payload["layout"] == "1x3"
    assert "prompt" in meta_payload


def test_pipeline_with_force_overwrites_existing(tmp_path: Path, monkeypatch, fake_api_key):
    """--force should overwrite rather than auto-suffix."""
    _patch_generate(monkeypatch, _build_fire_mage_sheet())

    # Pre-create a frame file to provoke the suffix path
    (tmp_path / "frame_001.png").write_bytes(b"old")

    rc = main(
        [
            "pipeline",
            "--prompt",
            "x",
            "--frames",
            "3",
            "--layout",
            "1x3",
            "--format",
            "png",
            "--output",
            str(tmp_path),
            "--force",
        ]
    )

    assert rc == 0
    # No -2 suffix appears with --force
    assert not (tmp_path / "frame_001-2.png").exists()


def test_pipeline_without_force_suffixes_on_conflict(tmp_path: Path, monkeypatch, fake_api_key):
    """ADR-3: existing files must not be overwritten unless --force."""
    _patch_generate(monkeypatch, _build_fire_mage_sheet())

    sentinel = tmp_path / "frame_001.png"
    sentinel.write_bytes(b"do-not-touch")

    rc = main(
        [
            "pipeline",
            "--prompt",
            "x",
            "--frames",
            "3",
            "--layout",
            "1x3",
            "--format",
            "png",
            "--output",
            str(tmp_path),
        ]
    )

    assert rc == 0
    assert sentinel.read_bytes() == b"do-not-touch"
    # First new frame should land at the -2 suffix
    assert (tmp_path / "frame_001-2.png").exists()


# ---------------------------------------------------------------------------
# Real-API integration tests (manual, skipped unless explicitly requested)
# ---------------------------------------------------------------------------
#
# Run with:  pytest -m integration tests/integration/test_pipeline.py
#
# These actually call the OpenAI Image API and cost real money. Each template
# is exercised once to verify AC-5 (template loading + style injection) end
# to end. Implementations are intentionally minimal — they only assert the
# pipeline returns 0 and writes the expected files — so a single API failure
# doesn't drown out the signal.


@pytest.mark.integration
@pytest.mark.parametrize(
    "template",
    ["pixel_art", "brutalism", "retro_futurism", "tech_futurism"],
)
def test_real_api_each_template_smoke(tmp_path: Path, template: str):  # pragma: no cover - manual
    """Run the full pipeline against the real OpenAI API for each template.

    Skipped by default. Requires a valid OPENAI_API_KEY in the environment.
    """
    import os

    if not os.environ.get("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set; skipping real-API smoke test.")

    rc = main(
        [
            "pipeline",
            "--prompt",
            "simple test sprite",
            "--template",
            template,
            "--frames",
            "3",
            "--layout",
            "1x3",
            "--format",
            "png",
            "--output",
            str(tmp_path),
        ]
    )

    assert rc == 0
    assert list(tmp_path.glob("frame_*.png")), "no frames written"
