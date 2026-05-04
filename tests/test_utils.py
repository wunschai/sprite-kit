"""Tests for sprite_kit.utils — file naming, output dirs, logging."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from sprite_kit.utils import ensure_output_dir, get_logger, next_available_path

# --------------------------------------------------------------------------- #
# next_available_path  (ADR-3)
# --------------------------------------------------------------------------- #


class TestNextAvailablePath:
    def test_returns_path_unchanged_when_not_exists(self, tmp_path: Path):
        target = tmp_path / "frame_001.png"

        result = next_available_path(target)

        assert result == target

    def test_appends_dash_2_when_target_exists(self, tmp_path: Path):
        target = tmp_path / "frame_001.png"
        target.write_bytes(b"existing")

        result = next_available_path(target)

        assert result == tmp_path / "frame_001-2.png"

    def test_increments_to_dash_3_when_dash_2_also_exists(self, tmp_path: Path):
        (tmp_path / "frame_001.png").write_bytes(b"a")
        (tmp_path / "frame_001-2.png").write_bytes(b"b")

        result = next_available_path(tmp_path / "frame_001.png")

        assert result == tmp_path / "frame_001-3.png"

    def test_handles_json_extension(self, tmp_path: Path):
        (tmp_path / "atlas.json").write_text("{}")

        result = next_available_path(tmp_path / "atlas.json")

        assert result == tmp_path / "atlas-2.json"

    def test_handles_gif_extension(self, tmp_path: Path):
        (tmp_path / "anim.gif").write_bytes(b"GIF")

        result = next_available_path(tmp_path / "anim.gif")

        assert result == tmp_path / "anim-2.gif"

    def test_accepts_string_path(self, tmp_path: Path):
        target = tmp_path / "out.png"

        result = next_available_path(str(target))

        assert isinstance(result, Path)
        assert result == target

    def test_skips_already_used_suffixes_in_sequence(self, tmp_path: Path):
        # gap: stem.png and stem-2.png exist, stem-3.png does NOT
        (tmp_path / "x.png").write_bytes(b"a")
        (tmp_path / "x-2.png").write_bytes(b"b")

        result = next_available_path(tmp_path / "x.png")

        assert result == tmp_path / "x-3.png"


# --------------------------------------------------------------------------- #
# ensure_output_dir
# --------------------------------------------------------------------------- #


class TestEnsureOutputDir:
    def test_creates_missing_directory(self, tmp_path: Path):
        target = tmp_path / "new_dir"

        result = ensure_output_dir(target)

        assert result.exists()
        assert result.is_dir()
        assert result == target.resolve()

    def test_creates_nested_directories(self, tmp_path: Path):
        target = tmp_path / "a" / "b" / "c"

        result = ensure_output_dir(target)

        assert result.exists()
        assert result.is_dir()

    def test_returns_existing_directory_unchanged(self, tmp_path: Path):
        target = tmp_path / "exists"
        target.mkdir()

        result = ensure_output_dir(target)

        assert result == target.resolve()
        assert result.is_dir()

    def test_raises_oserror_when_path_is_existing_file(self, tmp_path: Path):
        target = tmp_path / "a-file.txt"
        target.write_text("hi")

        with pytest.raises(OSError):
            ensure_output_dir(target)

    def test_accepts_string_path(self, tmp_path: Path):
        target = tmp_path / "from_str"

        result = ensure_output_dir(str(target))

        assert result.is_dir()


# --------------------------------------------------------------------------- #
# get_logger
# --------------------------------------------------------------------------- #


class TestGetLogger:
    def test_returns_logger_with_default_name(self):
        logger = get_logger()

        assert isinstance(logger, logging.Logger)
        assert logger.name == "sprite_kit"

    def test_returns_named_logger(self):
        logger = get_logger("sprite_kit.cli")

        assert logger.name == "sprite_kit.cli"

    def test_does_not_duplicate_handlers_when_called_repeatedly(self):
        logger_a = get_logger("sprite_kit.dup_test")
        handlers_after_first = list(logger_a.handlers)

        logger_b = get_logger("sprite_kit.dup_test")

        assert logger_b is logger_a
        assert list(logger_b.handlers) == handlers_after_first

    def test_sets_level_to_info_or_below(self):
        logger = get_logger("sprite_kit.level_test")

        # level must be set (not NOTSET=0) and at most INFO
        assert logger.level != logging.NOTSET
        assert logger.level <= logging.INFO
