"""Tests for sprite_kit.process — covers AC-2 (chroma key) and AC-3 (alignment)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from sprite_kit.process import (
    align_frames,
    chroma_key_remove,
    despill,
    qc_check,
    resize,
    split_frames,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sample_sheet.png"
CHROMA_RGB = (255, 0, 255)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _make_solid(size: tuple[int, int], color: tuple[int, int, int]) -> Image.Image:
    return Image.new("RGB", size, color)


def _make_rgba_blank(size: tuple[int, int]) -> Image.Image:
    return Image.new("RGBA", size, (0, 0, 0, 0))


def _make_rgba_with_rect(
    size: tuple[int, int],
    rect: tuple[int, int, int, int],
    color: tuple[int, int, int, int] = (10, 20, 30, 255),
) -> Image.Image:
    img = _make_rgba_blank(size)
    draw = ImageDraw.Draw(img)
    draw.rectangle(rect, fill=color)
    return img


def _content_bottom_y(img: Image.Image) -> int:
    """Return y-coordinate of bottom-most non-transparent pixel."""
    bbox = img.getbbox()
    assert bbox is not None, "frame has no content"
    return bbox[3] - 1  # bbox is exclusive on bottom edge


# ---------------------------------------------------------------------------
# chroma_key_remove
# ---------------------------------------------------------------------------


class TestChromaKeyRemove:
    def test_pure_chroma_pixels_become_transparent(self):
        img = _make_solid((10, 10), CHROMA_RGB)

        out = chroma_key_remove(img)

        assert out.mode == "RGBA"
        alpha = out.split()[3]
        assert alpha.getextrema() == (0, 0)

    def test_content_pixels_stay_opaque(self):
        img = Image.new("RGB", (4, 4), CHROMA_RGB)
        ImageDraw.Draw(img).rectangle((1, 1, 2, 2), fill=(0, 0, 0))

        out = chroma_key_remove(img)

        assert out.getpixel((1, 1))[3] == 255
        assert out.getpixel((2, 2))[3] == 255
        assert out.getpixel((0, 0))[3] == 0

    def test_higher_fuzz_removes_near_chroma(self):
        # near-magenta pixel: (250, 5, 250) — within ~7 RGB units of #FF00FF
        img = Image.new("RGB", (2, 1), (250, 5, 250))

        strict = chroma_key_remove(img, fuzz=0)
        loose = chroma_key_remove(img, fuzz=15)

        assert strict.getpixel((0, 0))[3] == 255  # not pure chroma
        assert loose.getpixel((0, 0))[3] == 0  # fuzz catches it

    def test_accepts_non_rgba_input(self):
        img = _make_solid((3, 3), CHROMA_RGB).convert("L")  # grayscale path

        out = chroma_key_remove(img)

        assert out.mode == "RGBA"
        assert out.size == (3, 3)

    def test_custom_chroma_color(self):
        img = Image.new("RGB", (2, 1), (0, 255, 0))

        out = chroma_key_remove(img, chroma="#00FF00", fuzz=0)

        assert out.getpixel((0, 0))[3] == 0

    def test_fixture_sheet_background_removed(self):
        sheet = Image.open(FIXTURE_PATH)

        out = chroma_key_remove(sheet)

        # corner pixels of every cell are background → must be transparent
        assert out.getpixel((0, 0))[3] == 0
        assert out.getpixel((150, 0))[3] == 0
        assert out.getpixel((299, 99))[3] == 0

    def test_preserves_existing_transparent_pixels(self):
        """spec §8: re-running chroma key on an RGBA must not 'unhide' alpha=0 pixels."""
        # A pre-transparent pixel whose RGB is NOT chroma (black) must stay transparent.
        img = Image.new("RGBA", (2, 1), (0, 0, 0, 0))

        out = chroma_key_remove(img)

        assert out.getpixel((0, 0))[3] == 0
        assert out.getpixel((1, 0))[3] == 0

    def test_preserves_partial_alpha_on_non_chroma(self):
        """Non-chroma pixels keep their original alpha (monotonic non-increase)."""
        img = Image.new("RGBA", (1, 1), (0, 100, 200, 128))  # semi-transparent blue

        out = chroma_key_remove(img)

        # Alpha must not be lifted above the input value.
        assert out.getpixel((0, 0))[3] <= 128

    def test_idempotent_on_rgba_input(self):
        """spec §8: applying chroma key twice on an already-keyed image is a no-op."""
        img = Image.new("RGBA", (4, 4), (255, 0, 255, 255))
        ImageDraw.Draw(img).rectangle((1, 1, 2, 2), fill=(0, 0, 0, 255))

        once = chroma_key_remove(img)
        twice = chroma_key_remove(once)

        import numpy as np

        assert np.array_equal(np.array(once), np.array(twice))


# ---------------------------------------------------------------------------
# despill
# ---------------------------------------------------------------------------


class TestDespill:
    def test_pure_white_unchanged(self):
        img = Image.new("RGBA", (1, 1), (255, 255, 255, 255))

        out = despill(img)

        assert out.getpixel((0, 0)) == (255, 255, 255, 255)

    def test_pure_black_unchanged(self):
        img = Image.new("RGBA", (1, 1), (0, 0, 0, 255))

        out = despill(img)

        assert out.getpixel((0, 0)) == (0, 0, 0, 255)

    def test_magenta_tint_green_lifted(self):
        # R=200, G=50, B=200 — clearly magenta-cast; G should rise toward min(R,B)
        img = Image.new("RGBA", (1, 1), (200, 50, 200, 255))

        out = despill(img)

        r, g, b, a = out.getpixel((0, 0))
        assert g > 50, "green channel should be lifted to suppress magenta"
        assert r == 200 and b == 200 and a == 255

    def test_transparent_pixel_not_modified(self):
        img = Image.new("RGBA", (1, 1), (255, 0, 255, 0))

        out = despill(img)

        assert out.getpixel((0, 0))[3] == 0

    def test_returns_rgba(self):
        img = Image.new("RGBA", (2, 2), (200, 0, 200, 255))

        out = despill(img)

        assert out.mode == "RGBA"
        assert out.size == (2, 2)


# ---------------------------------------------------------------------------
# split_frames
# ---------------------------------------------------------------------------


class TestSplitFrames:
    def test_1x3_split_returns_three_equal_cells(self):
        img = Image.new("RGBA", (300, 100), (0, 0, 0, 255))

        frames = split_frames(img, rows=1, cols=3)

        assert len(frames) == 3
        for f in frames:
            assert f.size == (100, 100)

    def test_2x2_split_row_major_order(self):
        img = Image.new("RGBA", (20, 20), (0, 0, 0, 0))
        # paint each cell a unique color so we can verify ordering
        colors = [
            (255, 0, 0, 255),  # top-left
            (0, 255, 0, 255),  # top-right
            (0, 0, 255, 255),  # bottom-left
            (255, 255, 0, 255),  # bottom-right
        ]
        draw = ImageDraw.Draw(img)
        draw.rectangle((0, 0, 9, 9), fill=colors[0])
        draw.rectangle((10, 0, 19, 9), fill=colors[1])
        draw.rectangle((0, 10, 9, 19), fill=colors[2])
        draw.rectangle((10, 10, 19, 19), fill=colors[3])

        frames = split_frames(img, rows=2, cols=2)

        assert len(frames) == 4
        for frame, expected in zip(frames, colors, strict=True):
            assert frame.getpixel((5, 5)) == expected

    def test_non_divisible_dimensions_raise(self):
        img = Image.new("RGBA", (10, 10))

        with pytest.raises(ValueError):
            split_frames(img, rows=1, cols=3)  # 10 % 3 != 0

        with pytest.raises(ValueError):
            split_frames(img, rows=3, cols=1)

    def test_zero_or_negative_grid_raises(self):
        img = Image.new("RGBA", (10, 10))

        with pytest.raises(ValueError):
            split_frames(img, rows=0, cols=1)
        with pytest.raises(ValueError):
            split_frames(img, rows=1, cols=0)
        with pytest.raises(ValueError):
            split_frames(img, rows=-1, cols=1)


# ---------------------------------------------------------------------------
# align_frames — AC-3
# ---------------------------------------------------------------------------


class TestAlignFrames:
    def _three_frames_varied_heights(self) -> list[Image.Image]:
        # canvas 50x50; varying content heights with different bottom paddings
        frames: list[Image.Image] = []
        specs = [
            (20, 5),  # height 20, bottom padding 5  → bottom y = 44
            (35, 10),  # height 35, bottom padding 10 → bottom y = 39
            (28, 2),  # height 28, bottom padding 2  → bottom y = 47
        ]
        for height, bottom_pad in specs:
            img = _make_rgba_blank((50, 50))
            y1 = 50 - 1 - bottom_pad
            y0 = y1 - height + 1
            ImageDraw.Draw(img).rectangle((10, y0, 30, y1), fill=(255, 255, 255, 255))
            frames.append(img)
        return frames

    def test_canvas_size_uniform(self):
        frames = self._three_frames_varied_heights()

        aligned = align_frames(frames, anchor="bottom-center")

        sizes = {f.size for f in aligned}
        assert len(sizes) == 1

    def test_bottom_center_aligns_feet_within_1px(self):
        """AC-3: bottom-most non-transparent y differs by at most 1px."""
        frames = self._three_frames_varied_heights()

        aligned = align_frames(frames, anchor="bottom-center")

        bottoms = [_content_bottom_y(f) for f in aligned]
        assert max(bottoms) - min(bottoms) <= 1, f"bottoms not aligned: {bottoms}"

    def test_bottom_center_centers_x(self):
        frames = self._three_frames_varied_heights()

        aligned = align_frames(frames, anchor="bottom-center")

        for f in aligned:
            bbox = f.getbbox()
            content_left, _, content_right, _ = bbox
            content_center = (content_left + content_right) / 2
            canvas_center = f.size[0] / 2
            assert abs(content_center - canvas_center) <= 1

    def test_top_center_aligns_tops(self):
        frames = self._three_frames_varied_heights()

        aligned = align_frames(frames, anchor="top-center")

        tops = [f.getbbox()[1] for f in aligned]
        assert max(tops) - min(tops) <= 1

    def test_center_anchor_centers_content(self):
        frames = self._three_frames_varied_heights()

        aligned = align_frames(frames, anchor="center")

        for f in aligned:
            bbox = f.getbbox()
            cx = (bbox[0] + bbox[2]) / 2
            cy = (bbox[1] + bbox[3]) / 2
            assert abs(cx - f.size[0] / 2) <= 1
            assert abs(cy - f.size[1] / 2) <= 1

    def test_blank_frame_does_not_crash(self):
        frames = [
            _make_rgba_blank((20, 20)),
            _make_rgba_with_rect((20, 20), (5, 5, 14, 14)),
        ]

        aligned = align_frames(frames, anchor="bottom-center")

        assert len(aligned) == 2
        assert aligned[0].size == aligned[1].size

    def test_pipeline_with_fixture_aligns_feet(self):
        """End-to-end: chroma-key + split + align on the real fixture sheet."""
        sheet = Image.open(FIXTURE_PATH)
        keyed = chroma_key_remove(sheet)
        cells = split_frames(keyed, rows=1, cols=3)

        aligned = align_frames(cells, anchor="bottom-center")

        bottoms = [_content_bottom_y(f) for f in aligned]
        assert max(bottoms) - min(bottoms) <= 1, f"AC-3 violated: feet bottoms differ: {bottoms}"


# ---------------------------------------------------------------------------
# resize
# ---------------------------------------------------------------------------


class TestResize:
    def test_scale_half_halves_dimensions(self):
        img = Image.new("RGBA", (100, 80), (1, 2, 3, 255))

        out = resize(img, scale=0.5)

        assert out.size == (50, 40)

    def test_size_target_exact(self):
        img = Image.new("RGBA", (100, 80), (1, 2, 3, 255))

        out = resize(img, size=(64, 64))

        assert out.size == (64, 64)

    def test_both_scale_and_size_raises(self):
        img = Image.new("RGBA", (10, 10))

        with pytest.raises(ValueError):
            resize(img, scale=0.5, size=(5, 5))

    def test_neither_scale_nor_size_raises(self):
        img = Image.new("RGBA", (10, 10))

        with pytest.raises(ValueError):
            resize(img)

    def test_method_nearest_runs(self):
        img = Image.new("RGBA", (10, 10), (1, 2, 3, 255))

        out = resize(img, scale=2.0, method="nearest")

        assert out.size == (20, 20)

    def test_method_lanczos_runs(self):
        img = Image.new("RGBA", (10, 10), (1, 2, 3, 255))

        out = resize(img, scale=2.0, method="lanczos")

        assert out.size == (20, 20)

    def test_preserves_mode(self):
        img = Image.new("RGB", (10, 10), (1, 2, 3))

        out = resize(img, scale=0.5)

        assert out.mode == "RGB"


# ---------------------------------------------------------------------------
# qc_check
# ---------------------------------------------------------------------------


class TestQcCheck:
    def test_all_good_frames_no_issues(self):
        frames = [
            _make_rgba_with_rect((20, 20), (5, 5, 10, 10)),
            _make_rgba_with_rect((20, 20), (3, 3, 12, 12)),
        ]

        report = qc_check(frames)

        assert report["blank_frames"] == []
        assert report["size_consistent"] is True
        assert report["all_rgba"] is True
        assert report["frame_count"] == 2
        assert report["issues"] == []

    def test_blank_frame_detected(self):
        frames = [
            _make_rgba_with_rect((20, 20), (5, 5, 10, 10)),
            _make_rgba_blank((20, 20)),
            _make_rgba_with_rect((20, 20), (3, 3, 12, 12)),
        ]

        report = qc_check(frames)

        assert report["blank_frames"] == [1]
        assert any("blank" in issue.lower() for issue in report["issues"])

    def test_size_inconsistency_flagged(self):
        frames = [
            _make_rgba_with_rect((20, 20), (5, 5, 10, 10)),
            _make_rgba_with_rect((30, 30), (5, 5, 10, 10)),
        ]

        report = qc_check(frames)

        assert report["size_consistent"] is False
        assert any("size" in issue.lower() for issue in report["issues"])

    def test_non_rgba_frame_flagged(self):
        frames = [
            _make_rgba_with_rect((20, 20), (5, 5, 10, 10)),
            Image.new("RGB", (20, 20), (1, 2, 3)),
        ]

        report = qc_check(frames)

        assert report["all_rgba"] is False
        assert any(
            "rgba" in issue.lower() or "alpha" in issue.lower() for issue in report["issues"]
        )

    def test_empty_frame_list(self):
        report = qc_check([])

        assert report["frame_count"] == 0
        assert report["blank_frames"] == []
        # vacuously consistent
        assert report["size_consistent"] is True
        assert report["all_rgba"] is True
