"""One-shot generator for tests/fixtures/sample_sheet.png.

Run from repo root:

    python tests/fixtures/_make_sample_sheet.py

Produces a 1x3 sprite sheet on a #FF00FF background. Each cell is 100x100;
content shapes vary in height so ``align_frames`` can prove that
bottom-center anchoring lifts feet to the same y across frames (AC-3).
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

CELL = 100
ROWS = 1
COLS = 3
CHROMA = (255, 0, 255)

# Each entry: (fill_color, content_height, bottom_padding_in_cell)
# Content widths are intentionally identical (40px) so the only varying
# dimension is height — this isolates the vertical-alignment behavior.
SHAPES: tuple[tuple[tuple[int, int, int], int, int], ...] = (
    ((0, 0, 0), 50, 10),  # short black rectangle
    ((255, 255, 255), 80, 5),  # tall white rectangle
    ((0, 0, 255), 65, 20),  # medium blue rectangle
)

CONTENT_WIDTH = 40


def build() -> Image.Image:
    sheet = Image.new("RGB", (CELL * COLS, CELL * ROWS), CHROMA)
    draw = ImageDraw.Draw(sheet)
    for col, (color, height, bottom_pad) in enumerate(SHAPES):
        cell_x0 = col * CELL
        x0 = cell_x0 + (CELL - CONTENT_WIDTH) // 2
        x1 = x0 + CONTENT_WIDTH - 1
        y1 = CELL - 1 - bottom_pad
        y0 = y1 - height + 1
        draw.rectangle((x0, y0, x1, y1), fill=color)
    return sheet


def main() -> None:
    out = Path(__file__).with_name("sample_sheet.png")
    build().save(out, format="PNG")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
