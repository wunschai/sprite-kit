# Sprite Kit

獨立的 2D 遊戲素材生成與後處理工具包。用 OpenAI Image API 產出 sprite
sheet，再用本地 Python 管線輸出透明 PNG / GIF / atlas JSON。

English：[README.md](README.md)

## 特色

- 4 個內建畫風模板：`pixel_art` / `brutalism` / `retro_futurism` / `tech_futurism`
- 色鍵去背（`#FF00FF` 洋紅）+ despill 去色溢
- 自動切格 + bottom-center 錨點對齊
- 多格式輸出：個別 PNG、sprite sheet、透明 GIF、atlas JSON
- 一個指令從 prompt 到遊戲可用素材

## 安裝

推薦（uv）：

```bash
uv venv
uv pip install -e ".[dev]"
```

或用 pip：

```bash
pip install -e .
```

設定 OpenAI key：

```bash
cp .env.example .env
# 編輯 .env 填入 OPENAI_API_KEY
```

## 快速開始

完整 pipeline（生成到所有格式）：

```bash
sprite-kit pipeline \
  --prompt "fire mage cast animation" \
  --template tech_futurism \
  --frames 3 --layout 1x3 \
  --output ./output/fire-mage/
```

只生成：

```bash
sprite-kit generate --prompt "cyberpunk hacker idle" --output ./output/
```

只後處理：

```bash
sprite-kit process --input raw.png --layout 1x4 --output ./output/
```

只匯出（從幀資料夾）：

```bash
sprite-kit export --input ./output/ --format gif atlas --fps 8
```

加 `--force` 直接覆寫既有檔案；預設會自動加 `-2`、`-3` 等後綴避免覆蓋（ADR-3）。

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
# 將 raw_bytes 餵給 process / export 函式
```

## 模板

內建模板放在 `templates/*.yaml`，透過 `extends:` 繼承 `base.yaml`。
使用者可放自訂 YAML 到 `templates/`，用 `--template my_style` 載入。
範本見 `templates/custom.yaml.example`。

## 整合方式

1. **Git submodule** — `git submodule add https://github.com/YOUR/sprite-kit tools/sprite-kit`
2. **pip install** — `pip install git+https://github.com/YOUR/sprite-kit.git`
3. **直接呼叫 CLI** — `python -m sprite_kit.cli pipeline --prompt "..."`
4. **Python 模組 import** — 見上方 Python API 區段
5. **n8n / CI 管線** — 任何 shell node 都能呼叫 CLI

完整範例見 `docs/TECHSTACK.md` 第 5 節。

## 設定

優先順序：CLI 參數 > 環境變數 > `.env` 檔案 > 程式內預設值。

| 變數 | 預設 | 用途 |
|------|------|------|
| `OPENAI_API_KEY` | — | `generate` / `pipeline` 必要 |
| `SPRITE_KIT_MODEL` | `gpt-image-2` | 圖像模型 |
| `SPRITE_KIT_QUALITY` | `medium` | low / medium / high |
| `SPRITE_KIT_SIZE` | `1536x1024` | 輸出尺寸 |
| `SPRITE_KIT_CHROMA_KEY` | `#FF00FF` | 色鍵背景色 |
| `SPRITE_KIT_CHROMA_FUZZ` | `15` | 色鍵容差（%） |
| `SPRITE_KIT_OUTPUT_DIR` | `./output` | 預設輸出目錄 |

## 開發

```bash
uv venv && uv pip install -e ".[dev]"
uv run pytest                    # 單元 + mock pipeline 測試
uv run pytest -m integration     # 真實 API smoke 測試（要花錢）
uv run ruff check .
uv run ruff format .
```

## License

MIT
