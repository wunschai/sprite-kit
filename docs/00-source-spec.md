# sprite-kit — 專案規格書

> 獨立的 2D 遊戲素材生成與後處理工具包。
> 透過 OpenAI Image API 生成 sprite sheet，搭配本地 Python 後處理管線輸出遊戲可用的透明 PNG、GIF 和 sprite atlas。
> 設計為可被任意專案引入的獨立模組。

---

## 1. 專案目標

打造一個**與專案無關、可獨立運作**的 2D 遊戲素材生成工具，滿足以下需求：

- 從文字描述生成 sprite sheet（呼叫 OpenAI gpt-image-2 API）
- 從已有圖片做後處理（色鍵去背、切格、對齊、GIF 組裝）
- 支援即時模式（Standard API）和批次模式（Batch API，省 50% 費用）
- 內建多種畫風的 prompt 模板（像素風、粗獷主義、復古未來主義、科技未來風）
- 可被 Claude Code、n8n、shell script、CI/CD 或任何外部系統呼叫

---

## 2. 設計原則

1. **零耦合**：不綁定任何遊戲引擎、AI agent 框架或特定專案結構
2. **CLI 優先**：所有功能都可透過命令列呼叫，方便整合
3. **模組化**：生成、後處理、匯出三層分離，可獨立使用
4. **可擴展**：prompt 模板和後處理 pipeline 都可自訂

---

## 3. 目錄結構

```
sprite-kit/
├── README.md                    # 專案說明（中英雙語）
├── README.zh-TW.md              # 繁體中文說明
├── LICENSE                      # MIT License
├── requirements.txt             # Python 依賴
├── setup.py                     # pip install 支援
├── .env.example                 # 環境變數範本
├── CLAUDE.md                    # Claude Code 專用指引
│
├── sprite_kit/                  # 主套件
│   ├── __init__.py
│   ├── cli.py                   # CLI 入口（argparse）
│   ├── config.py                # 設定管理（API key、預設參數）
│   ├── generate.py              # 圖像生成模組
│   ├── batch.py                 # Batch API 模組
│   ├── process.py               # 後處理模組（去背、切格、對齊）
│   ├── export.py                # 匯出模組（PNG、GIF、atlas JSON）
│   └── utils.py                 # 共用工具函式
│
├── templates/                   # Prompt 模板
│   ├── base.yaml                # 基礎模板結構
│   ├── pixel_art.yaml           # 像素風
│   ├── brutalism.yaml           # 粗獷主義
│   ├── retro_futurism.yaml      # 復古未來主義
│   ├── tech_futurism.yaml       # 科技未來風
│   └── custom.yaml.example      # 自訂模板範例
│
├── tests/                       # 測試
│   ├── test_process.py          # 後處理單元測試
│   ├── test_export.py           # 匯出單元測試
│   └── fixtures/                # 測試用素材
│       └── sample_sheet.png     # 帶色鍵背景的範例 sprite sheet
│
└── docs/                        # 文件
    ├── api-reference.md         # API 參考
    ├── prompt-guide.md          # Prompt 撰寫指南
    └── integration-guide.md     # 整合指南（Claude Code / n8n / shell）
```

---

## 4. 核心模組規格

### 4.1 config.py — 設定管理

```python
# 設定來源優先順序：
# 1. CLI 參數
# 2. 環境變數
# 3. .env 檔案
# 4. 預設值

# 必要環境變數
OPENAI_API_KEY = ""          # OpenAI API key

# 可選環境變數
SPRITE_KIT_MODEL = "gpt-image-2"          # 圖像模型
SPRITE_KIT_QUALITY = "medium"              # low / medium / high
SPRITE_KIT_SIZE = "1536x1024"              # 輸出尺寸
SPRITE_KIT_CHROMA_KEY = "#FF00FF"          # 色鍵背景色
SPRITE_KIT_CHROMA_FUZZ = 15               # 色鍵容差 (%)
SPRITE_KIT_OUTPUT_DIR = "./output"         # 輸出目錄
```

### 4.2 generate.py — 圖像生成模組

**功能**：呼叫 OpenAI Image API 生成 raw sprite sheet

**Standard API 呼叫方式**：
```python
from openai import OpenAI
import base64

client = OpenAI()

result = client.images.generate(
    model="gpt-image-2",
    prompt=assembled_prompt,
    size="1536x1024",
    quality="medium",
    output_format="png",
    n=1
)

image_base64 = result.data[0].b64_json
image_bytes = base64.b64decode(image_base64)
```

**關鍵設計**：
- 接收使用者描述 + 模板名稱 → 組裝完整 prompt
- 自動附加色鍵背景指令（`Solid #FF00FF magenta background`）
- 自動附加幀一致性指令（`Consistent proportions and pixel scale across all frames`）
- 支援傳入參考圖（reference image）做風格一致性控制
- 回傳 raw PNG bytes + 使用的 prompt + metadata

**API 費用參考（gpt-image-2, 1024×1024）**：
- low: ~$0.006/張
- medium: ~$0.053/張
- high: ~$0.211/張

### 4.3 batch.py — Batch API 模組

**功能**：打包多個生成請求，透過 Batch API 非同步處理

**流程**：
1. `prepare_batch(requests: list[dict]) -> str`
   - 將多個請求寫成 `.jsonl` 格式
   - 每個請求包含 `custom_id`、`method`、`url`、`body`

2. `submit_batch(jsonl_path: str) -> str`
   - 上傳 `.jsonl` 到 Files API
   - 建立 Batch job
   - 回傳 batch_id

3. `poll_batch(batch_id: str) -> str`
   - 輪詢 Batch 狀態（validating → in_progress → completed）
   - 完成後回傳 output_file_id

4. `download_batch(output_file_id: str, output_dir: str) -> list[str]`
   - 下載結果
   - 解析每個請求的圖像
   - 存檔並回傳檔案路徑列表

**JSONL 格式範例**：
```jsonl
{"custom_id": "idle-pixel", "method": "POST", "url": "/v1/images/generations", "body": {"model": "gpt-image-2", "prompt": "...", "size": "1536x1024", "quality": "medium"}}
{"custom_id": "walk-pixel", "method": "POST", "url": "/v1/images/generations", "body": {"model": "gpt-image-2", "prompt": "...", "size": "1536x1024", "quality": "medium"}}
```

**Batch API 費用**：Standard API 的 50%（所有 token 類型）

**限制**：
- 24 小時完成窗口
- 單檔最多 50,000 請求 / 200MB
- 不支援串流
- 不支援 multipart 參考圖上傳（需用 file_id 或 image_url）

### 4.4 process.py — 後處理模組

**功能**：將 raw sprite sheet 處理成遊戲可用的素材

參考 agent-sprite-forge 的 `generate2dsprite.py` 後處理邏輯，依賴 Pillow + numpy。

**Pipeline 步驟**：

1. **色鍵去背 (chroma_key_remove)**
   - 輸入：帶 #FF00FF 背景的 raw PNG
   - 使用容差匹配（預設 fuzz=15%）處理邊緣洋紅殘留
   - 特別處理發光效果溢出到接近洋紅色的區域
   - 輸出：RGBA 透明背景 PNG

2. **去色溢 (despill)**
   - 移除角色邊緣的洋紅色暈染
   - 對受影響的像素做色彩校正

3. **幀切割 (split_frames)**
   - 自動偵測 grid layout（根據等距分割或 bounding box）
   - 支援指定 rows × cols 手動切割
   - 輸出：個別幀 PNG 列表

4. **Bounding Box 對齊 (align_frames)**
   - 計算每幀的實際內容 bounding box
   - 統一所有幀的 canvas 大小
   - 角色錨點對齊（底部中心或自訂錨點）

5. **縮放 (resize)**
   - 支援 nearest-neighbor 縮放（保持像素風銳利邊緣）
   - 支援指定目標尺寸或縮放比例

6. **品質檢查 (qc_check)**
   - 檢查空白幀
   - 檢查幀間尺寸一致性
   - 檢查透明度正確性
   - 回傳 QC 報告

### 4.5 export.py — 匯出模組

**功能**：將處理後的幀匯出為多種格式

1. **透明 PNG 幀**
   - 個別幀存為 `frame_001.png`, `frame_002.png`, ...

2. **Sprite Sheet PNG**
   - 將對齊後的幀重新組成 sheet
   - 支援自訂 columns 數量
   - 透明背景

3. **動畫 GIF**
   - 支援自訂 FPS
   - 透明背景 GIF
   - 自動計算最佳全域色盤

4. **Sprite Atlas JSON**
   - 相容主流遊戲引擎格式
   - 包含每幀的 x, y, width, height, sourceSize

```json
{
  "frames": {
    "idle_001": { "x": 0, "y": 0, "w": 64, "h": 64 },
    "idle_002": { "x": 64, "y": 0, "w": 64, "h": 64 }
  },
  "meta": {
    "image": "idle_sheet.png",
    "size": { "w": 256, "h": 64 },
    "scale": 1,
    "format": "RGBA8888"
  }
}
```

5. **Pipeline Metadata JSON**
   - 記錄使用的 prompt、模型、品質、處理步驟
   - 方便重現或批次管理

### 4.6 cli.py — CLI 入口

**命令結構**：

```bash
# 生成 sprite sheet（即時模式）
sprite-kit generate \
  --prompt "cyberpunk hacker idle animation" \
  --template pixel_art \
  --frames 3 \
  --layout 1x3 \
  --size 1536x1024 \
  --quality medium \
  --output ./output/hacker-idle/

# 生成 sprite sheet（批次模式）
sprite-kit batch \
  --input requests.yaml \
  --output ./output/batch-001/

# 僅做後處理（已有 raw sheet）
sprite-kit process \
  --input raw-sheet.png \
  --layout 1x4 \
  --chroma-key "#FF00FF" \
  --fuzz 15 \
  --anchor bottom-center \
  --output ./output/processed/

# 僅做匯出（已有處理後的幀）
sprite-kit export \
  --input ./frames/ \
  --format gif png atlas \
  --fps 12 \
  --columns 4 \
  --output ./output/final/

# 完整管線（生成 + 後處理 + 匯出）
sprite-kit pipeline \
  --prompt "fire mage cast animation with projectile and impact" \
  --template tech_futurism \
  --frames 3 \
  --layout 1x3 \
  --format all \
  --output ./output/fire-mage/
```

---

## 5. Prompt 模板規格

模板為 YAML 格式，定義畫風的標準化 prompt 結構。

### 5.1 基礎模板結構 (base.yaml)

```yaml
# base.yaml - 所有模板繼承此結構
version: 1
base:
  background: "Solid #FF00FF magenta background."
  consistency: "Consistent character proportions and pixel scale across all frames."
  margin: "Each frame must fit fully inside its cell with clear margin on all sides."
  separation: "No overlap between frames. Clear visual separation."

# 模板變數（由使用者或 CLI 填入）
variables:
  subject: ""          # 角色/物件描述
  action: ""           # 動作描述
  frame_count: 3       # 幀數
  layout: "1x3"        # 排列方式 (rows x cols)
  view: "side-view"    # 視角
```

### 5.2 像素風模板 (pixel_art.yaml)

```yaml
extends: base
style:
  name: "pixel_art"
  prompt_prefix: "Create a 2D pixel art sprite sheet"
  style_keywords:
    - "16-bit SNES-style pixel art"
    - "limited 32-color palette"
    - "clean blocky pixel style with sharp edges"
    - "retro JRPG aesthetic"
  size_recommendation: "1536x1024"
  quality_recommendation: "medium"
  post_process:
    resize_method: "nearest"     # 保持像素銳利
    target_scale: 0.5            # 生成 2x 再縮小
```

### 5.3 粗獷主義模板 (brutalism.yaml)

```yaml
extends: base
style:
  name: "brutalism"
  prompt_prefix: "Create a set of brutalist-style game assets"
  style_keywords:
    - "raw concrete texture"
    - "harsh geometric forms"
    - "minimal color palette using only black, white, and rust orange"
    - "heavy visual weight with sharp edges"
    - "flat lighting, no gradients, no rounded corners"
    - "architectural brutalism applied to game design"
  size_recommendation: "1024x1024"
  quality_recommendation: "medium"
  post_process:
    resize_method: "lanczos"     # 保留紋理細節
```

### 5.4 復古未來主義模板 (retro_futurism.yaml)

```yaml
extends: base
style:
  name: "retro_futurism"
  prompt_prefix: "Create a 2D retro-futuristic sprite sheet"
  style_keywords:
    - "1980s retrofuturism aesthetic"
    - "chrome armor with neon accents"
    - "CRT scanline visual style"
    - "color palette inspired by Tron and Blade Runner"
    - "deep navy, electric cyan, hot magenta, chrome silver"
  size_recommendation: "1536x1024"
  quality_recommendation: "medium"
  post_process:
    resize_method: "lanczos"
```

### 5.5 科技未來風模板 (tech_futurism.yaml)

```yaml
extends: base
style:
  name: "tech_futurism"
  prompt_prefix: "Create a 2D sci-fi tech style sprite sheet"
  style_keywords:
    - "holographic particle effects"
    - "electric arcs and glowing energy"
    - "futuristic HUD-style visual elements"
    - "electric blue core, white-hot center, purple edge glow"
    - "clean edges suitable for game engine integration"
  size_recommendation: "1536x1024"
  quality_recommendation: "medium"
  post_process:
    resize_method: "lanczos"
    chroma_fuzz: 20              # 發光效果需要更高容差
```

---

## 6. CLAUDE.md — Claude Code 整合指引

此檔案放在專案根目錄，讓 Claude Code 理解如何使用此工具。

```markdown
# sprite-kit

2D 遊戲素材生成與後處理工具包。

## 快速使用

### 環境設定
確保 OPENAI_API_KEY 環境變數已設定。

### 生成素材
python -m sprite_kit.cli generate --prompt "描述" --template pixel_art --output ./output/

### 僅後處理已有圖片
python -m sprite_kit.cli process --input raw.png --layout 1x4 --output ./output/

### 批次生成（省 50% 費用）
python -m sprite_kit.cli batch --input requests.yaml --output ./output/

## 可用模板
- pixel_art: 像素風（16-bit, SNES 風格）
- brutalism: 粗獷主義（水泥質感、幾何造型）
- retro_futurism: 復古未來主義（80s, Tron/Blade Runner）
- tech_futurism: 科技未來風（全息、電弧、能量環）

## 專案整合
此工具可作為 git submodule 或 pip install 引入任何專案。
```

---

## 7. 依賴

### requirements.txt

```
openai>=1.30.0
Pillow>=10.0
numpy>=1.26
pyyaml>=6.0
python-dotenv>=1.0
```

### Python 版本

- 最低 Python 3.10

---

## 8. 整合方式

### 8.1 Git Submodule（推薦）

```bash
cd your-game-project
git submodule add https://github.com/YOUR_USER/sprite-kit.git tools/sprite-kit
pip install -r tools/sprite-kit/requirements.txt
```

### 8.2 pip install

```bash
pip install git+https://github.com/YOUR_USER/sprite-kit.git
```

### 8.3 直接呼叫

```bash
# 從任何專案目錄
python /path/to/sprite-kit/sprite_kit/cli.py generate --prompt "..." --output ./assets/
```

### 8.4 作為 Python 模組引入

```python
from sprite_kit.generate import generate_sprite
from sprite_kit.process import chroma_key_remove, split_frames, align_frames
from sprite_kit.export import export_gif, export_atlas

# 生成
raw_bytes = generate_sprite(
    prompt="cyberpunk hacker idle",
    template="pixel_art",
    frames=3
)

# 後處理
transparent = chroma_key_remove(raw_bytes, fuzz=15)
frames = split_frames(transparent, cols=3)
aligned = align_frames(frames, anchor="bottom-center")

# 匯出
export_gif(aligned, "hacker-idle.gif", fps=8)
export_atlas(aligned, "hacker-idle", format="json")
```

### 8.5 n8n 整合

在 Execute Command node 中：
```bash
cd /path/to/sprite-kit && python -m sprite_kit.cli pipeline \
  --prompt "{{$json.prompt}}" \
  --template "{{$json.style}}" \
  --output "/path/to/assets/{{$json.name}}/"
```

---

## 9. 開發優先順序

### Phase 1 — 核心功能（MVP）
1. config.py（設定管理 + .env 支援）
2. generate.py（Standard API 即時生成）
3. process.py（色鍵去背 + 切格 + 對齊）
4. export.py（PNG 幀 + GIF + atlas JSON）
5. cli.py（generate / process / export / pipeline 四個命令）
6. 四個 prompt 模板

### Phase 2 — 批次與效率
7. batch.py（Batch API 支援）
8. cli.py 加入 batch 命令
9. 參考圖支援（reference image input）

### Phase 3 — 擴展
10. MCP Server 封裝（讓 Claude Code 用自然語言呼叫）
11. 方向性 sprite sheet 支援（四方向 walk cycle 自動切割）
12. sprite sheet 合併工具（多個動作合成一張完整 atlas）

---

## 10. 費用估算

基於 gpt-image-2 API，1024×1024 medium quality：

| 場景 | Standard API | Batch API |
|------|-------------|-----------|
| 單張 sprite sheet | $0.053 | $0.027 |
| 一個角色完整素材（8 張） | $0.42 | $0.21 |
| 20 個角色 | $8.48 | $4.24 |
| 探索階段試 30 種風格 | $1.59 | $0.80 |

API key 最低儲值 $5，足夠生成約 90 張中品質 sprite sheet（Standard）或 180 張（Batch）。

---

## 11. 已驗證的測試結果

以下四種畫風已透過 ChatGPT Plus 手動測試，確認 gpt-image-2 可穩定產出：

1. **像素風** — 角色 idle 動畫（3 幀），角色一致性高，色鍵背景乾淨
2. **粗獷主義** — UI icon set（3×2 grid），水泥質感和幾何造型到位
3. **復古未來主義** — 角色 walk cycle（4 幀），chrome + 霓虹配色佳，幀間動作差異需注意
4. **科技未來風** — 技能特效（charge/fire/dissipate），發光效果邊緣需較高色鍵容差

主要需後處理解決的問題：
- 幀間對齊和比例校正（walk cycle 最明顯）
- 色鍵去背的發光溢出邊緣處理
- 幀間動作差異不足時需重新生成

---

## 12. 參考資料

- [agent-sprite-forge](https://github.com/0x0funky/agent-sprite-forge) — Codex 版 sprite 生成 skill，本專案參考其後處理管線邏輯
- [OpenAI Image Generation Guide](https://developers.openai.com/api/docs/guides/image-generation)
- [OpenAI Batch API Guide](https://platform.openai.com/docs/guides/batch)
- [GPT Image Generation Prompting Guide](https://developers.openai.com/cookbook/examples/multimodal/image-gen-models-prompting-guide)
- [OpenAI API Pricing](https://openai.com/api/pricing/)
