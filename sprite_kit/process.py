"""Post-processing pipeline: chroma key, despill, split, align, resize, QC.

All functions are pure: they accept and return :class:`PIL.Image.Image`
instances without mutating the input.
"""

from __future__ import annotations

from typing import Literal

import numpy as np
from PIL import Image

Anchor = Literal["bottom-center", "top-center", "center"]
ResizeMethod = Literal["nearest", "lanczos"]

# sqrt(3 * 255**2) — max possible RGB Euclidean distance
_MAX_RGB_DISTANCE = float(np.sqrt(3.0) * 255.0)

_RESAMPLERS: dict[str, int] = {
    "nearest": Image.Resampling.NEAREST,
    "lanczos": Image.Resampling.LANCZOS,
}


def chroma_key_remove(
    img: Image.Image,
    chroma: str = "#FF00FF",
    fuzz: int = 15,
) -> Image.Image:
    """Remove chroma-key background, returning an RGBA image.

    Pixels whose RGB Euclidean distance to ``chroma`` is within
    ``fuzz`` percent of the maximum possible distance are made fully
    transparent; all other pixels are made fully opaque.

    Args:
        img: Input image (any mode; converted to RGBA internally).
        chroma: Hex color string of the background, e.g. ``"#FF00FF"``.
        fuzz: Tolerance percentage 0-100.

    Returns:
        RGBA image with chroma pixels having ``alpha=0``.
    """
    chroma_rgb = _parse_hex_color(chroma)
    threshold = (max(0, min(100, fuzz)) / 100.0) * _MAX_RGB_DISTANCE

    rgba = img.convert("RGBA")
    arr = np.array(rgba, dtype=np.uint8)
    diff = arr[..., :3].astype(np.int32) - np.array(chroma_rgb, dtype=np.int32)
    distance_sq = (diff * diff).sum(axis=-1)

    mask_bg = distance_sq <= (threshold * threshold)
    # Preserve existing alpha so re-applying chroma key on an already-keyed
    # image is a no-op (spec §8). np.minimum guarantees monotonic non-increase:
    # chroma pixels collapse to 0; non-chroma pixels retain their input alpha.
    existing_alpha = arr[..., 3]
    arr[..., 3] = np.minimum(existing_alpha, np.where(mask_bg, 0, 255)).astype(np.uint8)
    return Image.fromarray(arr, mode="RGBA")


def despill(img: Image.Image) -> Image.Image:
    """Remove magenta spill from edge pixels.

    For visible pixels (``alpha > 0``) where the red and blue channels
    both exceed green (a magenta cast), pull green up toward
    ``min(R, B)`` to neutralize the tint. Fully transparent pixels are
    left untouched.

    Args:
        img: RGBA image (typically the output of :func:`chroma_key_remove`).

    Returns:
        RGBA image with spill suppressed.
    """
    rgba = img.convert("RGBA")
    arr = np.array(rgba, dtype=np.uint8)

    r = arr[..., 0]
    g = arr[..., 1]
    b = arr[..., 2]
    a = arr[..., 3]

    rb_min = np.minimum(r, b)
    spill_mask = (a > 0) & (r > g) & (b > g)
    new_g = np.where(spill_mask, np.maximum(g, rb_min), g)
    arr[..., 1] = new_g
    return Image.fromarray(arr, mode="RGBA")


def split_frames(img: Image.Image, rows: int, cols: int) -> list[Image.Image]:
    """Split an image into ``rows × cols`` equal cells, ordered row-major.

    Args:
        img: Source image (will be converted to RGBA).
        rows: Number of grid rows (>= 1).
        cols: Number of grid columns (>= 1).

    Raises:
        ValueError: If ``rows`` or ``cols`` is < 1, or the image cannot
            be divided evenly into the requested grid.
    """
    if rows < 1 or cols < 1:
        raise ValueError(f"rows and cols must be >= 1, got rows={rows}, cols={cols}")

    width, height = img.size
    if width % cols != 0 or height % rows != 0:
        raise ValueError(
            f"Image size {width}x{height} cannot be evenly split into {rows}x{cols} cells."
        )

    rgba = img.convert("RGBA")
    cell_w = width // cols
    cell_h = height // rows

    frames: list[Image.Image] = []
    for r in range(rows):
        for c in range(cols):
            box = (c * cell_w, r * cell_h, (c + 1) * cell_w, (r + 1) * cell_h)
            frames.append(rgba.crop(box))
    return frames


def align_frames(
    frames: list[Image.Image],
    anchor: Anchor = "bottom-center",
) -> list[Image.Image]:
    """Align frames on a uniform canvas using their content bounding boxes.

    The output canvas is sized to fit the largest content bbox across
    all frames; each frame is then placed on its own copy of that
    canvas at the position dictated by ``anchor``. Empty frames produce
    a blank canvas of the same size.

    Args:
        frames: List of RGBA images.
        anchor: Placement rule. ``"bottom-center"`` keeps content
            bottoms aligned (critical for AC-3); other modes align by
            top or center.

    Returns:
        List of RGBA images, all the same size, aligned per ``anchor``.
    """
    if not frames:
        return []

    rgba_frames = [f.convert("RGBA") for f in frames]
    bboxes = [f.getbbox() for f in rgba_frames]

    max_w = 0
    max_h = 0
    for bbox in bboxes:
        if bbox is None:
            continue
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        max_w = max(max_w, w)
        max_h = max(max_h, h)

    # Edge case: no frame had any content — preserve a 1×1 transparent canvas
    canvas_w = max(max_w, 1)
    canvas_h = max(max_h, 1)

    aligned: list[Image.Image] = []
    for frame, bbox in zip(rgba_frames, bboxes, strict=True):
        canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        if bbox is None:
            aligned.append(canvas)
            continue
        cropped = frame.crop(bbox)
        x, y = _anchor_position(cropped.size, (canvas_w, canvas_h), anchor)
        canvas.paste(cropped, (x, y), cropped)
        aligned.append(canvas)
    return aligned


def resize(
    img: Image.Image,
    scale: float | None = None,
    size: tuple[int, int] | None = None,
    method: ResizeMethod = "nearest",
) -> Image.Image:
    """Resize an image by scale factor or to an explicit target size.

    Exactly one of ``scale`` or ``size`` must be provided.

    Args:
        img: Input image (mode preserved).
        scale: Multiplicative scale factor (e.g., ``0.5`` for half).
        size: Target ``(width, height)`` in pixels.
        method: ``"nearest"`` for pixel-art sharpness, ``"lanczos"`` for
            smooth-art texture.

    Raises:
        ValueError: If both or neither of ``scale``/``size`` are given,
            or ``method`` is unknown.
    """
    if (scale is None) == (size is None):
        raise ValueError("Provide exactly one of `scale` or `size`.")

    resampler = _RESAMPLERS.get(method)
    if resampler is None:
        raise ValueError(f"Unknown resize method: {method!r}")

    if size is not None:
        target = size
    else:
        w, h = img.size
        target = (max(1, round(w * scale)), max(1, round(h * scale)))

    return img.resize(target, resample=resampler)


def qc_check(frames: list[Image.Image]) -> dict:
    """Quality-check a list of frames.

    Returns:
        Dict containing:
          - ``blank_frames``: indices of frames with no opaque pixels.
          - ``size_consistent``: ``True`` when every frame shares the
            same ``(width, height)``.
          - ``all_rgba``: ``True`` when every frame is in mode ``RGBA``.
          - ``frame_count``: number of frames inspected.
          - ``issues``: human-readable warning strings (empty when OK).
    """
    blank: list[int] = []
    sizes: set[tuple[int, int]] = set()
    all_rgba = True

    for idx, frame in enumerate(frames):
        sizes.add(frame.size)
        if frame.mode != "RGBA":
            all_rgba = False
            continue
        # bbox is None when every alpha is zero
        if frame.getbbox() is None:
            blank.append(idx)

    size_consistent = len(sizes) <= 1
    issues: list[str] = []
    if blank:
        issues.append(f"Blank frames detected at indices: {blank}")
    if not size_consistent:
        issues.append(f"Frame sizes are inconsistent: {sorted(sizes)}")
    if not all_rgba:
        issues.append("One or more frames lack an RGBA alpha channel.")

    return {
        "blank_frames": blank,
        "size_consistent": size_consistent,
        "all_rgba": all_rgba,
        "frame_count": len(frames),
        "issues": issues,
    }


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _parse_hex_color(value: str) -> tuple[int, int, int]:
    s = value.strip().lstrip("#")
    if len(s) != 6:
        raise ValueError(f"Expected 6-digit hex color, got {value!r}")
    try:
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
    except ValueError as exc:
        raise ValueError(f"Invalid hex color: {value!r}") from exc


def _anchor_position(
    content_size: tuple[int, int],
    canvas_size: tuple[int, int],
    anchor: Anchor,
) -> tuple[int, int]:
    cw, ch = content_size
    canvas_w, canvas_h = canvas_size
    x = (canvas_w - cw) // 2

    if anchor == "bottom-center":
        return x, canvas_h - ch
    if anchor == "top-center":
        return x, 0
    if anchor == "center":
        return x, (canvas_h - ch) // 2
    raise ValueError(f"Unknown anchor: {anchor!r}")
