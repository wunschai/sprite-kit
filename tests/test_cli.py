"""Tests for sprite_kit.cli — argparse subcommand dispatch + friendly errors."""

from __future__ import annotations

import base64
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PIL import Image

from sprite_kit.cli import main

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
    for key in SPRITE_KIT_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake")


def _make_magenta_sheet(rows: int = 1, cols: int = 3, cell: int = 16) -> bytes:
    """Build a small magenta-background sheet PNG, returned as raw bytes."""
    from io import BytesIO

    img = Image.new("RGB", (cell * cols, cell * rows), (255, 0, 255))
    # paint a black square in the middle of each cell so frames have content
    for r in range(rows):
        for c in range(cols):
            x = c * cell + cell // 4
            y = r * cell + cell // 4
            for yy in range(y, y + cell // 2):
                for xx in range(x, x + cell // 2):
                    img.putpixel((xx, yy), (0, 0, 0))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _patch_generate(monkeypatch, raw_bytes: bytes | None = None) -> MagicMock:
    """Replace the OpenAI client used by generate_sprite with a MagicMock."""
    if raw_bytes is None:
        raw_bytes = _make_magenta_sheet()

    client = MagicMock()
    datum = MagicMock()
    datum.b64_json = base64.b64encode(raw_bytes).decode("ascii")
    response = MagicMock()
    response.data = [datum]
    client.images.generate.return_value = response

    # Patch the OpenAI client builder where generate.py imports it.
    monkeypatch.setattr("sprite_kit.generate._build_openai_client", lambda api_key: client)
    return client


# --------------------------------------------------------------------------- #
# --help and dispatch
# --------------------------------------------------------------------------- #


class TestHelp:
    def test_top_level_help_returns_zero(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        assert exc_info.value.code == 0
        out = capsys.readouterr().out
        assert "generate" in out
        assert "process" in out
        assert "export" in out
        assert "pipeline" in out

    @pytest.mark.parametrize("subcommand", ["generate", "process", "export", "pipeline"])
    def test_subcommand_help_returns_zero(self, capsys, subcommand):
        with pytest.raises(SystemExit) as exc_info:
            main([subcommand, "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr().out
        assert subcommand in captured.lower() or "usage" in captured.lower()


class TestUnknownSubcommand:
    def test_unknown_subcommand_returns_nonzero(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["bogus"])
        assert exc_info.value.code != 0

    def test_no_subcommand_returns_nonzero(self):
        rc = main([])
        assert rc != 0


# --------------------------------------------------------------------------- #
# missing required args
# --------------------------------------------------------------------------- #


class TestMissingRequiredArgs:
    def test_generate_without_prompt_exits_nonzero(self):
        with pytest.raises(SystemExit) as exc_info:
            main(["generate", "--output", "/tmp/x"])
        assert exc_info.value.code != 0

    def test_process_without_input_exits_nonzero(self):
        with pytest.raises(SystemExit) as exc_info:
            main(["process", "--layout", "1x3"])
        assert exc_info.value.code != 0

    def test_process_without_layout_exits_nonzero(self):
        with pytest.raises(SystemExit) as exc_info:
            main(["process", "--input", "/tmp/in.png"])
        assert exc_info.value.code != 0

    def test_export_without_input_exits_nonzero(self):
        with pytest.raises(SystemExit) as exc_info:
            main(["export"])
        assert exc_info.value.code != 0

    def test_pipeline_without_prompt_exits_nonzero(self):
        with pytest.raises(SystemExit) as exc_info:
            main(["pipeline"])
        assert exc_info.value.code != 0


# --------------------------------------------------------------------------- #
# generate subcommand happy path
# --------------------------------------------------------------------------- #


class TestGenerateSubcommand:
    def test_generate_writes_raw_png(self, tmp_path: Path, monkeypatch):
        _patch_generate(monkeypatch)

        rc = main(
            [
                "generate",
                "--prompt",
                "fire mage",
                "--frames",
                "3",
                "--layout",
                "1x3",
                "--output",
                str(tmp_path),
            ]
        )

        assert rc == 0
        pngs = list(tmp_path.glob("*.png"))
        assert len(pngs) == 1

    def test_generate_force_overwrites_existing(self, tmp_path: Path, monkeypatch):
        _patch_generate(monkeypatch)
        # Pre-create a file that would normally trigger the suffix.
        existing = tmp_path / "raw_sheet.png"
        existing.write_bytes(b"old")

        rc = main(
            [
                "generate",
                "--prompt",
                "x",
                "--output",
                str(tmp_path),
                "--force",
            ]
        )

        assert rc == 0
        # With --force the original file should have been overwritten;
        # without --force a -2 suffix file would appear.
        assert not (tmp_path / "raw_sheet-2.png").exists()
        # File must still exist and not be the placeholder.
        assert existing.exists()
        assert existing.read_bytes() != b"old"

    def test_generate_without_force_uses_suffix_on_conflict(self, tmp_path: Path, monkeypatch):
        _patch_generate(monkeypatch)
        existing = tmp_path / "raw_sheet.png"
        existing.write_bytes(b"untouched")

        rc = main(
            [
                "generate",
                "--prompt",
                "x",
                "--output",
                str(tmp_path),
            ]
        )

        assert rc == 0
        assert existing.read_bytes() == b"untouched"
        assert (tmp_path / "raw_sheet-2.png").exists()


# --------------------------------------------------------------------------- #
# friendly error: missing API key
# --------------------------------------------------------------------------- #


class TestMissingApiKey:
    def test_generate_without_api_key_prints_friendly_error(
        self, tmp_path: Path, monkeypatch, capsys
    ):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        rc = main(
            [
                "generate",
                "--prompt",
                "test",
                "--output",
                str(tmp_path),
            ]
        )

        assert rc != 0
        captured = capsys.readouterr()
        combined = captured.out + captured.err
        assert "OPENAI_API_KEY" in combined
        # No raw traceback noise.
        assert "Traceback" not in combined


# --------------------------------------------------------------------------- #
# process subcommand
# --------------------------------------------------------------------------- #


class TestProcessSubcommand:
    def test_process_writes_individual_frames(self, tmp_path: Path):
        sheet_bytes = _make_magenta_sheet(rows=1, cols=3, cell=16)
        sheet_path = tmp_path / "raw.png"
        sheet_path.write_bytes(sheet_bytes)
        out_dir = tmp_path / "out"

        rc = main(
            [
                "process",
                "--input",
                str(sheet_path),
                "--layout",
                "1x3",
                "--output",
                str(out_dir),
            ]
        )

        assert rc == 0
        frames = sorted(out_dir.glob("frame_*.png"))
        assert len(frames) == 3
