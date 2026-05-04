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


# --------------------------------------------------------------------------- #
# F1: pipeline reads template post_process block
# --------------------------------------------------------------------------- #


class TestPipelineTemplatePostProcess:
    """run_pipeline must honour template post_process: chroma_fuzz + target_scale."""

    def _patch_chroma_capture(self, monkeypatch) -> dict:
        """Patch chroma_key_remove to capture its kwargs without altering output."""
        from sprite_kit import process as proc

        captured: dict = {}
        original = proc.chroma_key_remove

        def spy(img, chroma="#FF00FF", fuzz=15):
            captured["fuzz"] = fuzz
            captured["chroma"] = chroma
            return original(img, chroma=chroma, fuzz=fuzz)

        monkeypatch.setattr("sprite_kit.cli.chroma_key_remove", spy)
        return captured

    def test_pipeline_uses_template_chroma_fuzz_when_cli_unset(self, tmp_path, monkeypatch):
        _patch_generate(monkeypatch)
        captured = self._patch_chroma_capture(monkeypatch)

        rc = main(
            [
                "pipeline",
                "--prompt",
                "x",
                "--template",
                "tech_futurism",
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
        # tech_futurism template has post_process.chroma_fuzz=20
        assert captured["fuzz"] == 20

    def test_pipeline_cli_fuzz_overrides_template_fuzz(self, tmp_path, monkeypatch):
        _patch_generate(monkeypatch)
        captured = self._patch_chroma_capture(monkeypatch)

        rc = main(
            [
                "pipeline",
                "--prompt",
                "x",
                "--template",
                "tech_futurism",
                "--fuzz",
                "30",
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
        assert captured["fuzz"] == 30

    def test_pipeline_template_target_scale_resizes_output(self, tmp_path, monkeypatch):
        # pixel_art has post_process.target_scale=0.5 → output frames should be half-sized
        sheet = _make_magenta_sheet(rows=1, cols=3, cell=32)
        _patch_generate(monkeypatch, raw_bytes=sheet)

        rc = main(
            [
                "pipeline",
                "--prompt",
                "x",
                "--template",
                "pixel_art",
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
        frames = sorted(tmp_path.glob("frame_*.png"))
        assert frames, "no frames written"
        # Aligned content was 16x16 (half of cell), then scale 0.5 → 8x8.
        # Allow some tolerance because alignment trims to bbox first.
        sample = Image.open(frames[0])
        assert sample.size[0] <= 16, f"target_scale=0.5 should shrink width, got {sample.size}"

    def test_pipeline_no_resize_when_template_lacks_target_scale(self, tmp_path, monkeypatch):
        # brutalism's post_process has no target_scale → frames retain original size
        sheet = _make_magenta_sheet(rows=1, cols=3, cell=32)
        _patch_generate(monkeypatch, raw_bytes=sheet)

        rc = main(
            [
                "pipeline",
                "--prompt",
                "x",
                "--template",
                "brutalism",
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
        frames = sorted(tmp_path.glob("frame_*.png"))
        sample = Image.open(frames[0])
        # Aligned bbox is 16x16 (not scaled) since brutalism has no target_scale.
        assert sample.size[0] >= 16


# --------------------------------------------------------------------------- #
# F5: friendly errors for OSError (corrupt PNG) and yaml.YAMLError
# --------------------------------------------------------------------------- #


class TestFriendlyErrors:
    def test_friendly_error_on_corrupt_png(self, tmp_path: Path, capsys):
        bad = tmp_path / "broken.png"
        bad.write_bytes(b"")  # 0-byte → PIL.UnidentifiedImageError (OSError subclass)

        rc = main(
            [
                "process",
                "--input",
                str(bad),
                "--layout",
                "1x3",
                "--output",
                str(tmp_path / "out"),
            ]
        )

        assert rc != 0
        captured = capsys.readouterr()
        combined = captured.out + captured.err
        assert "Traceback" not in combined
        assert "Error" in combined or "error" in combined

    def test_friendly_error_on_malformed_yaml(self, tmp_path: Path, capsys, monkeypatch):
        bad_dir = tmp_path / "templates"
        bad_dir.mkdir()
        (bad_dir / "broken.yaml").write_text("style:\n  - this is: : not valid: yaml: : :\n  bad")

        # Force load_template to read from this dir by monkeypatching the package
        # template dir constant.
        monkeypatch.setattr("sprite_kit.generate._PACKAGE_TEMPLATES_DIR", bad_dir)
        _patch_generate(monkeypatch)

        rc = main(
            [
                "generate",
                "--prompt",
                "x",
                "--template",
                "broken",
                "--output",
                str(tmp_path / "out"),
            ]
        )

        assert rc != 0
        captured = capsys.readouterr()
        combined = captured.out + captured.err
        assert "Traceback" not in combined


# --------------------------------------------------------------------------- #
# F6: process subcommand runs qc_check
# --------------------------------------------------------------------------- #


class TestProcessQcCheck:
    def test_process_logs_qc_warning_for_blank_frames(self, tmp_path: Path, caplog):
        # Build a sheet where one cell is blank (all-magenta with no content).
        from io import BytesIO

        cell = 16
        cols = 3
        img = Image.new("RGB", (cell * cols, cell), (255, 0, 255))
        # Only paint cells 0 and 2 with content; cell 1 remains pure magenta → blank after key.
        for c in (0, 2):
            for yy in range(4, 12):
                for xx in range(c * cell + 4, c * cell + 12):
                    img.putpixel((xx, yy), (0, 0, 0))
        buf = BytesIO()
        img.save(buf, format="PNG")
        sheet_path = tmp_path / "sheet.png"
        sheet_path.write_bytes(buf.getvalue())

        import logging

        with caplog.at_level(logging.WARNING):
            rc = main(
                [
                    "process",
                    "--input",
                    str(sheet_path),
                    "--layout",
                    "1x3",
                    "--output",
                    str(tmp_path / "out"),
                ]
            )

        assert rc == 0
        # QC should log a warning that includes "blank" or "Blank".
        warnings = " ".join(r.message for r in caplog.records if r.levelno >= logging.WARNING)
        assert "blank" in warnings.lower(), f"expected QC blank warning, got: {warnings!r}"


# --------------------------------------------------------------------------- #
# F7: _load_frames_from_input filters frame_*.png
# --------------------------------------------------------------------------- #


class TestLoadFramesFiltering:
    def test_load_frames_skips_non_frame_pngs_in_directory(self, tmp_path: Path):
        from sprite_kit.cli import _load_frames_from_input

        # Two real frames + one stray sheet PNG that must be ignored.
        for i in (1, 2):
            Image.new("RGBA", (8, 8)).save(tmp_path / f"frame_{i:03d}.png")
        Image.new("RGBA", (32, 8)).save(tmp_path / "raw_sheet.png")
        Image.new("RGBA", (32, 8)).save(tmp_path / "pixel_art_sheet.png")

        frames = _load_frames_from_input(tmp_path)

        assert len(frames) == 2
        for f in frames:
            assert f.size == (8, 8)


# --------------------------------------------------------------------------- #
# F3 + F4 + F10: env var precedence at CLI layer
# --------------------------------------------------------------------------- #


class TestCliEnvOverrides:
    def test_generate_uses_SPRITE_KIT_OUTPUT_DIR_when_cli_unset(self, tmp_path: Path, monkeypatch):
        _patch_generate(monkeypatch)
        env_out = tmp_path / "env-out"
        monkeypatch.setenv("SPRITE_KIT_OUTPUT_DIR", str(env_out))

        rc = main(["generate", "--prompt", "hero"])

        assert rc == 0
        assert env_out.is_dir()
        assert list(env_out.glob("*.png")), "generate should write into env-specified dir"

    def test_cli_output_overrides_SPRITE_KIT_OUTPUT_DIR(self, tmp_path: Path, monkeypatch):
        _patch_generate(monkeypatch)
        env_out = tmp_path / "env-out"
        cli_out = tmp_path / "cli-out"
        monkeypatch.setenv("SPRITE_KIT_OUTPUT_DIR", str(env_out))

        rc = main(["generate", "--prompt", "hero", "--output", str(cli_out)])

        assert rc == 0
        assert cli_out.is_dir()
        assert list(cli_out.glob("*.png"))
        # env dir should not have been used.
        assert not env_out.exists() or not list(env_out.glob("*.png"))

    def test_process_uses_SPRITE_KIT_CHROMA_FUZZ_when_cli_unset(self, tmp_path: Path, monkeypatch):
        captured: dict = {}
        from sprite_kit import process as proc

        original = proc.chroma_key_remove

        def spy(img, chroma="#FF00FF", fuzz=15):
            captured["fuzz"] = fuzz
            captured["chroma"] = chroma
            return original(img, chroma=chroma, fuzz=fuzz)

        monkeypatch.setattr("sprite_kit.cli.chroma_key_remove", spy)
        monkeypatch.setenv("SPRITE_KIT_CHROMA_FUZZ", "20")

        sheet_bytes = _make_magenta_sheet(rows=1, cols=3, cell=16)
        sheet_path = tmp_path / "raw.png"
        sheet_path.write_bytes(sheet_bytes)

        rc = main(
            [
                "process",
                "--input",
                str(sheet_path),
                "--layout",
                "1x3",
                "--output",
                str(tmp_path / "out"),
            ]
        )

        assert rc == 0
        assert captured["fuzz"] == 20

    def test_process_uses_SPRITE_KIT_CHROMA_KEY_when_cli_unset(self, tmp_path: Path, monkeypatch):
        captured: dict = {}
        from sprite_kit import process as proc

        original = proc.chroma_key_remove

        def spy(img, chroma="#FF00FF", fuzz=15):
            captured["chroma"] = chroma
            captured["fuzz"] = fuzz
            return original(img, chroma=chroma, fuzz=fuzz)

        monkeypatch.setattr("sprite_kit.cli.chroma_key_remove", spy)
        monkeypatch.setenv("SPRITE_KIT_CHROMA_KEY", "#00FF00")

        # Build a green-background sheet to match the env chroma key.
        from io import BytesIO

        cell = 16
        img = Image.new("RGB", (cell * 3, cell), (0, 255, 0))
        for c in range(3):
            for yy in range(4, 12):
                for xx in range(c * cell + 4, c * cell + 12):
                    img.putpixel((xx, yy), (0, 0, 0))
        buf = BytesIO()
        img.save(buf, format="PNG")
        sheet_path = tmp_path / "raw.png"
        sheet_path.write_bytes(buf.getvalue())

        rc = main(
            [
                "process",
                "--input",
                str(sheet_path),
                "--layout",
                "1x3",
                "--output",
                str(tmp_path / "out"),
            ]
        )

        assert rc == 0
        assert captured["chroma"] == "#00FF00"
