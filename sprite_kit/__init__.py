"""Sprite Kit: 2D game sprite asset generator + post-processor."""

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

__all__ = [
    "ConfigError",
    "GenerateError",
    "TemplateError",
    "align_frames",
    "assemble_prompt",
    "chroma_key_remove",
    "despill",
    "export_atlas",
    "export_frames",
    "export_gif",
    "export_metadata",
    "export_sheet",
    "generate_sprite",
    "load_config",
    "load_template",
    "qc_check",
    "require_api_key",
    "resize",
    "split_frames",
]
__version__ = "0.1.0"
