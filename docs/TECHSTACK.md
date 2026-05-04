# Sprite Kit — 技術棧

## 1. 執行環境

- **Python**：最低 3.10
- **作業系統**：跨平台（macOS / Linux / Windows）— 純 Python 套件，無平台限定二進位

## 2. 主要依賴

```
openai>=1.30.0          # OpenAI Image API（Standard + Batch）
Pillow>=10.0            # 影像處理（去背、切格、resize、GIF 組裝）
numpy>=1.26             # 像素運算（色鍵容差、bounding box 計算）
pyyaml>=6.0             # Prompt 模板載入
python-dotenv>=1.0      # .env 環境變數支援
```

## 3. 設定來源優先順序

```
CLI 參數 > 環境變數 > .env 檔案 > 程式內預設值
```

### 環境變數

| 變數 | 必要 | 預設 | 用途 |
|------|------|------|------|
| `OPENAI_API_KEY` | Y | — | OpenAI API key |
| `SPRITE_KIT_MODEL` | N | `gpt-image-2` | 圖像模型 |
| `SPRITE_KIT_QUALITY` | N | `medium` | low / medium / high |
| `SPRITE_KIT_SIZE` | N | `1536x1024` | 輸出尺寸 |
| `SPRITE_KIT_CHROMA_KEY` | N | `#FF00FF` | 色鍵背景色 |
| `SPRITE_KIT_CHROMA_FUZZ` | N | `15` | 色鍵容差（%） |
| `SPRITE_KIT_OUTPUT_DIR` | N | `./output` | 輸出目錄 |

## 4. OpenAI API 規格

### Standard API（即時）

| 模型 | 尺寸 | low | medium | high |
|------|------|-----|--------|------|
| gpt-image-2 | 1024×1024 | ~$0.006 | ~$0.053 | ~$0.211 |

### Batch API

- 費用為 Standard 的 50%
- 24 小時完成窗口
- 單檔最多 50,000 請求 / 200MB
- 不支援串流
- 不支援 multipart 參考圖上傳（需用 `file_id` 或 `image_url`）

## 5. 整合方式（給下游專案）

### 5.1 Git Submodule（推薦）

```bash
cd your-game-project
git submodule add https://github.com/YOUR_USER/sprite-kit.git tools/sprite-kit
pip install -r tools/sprite-kit/requirements.txt
```

### 5.2 pip install

```bash
pip install git+https://github.com/YOUR_USER/sprite-kit.git
```

### 5.3 直接呼叫 CLI

```bash
python /path/to/sprite-kit/sprite_kit/cli.py generate --prompt "..." --output ./assets/
```

### 5.4 作為 Python 模組

```python
from sprite_kit.generate import generate_sprite
from sprite_kit.process import chroma_key_remove, split_frames, align_frames
from sprite_kit.export import export_gif, export_atlas

raw_bytes = generate_sprite(
    prompt="cyberpunk hacker idle",
    template="pixel_art",
    frames=3,
)

transparent = chroma_key_remove(raw_bytes, fuzz=15)
frames = split_frames(transparent, cols=3)
aligned = align_frames(frames, anchor="bottom-center")

export_gif(aligned, "hacker-idle.gif", fps=8)
export_atlas(aligned, "hacker-idle", format="json")
```

### 5.5 n8n 整合

在 Execute Command node：

```bash
cd /path/to/sprite-kit && python -m sprite_kit.cli pipeline \
  --prompt "{{$json.prompt}}" \
  --template "{{$json.style}}" \
  --output "/path/to/assets/{{$json.name}}/"
```

## 6. 開發工具

- **單元 / 整合測試**：Vitest 不適用（Python 專案），改用 **pytest**
- **Linter / Formatter**：待確認（建議 `ruff` + `black`，或 `ruff format`）
- **套件管理**：建議 `uv`（依 `.claude/references/AGENTS.md` 工具偏好）

> 上述開發工具尚未在 PRD 規格中明確指定，需在第一個 sprint 的 ADR 中決定。

## 7. 參考資料

- [agent-sprite-forge](https://github.com/0x0funky/agent-sprite-forge) — Codex 版 sprite 生成 skill，本專案參考其後處理管線邏輯
- [OpenAI Image Generation Guide](https://developers.openai.com/api/docs/guides/image-generation)
- [OpenAI Batch API Guide](https://platform.openai.com/docs/guides/batch)
- [GPT Image Generation Prompting Guide](https://developers.openai.com/cookbook/examples/multimodal/image-gen-models-prompting-guide)
- [OpenAI API Pricing](https://openai.com/api/pricing/)
