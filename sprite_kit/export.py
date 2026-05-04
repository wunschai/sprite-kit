"""Output writers for individual frames, sprite sheets, GIFs, atlas JSON, and metadata.

Covers AC-4 (export format correctness) of the MVP spec §6.3.

All writers are pure I/O functions: they accept in-memory data and return
the :class:`pathlib.Path` of the file written. Parent directories are
created if missing. For MVP, files are overwritten on conflict; the
ADR-3 numeric-suffix-on-conflict policy is implemented in ``utils.py``
during Milestone 3 and will wrap these functions later.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image

_ATLAS_SCALE = 1
_ATLAS_FORMAT = "RGBA8888"


def export_frames(
    frames: list[Image.Image],
    output_dir: str | Path,
    name_prefix: str = "frame",
) -> list[Path]:
    """Save individual frames as PNG with zero-padded numeric suffix.

    Filenames follow ``{name_prefix}_001.png``, ``{name_prefix}_002.png`` …
    The padding width is ``max(3, len(str(len(frames))))`` so 3-digit padding
    is the floor and longer sequences expand automatically.

    Args:
        frames: List of RGBA images.
        output_dir: Directory to write into. Created if missing.
        name_prefix: Prefix for filenames.

    Returns:
        List of paths in the same order as ``frames``.

    Raises:
        ValueError: If ``frames`` is empty.
    """
    if not frames:
        raise ValueError("frames must not be empty.")

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    width = max(3, len(str(len(frames))))
    paths: list[Path] = []
    for index, frame in enumerate(frames, start=1):
        filename = f"{name_prefix}_{index:0{width}d}.png"
        path = out_dir / filename
        frame.save(path, format="PNG")
        paths.append(path)
    return paths


def export_sheet(
    frames: list[Image.Image],
    columns: int,
    output: str | Path,
) -> Path:
    """Compose frames into a single sprite sheet PNG with a transparent background.

    Cell size = ``(max width across frames, max height across frames)``.
    Layout = ``ceil(len(frames) / columns)`` rows × ``columns`` columns.
    Empty trailing cells remain fully transparent.

    Args:
        frames: List of RGBA images (any sizes; sheet uses max).
        columns: Number of columns in the sheet (>= 1).
        output: Output PNG path.

    Returns:
        Path to written file.

    Raises:
        ValueError: If ``frames`` is empty or ``columns < 1``.
    """
    if not frames:
        raise ValueError("frames must not be empty.")
    if columns < 1:
        raise ValueError(f"columns must be >= 1, got {columns}.")

    cell_w = max(f.width for f in frames)
    cell_h = max(f.height for f in frames)
    rows = math.ceil(len(frames) / columns)

    sheet = Image.new("RGBA", (cell_w * columns, cell_h * rows), (0, 0, 0, 0))
    for index, frame in enumerate(frames):
        row, col = divmod(index, columns)
        sheet.paste(frame, (col * cell_w, row * cell_h), frame)

    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path, format="PNG")
    return out_path


def export_gif(
    frames: list[Image.Image],
    output: str | Path,
    fps: int = 8,
    bg_color: tuple[int, int, int] = (255, 255, 255),
) -> Path:
    """Save frames as animated GIF with a transparent background.

    GIF transparency is single-color (binary alpha). Pillow handles the
    palette via ``disposal=2`` and a reserved transparent palette index.

    Args:
        frames: List of RGBA images.
        output: Output GIF path.
        fps: Frames per second; frame duration ms = ``round(1000 / fps)``.
        bg_color: RGB color used to blend semi-transparent edges before
            quantization (binary alpha softens jaggies). Only fully
            transparent (alpha=0) pixels remain transparent in the GIF.

    Returns:
        Path to written file.

    Raises:
        ValueError: If ``frames`` is empty or ``fps <= 0``.
    """
    if not frames:
        raise ValueError("frames must not be empty.")
    if fps <= 0:
        raise ValueError(f"fps must be > 0, got {fps}.")

    duration_ms = round(1000 / fps)
    quantized = [_quantize_for_gif(f, bg_color=bg_color) for f in frames]

    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    quantized[0].save(
        out_path,
        format="GIF",
        save_all=True,
        append_images=quantized[1:],
        duration=duration_ms,
        loop=0,
        disposal=2,
        transparency=0,
    )
    return out_path


def export_atlas(
    frames: list[Image.Image],
    name: str,
    output: str | Path,
    image_filename: str | None = None,
) -> Path:
    """Write atlas JSON describing a horizontally-arranged sprite sheet.

    Frames are assumed to lay out in a single row in the order given.
    Callers wanting grid layouts should atlas-export per row.

    Args:
        frames: Frames in the order they appear horizontally on the sheet.
        name: Base name for atlas keys, e.g. ``"idle"`` -> ``"idle_001"``…
        output: Output JSON path.
        image_filename: Image filename to record in ``meta.image``. If None,
            defaults to ``f"{name}_sheet.png"``.

    Returns:
        Path to written file.

    Raises:
        ValueError: If ``frames`` is empty.
    """
    if not frames:
        raise ValueError("frames must not be empty.")

    width = max(3, len(str(len(frames))))
    frame_entries: dict[str, dict[str, int]] = {}
    cursor_x = 0
    for index, frame in enumerate(frames, start=1):
        key = f"{name}_{index:0{width}d}"
        frame_entries[key] = {
            "x": cursor_x,
            "y": 0,
            "w": frame.width,
            "h": frame.height,
        }
        cursor_x += frame.width

    total_w = sum(f.width for f in frames)
    total_h = max(f.height for f in frames)

    atlas = {
        "frames": frame_entries,
        "meta": {
            "image": image_filename if image_filename is not None else f"{name}_sheet.png",
            "size": {"w": total_w, "h": total_h},
            "scale": _ATLAS_SCALE,
            "format": _ATLAS_FORMAT,
        },
    }

    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(atlas, indent=2))
    return out_path


def export_metadata(
    meta: dict,
    output: str | Path,
) -> Path:
    """Write pipeline metadata JSON (prompt, model, quality, steps, …).

    Args:
        meta: Arbitrary JSON-serializable dict.
        output: Output JSON path.

    Returns:
        Path to written file.

    Raises:
        TypeError: If ``meta`` is not JSON-serializable.
    """
    payload = json.dumps(meta, indent=2)

    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(payload)
    return out_path


def _quantize_for_gif(
    frame: Image.Image,
    bg_color: tuple[int, int, int] = (255, 255, 255),
) -> Image.Image:
    """Convert an RGBA frame to a palette image with index 0 reserved as transparent.

    Semi-transparent pixels are first blended onto ``bg_color`` so GIF's
    binary alpha doesn't produce jagged edges. Only fully transparent
    (alpha=0) pixels are mapped to the reserved transparent palette
    index 0; the remaining 255 slots receive quantized visible colors.
    """
    rgba = frame.convert("RGBA")
    alpha = rgba.split()[3]

    # Composite onto solid bg so semi-transparent edges blend smoothly before
    # the GIF binary alpha kicks in.
    blended = Image.new("RGB", rgba.size, bg_color)
    blended.paste(rgba, mask=alpha)
    palette_img = blended.quantize(colors=255, method=Image.Quantize.MEDIANCUT)

    # Shift every existing palette index up by 1 so index 0 stays free for
    # transparency. ``point`` keeps mode "P".
    shifted = palette_img.point(lambda v: v + 1)

    # Stamp transparent index 0 only over fully-transparent pixels (alpha=0).
    transparent_mask = alpha.point(lambda v: 255 if v == 0 else 0)
    transparent_layer = Image.new("P", shifted.size, 0)
    transparent_layer.putpalette(shifted.getpalette() or [])
    shifted.paste(transparent_layer, mask=transparent_mask)

    # Carry over the 255-entry palette shifted by one slot; index 0 is the
    # reserved transparent color.
    source_palette = palette_img.getpalette() or []
    new_palette = [0, 0, 0] + source_palette[: 255 * 3]
    new_palette += [0] * (768 - len(new_palette))
    shifted.putpalette(new_palette[:768])
    return shifted
