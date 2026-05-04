"""Sprite Kit CLI: argparse-based dispatch for generate / process / export / pipeline.

Pipeline orchestration lives here as ``run_pipeline``: it sequences
generate -> chroma key + despill -> split -> align -> qc -> export.
ADR-3 (numeric-suffix on conflict) is enforced at every write site
unless ``--force`` is supplied.
"""

from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path
from typing import Any

import yaml
from PIL import Image

from .config import ConfigError, load_config, require_api_key
from .export import (
    export_atlas,
    export_frames,
    export_gif,
    export_metadata,
    export_sheet,
)
from .generate import GenerateError, TemplateError, generate_sprite, load_template
from .process import align_frames, chroma_key_remove, despill, qc_check, resize, split_frames
from .utils import ensure_output_dir, get_logger, next_available_path

_DEFAULT_FORMATS = ["png", "sheet", "gif", "atlas"]
_VALID_FORMATS = {"png", "sheet", "gif", "atlas"}


# --------------------------------------------------------------------------- #
# Parser
# --------------------------------------------------------------------------- #


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sprite-kit",
        description="Generate, post-process, and export 2D game sprite assets.",
    )
    sub = parser.add_subparsers(dest="command", metavar="{generate,process,export,pipeline}")

    _add_generate_parser(sub)
    _add_process_parser(sub)
    _add_export_parser(sub)
    _add_pipeline_parser(sub)

    return parser


def _add_generate_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("generate", help="Generate a raw sprite-sheet PNG via OpenAI.")
    p.add_argument("--prompt", required=True, help="Subject / action description.")
    p.add_argument("--template", default="pixel_art", help="Template name (default: pixel_art).")
    p.add_argument("--frames", type=int, default=3, help="Frame count (default: 3).")
    p.add_argument("--layout", default="1x3", help='Grid layout, e.g. "1x3" (default: 1x3).')
    p.add_argument("--size", default=None, help="Image size override (e.g. 1024x1024).")
    p.add_argument("--quality", default=None, help="Quality override (low/medium/high).")
    p.add_argument(
        "--output",
        default=None,
        help="Output directory (default: $SPRITE_KIT_OUTPUT_DIR or ./output).",
    )
    p.add_argument("--force", action="store_true", help="Overwrite existing files.")


def _add_process_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("process", help="Post-process an existing sheet PNG.")
    p.add_argument("--input", required=True, help="Input sheet PNG path.")
    p.add_argument("--layout", required=True, help='Grid layout, e.g. "1x3".')
    p.add_argument(
        "--chroma-key",
        default=None,
        help="Chroma color (default: $SPRITE_KIT_CHROMA_KEY or #FF00FF).",
    )
    p.add_argument(
        "--fuzz",
        type=int,
        default=None,
        help="Chroma fuzz percent (default: $SPRITE_KIT_CHROMA_FUZZ or 15).",
    )
    p.add_argument(
        "--anchor",
        default="bottom-center",
        choices=["bottom-center", "top-center", "center"],
        help="Frame alignment anchor (default: bottom-center).",
    )
    p.add_argument(
        "--output",
        default=None,
        help="Output directory (default: $SPRITE_KIT_OUTPUT_DIR or ./output).",
    )
    p.add_argument("--force", action="store_true", help="Overwrite existing files.")


def _add_export_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("export", help="Export a directory of frame PNGs to sheet/gif/atlas.")
    p.add_argument("--input", required=True, help="Directory of frame PNGs (or a single sheet).")
    p.add_argument(
        "--format",
        nargs="+",
        default=["png", "sheet"],
        choices=sorted(_VALID_FORMATS),
        help="One or more output formats (default: png sheet).",
    )
    p.add_argument("--fps", type=int, default=8, help="GIF frames per second (default: 8).")
    p.add_argument(
        "--columns",
        type=int,
        default=None,
        help="Sheet column count (default: derive from frame count).",
    )
    p.add_argument(
        "--output",
        default=None,
        help="Output directory (default: $SPRITE_KIT_OUTPUT_DIR or ./output).",
    )
    p.add_argument("--force", action="store_true", help="Overwrite existing files.")


def _add_pipeline_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("pipeline", help="generate + process + export end to end.")
    p.add_argument("--prompt", required=True, help="Subject / action description.")
    p.add_argument("--template", default="pixel_art", help="Template name (default: pixel_art).")
    p.add_argument("--frames", type=int, default=3, help="Frame count (default: 3).")
    p.add_argument("--layout", default="1x3", help='Grid layout, e.g. "1x3" (default: 1x3).')
    p.add_argument("--size", default=None, help="Image size override.")
    p.add_argument("--quality", default=None, help="Quality override.")
    p.add_argument(
        "--format",
        nargs="+",
        default=list(_DEFAULT_FORMATS),
        choices=sorted(_VALID_FORMATS),
        help="Output formats (default: png sheet gif atlas).",
    )
    p.add_argument("--fps", type=int, default=8, help="GIF frames per second (default: 8).")
    p.add_argument(
        "--chroma-key",
        default=None,
        help="Chroma color (default: $SPRITE_KIT_CHROMA_KEY or #FF00FF).",
    )
    p.add_argument(
        "--fuzz",
        type=int,
        default=None,
        help="Chroma fuzz percent override (CLI > template > config).",
    )
    p.add_argument(
        "--anchor",
        default="bottom-center",
        choices=["bottom-center", "top-center", "center"],
        help="Frame alignment anchor (default: bottom-center).",
    )
    p.add_argument(
        "--output",
        default=None,
        help="Output directory (default: $SPRITE_KIT_OUTPUT_DIR or ./output).",
    )
    p.add_argument("--force", action="store_true", help="Overwrite existing files.")


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint. Returns process exit code (0 ok, non-zero on error)."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help(sys.stderr)
        return 2

    handlers = {
        "generate": _cmd_generate,
        "process": _cmd_process,
        "export": _cmd_export,
        "pipeline": _cmd_pipeline,
    }
    handler = handlers.get(args.command)
    if handler is None:  # pragma: no cover - argparse already filters this
        parser.print_help(sys.stderr)
        return 2

    log = get_logger("sprite_kit.cli")
    try:
        return handler(args, log)
    except (ConfigError, TemplateError, GenerateError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except FileNotFoundError as exc:
        print(f"Error: file not found — {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except yaml.YAMLError as exc:
        print(f"Error: invalid YAML — {exc}", file=sys.stderr)
        return 1
    except OSError as exc:  # PIL.UnidentifiedImageError, PermissionError, etc.
        print(f"Error: {exc}", file=sys.stderr)
        return 1


# --------------------------------------------------------------------------- #
# Command handlers
# --------------------------------------------------------------------------- #


def _cmd_generate(args: argparse.Namespace, log: Any) -> int:
    cfg = load_config(cli_args=_cli_args_for_config(args))
    out_dir = ensure_output_dir(_resolve_output(args, cfg))
    raw_bytes, _used_prompt, meta = generate_sprite(
        prompt=args.prompt,
        template=args.template,
        frames=args.frames,
        layout=args.layout,
        size=args.size,
        quality=args.quality,
    )
    target = out_dir / "raw_sheet.png"
    if not args.force:
        target = next_available_path(target)
    target.write_bytes(raw_bytes)
    log.info("wrote %s", target)

    meta_path = out_dir / "metadata.json"
    if not args.force:
        meta_path = next_available_path(meta_path)
    export_metadata({**meta, "pipeline": ["generate"]}, meta_path)
    log.info("wrote %s", meta_path)
    return 0


def _cmd_process(args: argparse.Namespace, log: Any) -> int:
    cfg = load_config(cli_args=_cli_args_for_config(args))
    out_dir = ensure_output_dir(_resolve_output(args, cfg))
    rows, cols = _parse_layout(args.layout)
    chroma = args.chroma_key if args.chroma_key is not None else cfg["chroma_key"]
    fuzz = args.fuzz if args.fuzz is not None else cfg["chroma_fuzz"]
    sheet = Image.open(args.input)
    frames = _process_frames(
        sheet, rows=rows, cols=cols, chroma=chroma, fuzz=fuzz, anchor=args.anchor
    )

    qc = qc_check(frames)
    for issue in qc.get("issues", []):
        log.warning("QC: %s", issue)

    paths = _safe_export_frames(frames, out_dir, force=args.force)
    for p in paths:
        log.info("wrote %s", p)
    return 0


def _cmd_export(args: argparse.Namespace, log: Any) -> int:
    cfg = load_config(cli_args=_cli_args_for_config(args))
    out_dir = ensure_output_dir(_resolve_output(args, cfg))
    frames = _load_frames_from_input(args.input)
    columns = args.columns if args.columns is not None else len(frames)
    paths = _export_formats(
        frames,
        out_dir=out_dir,
        formats=args.format,
        columns=columns,
        fps=args.fps,
        name="sprite",
        force=args.force,
    )
    for p in paths:
        log.info("wrote %s", p)
    return 0


def _cmd_pipeline(args: argparse.Namespace, log: Any) -> int:
    return run_pipeline(args, log)


# --------------------------------------------------------------------------- #
# Pipeline orchestration
# --------------------------------------------------------------------------- #


def run_pipeline(args: argparse.Namespace, log: Any) -> int:
    """Generate -> process -> export end-to-end. ADR-3 honoured per file."""
    cfg = load_config(cli_args=_cli_args_for_config(args))
    require_api_key(cfg)

    out_dir = ensure_output_dir(_resolve_output(args, cfg))
    rows, cols = _parse_layout(args.layout)

    # Template post_process block drives chroma fuzz + optional resize step.
    # Priority: CLI flag > template post_process > config default.
    tpl = load_template(args.template)
    post = (tpl.get("style") or {}).get("post_process") or {}

    fuzz = _resolve_fuzz(args, post, cfg)
    chroma = args.chroma_key if args.chroma_key is not None else cfg["chroma_key"]

    raw_bytes, used_prompt, meta = generate_sprite(
        prompt=args.prompt,
        template=args.template,
        frames=args.frames,
        layout=args.layout,
        size=args.size,
        quality=args.quality,
    )
    log.info("generated %d bytes from prompt %r", len(raw_bytes), used_prompt[:60])

    sheet = Image.open(io.BytesIO(raw_bytes))
    frames = _process_frames(
        sheet, rows=rows, cols=cols, chroma=chroma, fuzz=fuzz, anchor=args.anchor
    )

    target_scale = post.get("target_scale")
    resize_method = post.get("resize_method", "nearest")
    if target_scale is not None:
        frames = [resize(f, scale=float(target_scale), method=resize_method) for f in frames]
        log.info("resized frames by scale=%s using %s", target_scale, resize_method)

    qc = qc_check(frames)
    for issue in qc.get("issues", []):
        log.warning("QC: %s", issue)
    if len(qc.get("blank_frames", [])) == len(frames):
        raise GenerateError(
            "All output frames are blank after post-processing. "
            "Try a different prompt, lower --fuzz, or check the chroma key."
        )

    columns = cols
    paths = _export_formats(
        frames,
        out_dir=out_dir,
        formats=args.format,
        columns=columns,
        fps=args.fps,
        name=args.template,
        force=args.force,
    )
    for p in paths:
        log.info("wrote %s", p)

    meta_payload = {
        **meta,
        "pipeline": ["generate", "chroma_key_remove", "despill", "split_frames", "align_frames"],
        "qc": qc,
        "outputs": [str(p) for p in paths],
    }
    meta_path = out_dir / "metadata.json"
    if not args.force:
        meta_path = next_available_path(meta_path)
    export_metadata(meta_payload, meta_path)
    log.info("wrote %s", meta_path)
    return 0


# --------------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------------- #


def _process_frames(
    sheet: Image.Image,
    *,
    rows: int,
    cols: int,
    chroma: str,
    fuzz: int,
    anchor: str,
) -> list[Image.Image]:
    """Run chroma key + despill per frame, split, then align."""
    cells = split_frames(sheet, rows, cols)
    cleaned = [despill(chroma_key_remove(cell, chroma=chroma, fuzz=fuzz)) for cell in cells]
    return align_frames(cleaned, anchor=anchor)  # type: ignore[arg-type]


def _safe_export_frames(
    frames: list[Image.Image],
    out_dir: Path,
    *,
    force: bool,
    name_prefix: str = "frame",
) -> list[Path]:
    """Wrap export_frames so ADR-3 suffix policy applies per file."""
    if force:
        return export_frames(frames, out_dir, name_prefix=name_prefix)

    width = max(3, len(str(len(frames))))
    written: list[Path] = []
    for index, frame in enumerate(frames, start=1):
        candidate = out_dir / f"{name_prefix}_{index:0{width}d}.png"
        target = next_available_path(candidate)
        target.parent.mkdir(parents=True, exist_ok=True)
        frame.save(target, format="PNG")
        written.append(target)
    return written


def _export_formats(
    frames: list[Image.Image],
    *,
    out_dir: Path,
    formats: list[str],
    columns: int,
    fps: int,
    name: str,
    force: bool,
) -> list[Path]:
    """Dispatch each requested format through the suffix-aware writers."""
    written: list[Path] = []

    if "png" in formats:
        written.extend(_safe_export_frames(frames, out_dir, force=force))

    if "sheet" in formats:
        sheet_target = out_dir / f"{name}_sheet.png"
        if not force:
            sheet_target = next_available_path(sheet_target)
        written.append(export_sheet(frames, columns=columns, output=sheet_target))

    if "gif" in formats:
        gif_target = out_dir / f"{name}.gif"
        if not force:
            gif_target = next_available_path(gif_target)
        written.append(export_gif(frames, output=gif_target, fps=fps))

    if "atlas" in formats:
        atlas_target = out_dir / f"{name}_atlas.json"
        if not force:
            atlas_target = next_available_path(atlas_target)
        written.append(export_atlas(frames, name=name, output=atlas_target))

    return written


def _load_frames_from_input(input_path: str | Path) -> list[Image.Image]:
    """Load frames from either a directory of frame_*.png files or a single sheet image.

    Directory mode only picks up files matching ``frame_*.png`` (the prefix
    used by :func:`sprite_kit.export.export_frames`). This skips sheet PNGs
    written by previous pipeline runs (e.g. ``raw_sheet.png``,
    ``pixel_art_sheet.png``) so they don't get reloaded as individual frames.
    """
    p = Path(input_path)
    if p.is_dir():
        frame_files = sorted(p.glob("frame_*.png"))
        if not frame_files:
            raise FileNotFoundError(f"No frame_*.png files found in directory: {p}")
        return [Image.open(f).convert("RGBA") for f in frame_files]
    if p.is_file():
        return [Image.open(p).convert("RGBA")]
    raise FileNotFoundError(f"Input does not exist: {p}")


def _parse_layout(layout: str) -> tuple[int, int]:
    """Parse ``"RxC"`` or ``"R*C"`` into ``(rows, cols)`` integers."""
    sep = "x" if "x" in layout else "*"
    try:
        rows_str, cols_str = layout.lower().split(sep)
        rows, cols = int(rows_str), int(cols_str)
    except (ValueError, AttributeError) as exc:
        raise ValueError(f"Invalid --layout {layout!r}; expected format like '1x3'.") from exc
    if rows < 1 or cols < 1:
        raise ValueError(f"--layout dimensions must be >= 1, got {rows}x{cols}.")
    return rows, cols


def _resolve_output(args: argparse.Namespace, cfg: dict[str, Any]) -> str:
    """Resolve output directory: CLI flag > config (env / .env / default)."""
    cli_value = getattr(args, "output", None)
    if cli_value is not None:
        return cli_value
    return cfg["output_dir"]


def _resolve_fuzz(
    args: argparse.Namespace,
    post_process: dict[str, Any],
    cfg: dict[str, Any],
) -> int:
    """Pipeline fuzz precedence: CLI flag > template post_process > config default."""
    if args.fuzz is not None:
        return int(args.fuzz)
    template_fuzz = post_process.get("chroma_fuzz")
    if template_fuzz is not None:
        return int(template_fuzz)
    return int(cfg["chroma_fuzz"])


def _cli_args_for_config(args: argparse.Namespace) -> dict[str, Any]:
    """Build the dict passed to ``load_config`` from parsed CLI args."""
    mapping = {
        "model": None,
        "quality": getattr(args, "quality", None),
        "size": getattr(args, "size", None),
        "chroma_key": getattr(args, "chroma_key", None),
        "chroma_fuzz": getattr(args, "fuzz", None),
        "output_dir": getattr(args, "output", None),
    }
    return {k: v for k, v in mapping.items() if v is not None}
