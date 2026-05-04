# Sprite Kit

Stand-alone 2D game sprite asset generator and post-processor. Uses the
OpenAI Image API to produce sprite sheets, then a local Python pipeline
to output transparent PNG frames, animated GIFs, and atlas JSON.

繁體中文版：[README.zh-TW.md](README.zh-TW.md)

## Features

- 4 built-in style templates: `pixel_art`, `brutalism`, `retro_futurism`, `tech_futurism`
- Chroma-key background removal (`#FF00FF` magenta) with despill
- Auto frame splitting + bottom-center anchor alignment
- Multi-format export: individual PNGs, sprite sheet, transparent GIF, atlas JSON
- Single-command pipeline: prompt to game-ready assets

## Install

Recommended (uv):

```bash
uv venv
uv pip install -e ".[dev]"
```

Plain pip:

```bash
pip install -e .
```

Set your OpenAI key:

```bash
cp .env.example .env
# edit .env and fill OPENAI_API_KEY
```

## Quick start

Full pipeline (generate to all formats):

```bash
sprite-kit pipeline \
  --prompt "fire mage cast animation" \
  --template tech_futurism \
  --frames 3 --layout 1x3 \
  --output ./output/fire-mage/
```

Generate only:

```bash
sprite-kit generate --prompt "cyberpunk hacker idle" --output ./output/
```

Post-process an existing sheet:

```bash
sprite-kit process --input raw.png --layout 1x4 --output ./output/
```

Export a directory of frames:

```bash
sprite-kit export --input ./output/ --format gif atlas --fps 8
```

Add `--force` to overwrite existing files; the default behaviour appends
`-2`, `-3`, … to filenames on conflict (ADR-3).

## Python API

```python
from sprite_kit import (
    generate_sprite, chroma_key_remove, split_frames,
    align_frames, export_gif, export_atlas,
)

raw_bytes, prompt, meta = generate_sprite(
    prompt="cyberpunk hacker idle",
    template="pixel_art",
    frames=3,
    layout="1x3",
)
# ... feed `raw_bytes` into the process + export functions
```

## Templates

Built-in templates live in `templates/*.yaml` and inherit from
`base.yaml` via `extends:`. Drop your own YAML in `templates/` and load
it with `--template my_style`. See `templates/custom.yaml.example` for
the schema.

## Integration paths

1. **Git submodule** — `git submodule add https://github.com/YOUR/sprite-kit tools/sprite-kit`
2. **pip install** — `pip install git+https://github.com/YOUR/sprite-kit.git`
3. **Direct CLI** — `python -m sprite_kit.cli pipeline --prompt "..."`
4. **Python module import** — see Python API section above
5. **n8n / CI pipelines** — invoke the CLI from any shell node

Full examples: `docs/TECHSTACK.md` section 5.

## Configuration

Priority order: CLI arg > environment variable > `.env` file > built-in default.

| Variable | Default | Purpose |
|----------|---------|---------|
| `OPENAI_API_KEY` | — | Required for `generate` / `pipeline` |
| `SPRITE_KIT_MODEL` | `gpt-image-2` | Image model |
| `SPRITE_KIT_QUALITY` | `medium` | low / medium / high |
| `SPRITE_KIT_SIZE` | `1536x1024` | Output size |
| `SPRITE_KIT_CHROMA_KEY` | `#FF00FF` | Chroma background colour |
| `SPRITE_KIT_CHROMA_FUZZ` | `15` | Chroma tolerance percent |
| `SPRITE_KIT_OUTPUT_DIR` | `./output` | Default output directory |

## Development

```bash
uv venv && uv pip install -e ".[dev]"
uv run pytest                    # unit + mocked-pipeline tests
uv run pytest -m integration     # real-API smoke tests (costs money)
uv run ruff check .
uv run ruff format .
```

## License

MIT
