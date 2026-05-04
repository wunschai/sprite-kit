"""Tests for sprite_kit.export — covers AC-4 export format correctness."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from sprite_kit.export import (
    export_atlas,
    export_frames,
    export_gif,
    export_metadata,
    export_sheet,
)

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _make_frame(
    width: int = 16,
    height: int = 16,
    color: tuple[int, int, int, int] = (255, 0, 0, 255),
) -> Image.Image:
    """Create a small RGBA frame with a solid color (alpha=255 by default)."""
    return Image.new("RGBA", (width, height), color)


def _make_frames(
    count: int,
    width: int = 16,
    height: int = 16,
) -> list[Image.Image]:
    palette = [
        (255, 0, 0, 255),
        (0, 255, 0, 255),
        (0, 0, 255, 255),
        (255, 255, 0, 255),
    ]
    return [_make_frame(width, height, palette[i % len(palette)]) for i in range(count)]


# --------------------------------------------------------------------------- #
# export_frames
# --------------------------------------------------------------------------- #


class TestExportFrames:
    def test_writes_zero_padded_three_digit_filenames(self, tmp_path: Path):
        frames = _make_frames(3)

        paths = export_frames(frames, tmp_path)

        assert [p.name for p in paths] == [
            "frame_001.png",
            "frame_002.png",
            "frame_003.png",
        ]
        for p in paths:
            assert p.is_file()

    def test_returns_paths_in_same_order_as_frames(self, tmp_path: Path):
        frames = _make_frames(4)

        paths = export_frames(frames, tmp_path)

        assert len(paths) == len(frames)
        assert all(isinstance(p, Path) for p in paths)
        # Re-open and assert color matches input order.
        for original, path in zip(frames, paths, strict=True):
            reloaded = Image.open(path)
            assert reloaded.getpixel((0, 0)) == original.getpixel((0, 0))

    def test_padding_keeps_three_digits_for_up_to_999_frames(self, tmp_path: Path):
        frames = _make_frames(120)

        paths = export_frames(frames, tmp_path)

        # 120 fits in 3 digits (max(3, len("120")) = 3).
        assert paths[0].name == "frame_001.png"
        assert paths[99].name == "frame_100.png"
        assert paths[-1].name == "frame_120.png"

    def test_padding_expands_to_four_digits_at_1000_frames(self, tmp_path: Path):
        # Use tiny 1x1 frames to keep the disk write fast.
        frames = [_make_frame(1, 1) for _ in range(1000)]

        paths = export_frames(frames, tmp_path)

        # max(3, len("1000")) = 4.
        assert paths[0].name == "frame_0001.png"
        assert paths[999].name == "frame_1000.png"

    def test_creates_output_dir_if_missing(self, tmp_path: Path):
        target = tmp_path / "nested" / "output"
        frames = _make_frames(2)

        paths = export_frames(frames, target)

        assert target.is_dir()
        assert all(p.parent == target for p in paths)

    def test_custom_name_prefix(self, tmp_path: Path):
        frames = _make_frames(2)

        paths = export_frames(frames, tmp_path, name_prefix="walk")

        assert paths[0].name == "walk_001.png"
        assert paths[1].name == "walk_002.png"

    def test_writes_rgba_png(self, tmp_path: Path):
        frames = [_make_frame(color=(10, 20, 30, 128))]

        paths = export_frames(frames, tmp_path)

        reloaded = Image.open(paths[0])
        assert reloaded.mode == "RGBA"
        assert reloaded.getpixel((0, 0)) == (10, 20, 30, 128)

    def test_empty_frames_raises_value_error(self, tmp_path: Path):
        with pytest.raises(ValueError):
            export_frames([], tmp_path)

    def test_overwrites_existing_files(self, tmp_path: Path):
        frames = _make_frames(2)
        # First write
        export_frames(frames, tmp_path)
        # Now write a different color in same slot.
        new_frames = [_make_frame(color=(123, 45, 67, 255)), _make_frame()]

        paths = export_frames(new_frames, tmp_path)

        reloaded = Image.open(paths[0])
        assert reloaded.getpixel((0, 0)) == (123, 45, 67, 255)


# --------------------------------------------------------------------------- #
# export_sheet
# --------------------------------------------------------------------------- #


class TestExportSheet:
    def test_three_frames_one_row(self, tmp_path: Path):
        frames = _make_frames(3, width=16, height=16)
        out = tmp_path / "sheet.png"

        path = export_sheet(frames, columns=3, output=out)

        assert path == out
        sheet = Image.open(path)
        assert sheet.size == (48, 16)
        assert sheet.mode == "RGBA"

    def test_five_frames_two_columns_three_rows(self, tmp_path: Path):
        frames = _make_frames(5, width=10, height=20)
        out = tmp_path / "sheet.png"

        export_sheet(frames, columns=2, output=out)

        sheet = Image.open(out)
        # 2 cols × 3 rows of 10x20 cells
        assert sheet.size == (20, 60)

    def test_empty_cell_is_transparent(self, tmp_path: Path):
        # 5 frames in a 2-col grid leaves cell (1, 2) empty.
        frames = _make_frames(5, width=10, height=10)
        out = tmp_path / "sheet.png"

        export_sheet(frames, columns=2, output=out)

        sheet = Image.open(out)
        # Empty cell at column 1, row 2: pixel (15, 25)
        assert sheet.getpixel((15, 25)) == (0, 0, 0, 0)

    def test_sheet_uses_max_frame_size_per_cell(self, tmp_path: Path):
        frames = [
            _make_frame(width=8, height=8),
            _make_frame(width=20, height=12),
        ]
        out = tmp_path / "sheet.png"

        export_sheet(frames, columns=2, output=out)

        sheet = Image.open(out)
        # cell = max(20, 8) x max(12, 8) = 20x12; 2 cols × 1 row.
        assert sheet.size == (40, 12)

    def test_empty_frames_raises(self, tmp_path: Path):
        with pytest.raises(ValueError):
            export_sheet([], columns=1, output=tmp_path / "sheet.png")

    def test_columns_less_than_one_raises(self, tmp_path: Path):
        with pytest.raises(ValueError):
            export_sheet(_make_frames(2), columns=0, output=tmp_path / "sheet.png")

    def test_creates_parent_directory_if_missing(self, tmp_path: Path):
        out = tmp_path / "nested" / "dir" / "sheet.png"
        export_sheet(_make_frames(2), columns=2, output=out)
        assert out.is_file()


# --------------------------------------------------------------------------- #
# export_gif
# --------------------------------------------------------------------------- #


class TestExportGif:
    def test_n_frames_matches_input(self, tmp_path: Path):
        frames = _make_frames(4)
        out = tmp_path / "anim.gif"

        path = export_gif(frames, out, fps=8)

        assert path == out
        gif = Image.open(path)
        assert gif.n_frames == 4

    def test_fps_translates_to_frame_duration(self, tmp_path: Path):
        frames = _make_frames(3)
        out = tmp_path / "anim.gif"

        export_gif(frames, out, fps=10)

        gif = Image.open(out)
        # 1000ms / 10fps = 100ms per frame.
        assert gif.info["duration"] == 100

    def test_default_fps_used_when_not_passed(self, tmp_path: Path):
        # Default fps=8 -> 1000/8 = 125ms requested. GIF stores in 10ms
        # ticks, so the read-back duration is the nearest tick (120ms).
        frames = _make_frames(2)
        out = tmp_path / "anim.gif"

        export_gif(frames, out)

        gif = Image.open(out)
        assert gif.info["duration"] == 120

    def test_fps_five_round_trips_exactly(self, tmp_path: Path):
        # 200ms is a multiple of the 10ms GIF tick; round-trips cleanly.
        frames = _make_frames(2)
        out = tmp_path / "anim.gif"

        export_gif(frames, out, fps=5)

        gif = Image.open(out)
        assert gif.info["duration"] == 200

    def test_transparency_is_set(self, tmp_path: Path):
        frames = [
            _make_frame(color=(0, 0, 0, 0)),  # fully transparent
            _make_frame(color=(255, 0, 0, 255)),
        ]
        out = tmp_path / "anim.gif"

        export_gif(frames, out, fps=8)

        gif = Image.open(out)
        assert "transparency" in gif.info

    def test_empty_frames_raises(self, tmp_path: Path):
        with pytest.raises(ValueError):
            export_gif([], tmp_path / "anim.gif")

    def test_zero_fps_raises(self, tmp_path: Path):
        with pytest.raises(ValueError):
            export_gif(_make_frames(2), tmp_path / "anim.gif", fps=0)

    def test_negative_fps_raises(self, tmp_path: Path):
        with pytest.raises(ValueError):
            export_gif(_make_frames(2), tmp_path / "anim.gif", fps=-5)

    def test_creates_parent_directory_if_missing(self, tmp_path: Path):
        out = tmp_path / "nested" / "anim.gif"
        export_gif(_make_frames(2), out, fps=8)
        assert out.is_file()

    def test_only_alpha_zero_pixels_become_transparent(self, tmp_path: Path):
        """Semi-transparent pixels should blend onto the bg, not be discarded."""
        # Build a 3x1 frame: alpha=0, alpha=64 (semi), alpha=200 (mostly opaque).
        frame = Image.new("RGBA", (3, 1), (0, 0, 0, 0))
        frame.putpixel((0, 0), (10, 20, 30, 0))
        frame.putpixel((1, 0), (10, 20, 30, 64))
        frame.putpixel((2, 0), (10, 20, 30, 200))
        out = tmp_path / "anim.gif"

        export_gif([frame, frame], out, fps=8)

        gif = Image.open(out)
        gif.seek(0)
        rgba = gif.convert("RGBA")
        # alpha=0 must stay transparent in GIF.
        assert rgba.getpixel((0, 0))[3] == 0
        # alpha=64 was previously dropped; now it must be blended (i.e. opaque).
        assert rgba.getpixel((1, 0))[3] != 0
        assert rgba.getpixel((2, 0))[3] != 0

    def test_custom_bg_color_blends_semi_transparent_edges(self, tmp_path: Path):
        """bg_color parameter changes how semi-transparent pixels render."""
        from sprite_kit.export import export_gif as eg

        frame = Image.new("RGBA", (1, 1), (255, 255, 255, 64))  # mostly transparent white
        white_out = tmp_path / "white.gif"
        black_out = tmp_path / "black.gif"

        eg([frame, frame], white_out, fps=8, bg_color=(255, 255, 255))
        eg([frame, frame], black_out, fps=8, bg_color=(0, 0, 0))

        white_pixel = Image.open(white_out).convert("RGBA").getpixel((0, 0))
        black_pixel = Image.open(black_out).convert("RGBA").getpixel((0, 0))
        # On white bg the pixel reads near-white; on black bg it reads dark.
        assert sum(white_pixel[:3]) > sum(black_pixel[:3])


# --------------------------------------------------------------------------- #
# export_atlas
# --------------------------------------------------------------------------- #


class TestExportAtlas:
    def test_writes_valid_json(self, tmp_path: Path):
        frames = _make_frames(2, width=64, height=64)
        out = tmp_path / "idle.json"

        path = export_atlas(frames, name="idle", output=out)

        assert path == out
        data = json.loads(out.read_text())
        assert "frames" in data
        assert "meta" in data

    def test_frame_keys_zero_padded(self, tmp_path: Path):
        frames = _make_frames(2, width=64, height=64)
        out = tmp_path / "idle.json"

        export_atlas(frames, name="idle", output=out)

        data = json.loads(out.read_text())
        assert "idle_001" in data["frames"]
        assert "idle_002" in data["frames"]

    def test_frame_coords_match_horizontal_layout(self, tmp_path: Path):
        frames = _make_frames(2, width=64, height=64)
        out = tmp_path / "idle.json"

        export_atlas(frames, name="idle", output=out)

        data = json.loads(out.read_text())
        assert data["frames"]["idle_001"] == {"x": 0, "y": 0, "w": 64, "h": 64}
        assert data["frames"]["idle_002"] == {"x": 64, "y": 0, "w": 64, "h": 64}

    def test_meta_size_total_width_max_height(self, tmp_path: Path):
        frames = [
            _make_frame(width=64, height=64),
            _make_frame(width=32, height=80),
        ]
        out = tmp_path / "x.json"

        export_atlas(frames, name="x", output=out)

        data = json.loads(out.read_text())
        assert data["meta"]["size"] == {"w": 64 + 32, "h": 80}

    def test_meta_image_default_filename(self, tmp_path: Path):
        out = tmp_path / "idle.json"
        export_atlas(_make_frames(2), name="idle", output=out)

        data = json.loads(out.read_text())
        assert data["meta"]["image"] == "idle_sheet.png"

    def test_meta_image_overridable(self, tmp_path: Path):
        out = tmp_path / "idle.json"

        export_atlas(
            _make_frames(2),
            name="idle",
            output=out,
            image_filename="custom.png",
        )

        data = json.loads(out.read_text())
        assert data["meta"]["image"] == "custom.png"

    def test_meta_scale_and_format(self, tmp_path: Path):
        out = tmp_path / "x.json"
        export_atlas(_make_frames(1), name="x", output=out)

        data = json.loads(out.read_text())
        assert data["meta"]["scale"] == 1
        assert data["meta"]["format"] == "RGBA8888"

    def test_empty_frames_raises(self, tmp_path: Path):
        with pytest.raises(ValueError):
            export_atlas([], name="x", output=tmp_path / "x.json")

    def test_creates_parent_directory_if_missing(self, tmp_path: Path):
        out = tmp_path / "nested" / "x.json"
        export_atlas(_make_frames(1), name="x", output=out)
        assert out.is_file()


# --------------------------------------------------------------------------- #
# export_metadata
# --------------------------------------------------------------------------- #


class TestExportMetadata:
    def test_round_trip(self, tmp_path: Path):
        meta = {
            "prompt": "a cute knight idle",
            "model": "gpt-image-2",
            "quality": "medium",
            "steps": ["generate", "chroma_key", "split", "align"],
            "frame_count": 4,
        }
        out = tmp_path / "meta.json"

        path = export_metadata(meta, out)

        assert path == out
        assert json.loads(out.read_text()) == meta

    def test_empty_dict_is_valid(self, tmp_path: Path):
        out = tmp_path / "meta.json"

        export_metadata({}, out)

        assert json.loads(out.read_text()) == {}

    def test_non_serializable_raises_type_error(self, tmp_path: Path):
        meta = {"callback": lambda x: x}

        with pytest.raises(TypeError):
            export_metadata(meta, tmp_path / "meta.json")

    def test_creates_parent_directory_if_missing(self, tmp_path: Path):
        out = tmp_path / "nested" / "dir" / "meta.json"
        export_metadata({"a": 1}, out)
        assert out.is_file()
