"""Sprite Kit: 2D game sprite asset generator + post-processor."""

from sprite_kit.cli import main, run_pipeline
from sprite_kit.config import ConfigError, load_config, require_api_key
from sprite_kit.export import (
    export_atlas,
    export_frames,
    export_gif,
    export_metadata,
    export_sheet,
)
from sprite_kit.generate import (
    GenerateError,
    TemplateError,
    assemble_prompt,
    generate_sprite,
    load_template,
)
from sprite_kit.process import (
    align_frames,
    chroma_key_remove,
    despill,
    qc_check,
    resize,
    split_frames,
)
from sprite_kit.utils import ensure_output_dir, get_logger, next_available_path

__all__ = [
    "ConfigError",
    "GenerateError",
    "TemplateError",
    "align_frames",
    "assemble_prompt",
    "chroma_key_remove",
    "despill",
    "ensure_output_dir",
    "export_atlas",
    "export_frames",
    "export_gif",
    "export_metadata",
    "export_sheet",
    "generate_sprite",
    "get_logger",
    "load_config",
    "load_template",
    "main",
    "next_available_path",
    "qc_check",
    "require_api_key",
    "resize",
    "run_pipeline",
    "split_frames",
]
__version__ = "0.1.0"
