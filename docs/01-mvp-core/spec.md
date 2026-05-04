# 01-mvp-core — 規格

> Sprint：Sprite Kit 核心 MVP（Phase 1）
> 對應 PRD `docs/PRD.md` 第 4 節 Phase 1。
> 來源：`docs/00-source-spec.md` 第 3, 4.1–4.6, 5, 9 Phase 1 節。

---

## 1. 目標

完成 Sprite Kit 的核心生成 → 後處理 → 匯出管線，使用者能用單一 CLI 命令從 prompt 產出遊戲可用的透明 PNG / GIF / atlas JSON。

## 2. 非目標（這個 sprint 不做）

- Batch API 與批次命令（Phase 2）
- Reference image 風格控制（Phase 2）
- MCP Server 封裝（Phase 3）
- 方向性 sprite sheet 自動切割（Phase 3）
- atlas 合併工具（Phase 3）

## 3. User Story

### US-1：從 prompt 直出可用素材

> 作為遊戲開發者，我給一段角色描述和畫風模板，能在一個指令內拿到去背、對齊、可直接放進遊戲的 PNG 幀、GIF 動畫和 atlas JSON。

```bash
sprite-kit pipeline \
  --prompt "fire mage cast animation with projectile and impact" \
  --template tech_futurism \
  --frames 3 --layout 1x3 \
  --format all \
  --output ./output/fire-mage/
```

### US-2：對既有圖做後處理

> 作為已有 sprite sheet 圖檔的使用者，我能跳過生成步驟，直接做去背、切格、對齊、匯出。

```bash
sprite-kit process \
  --input raw-sheet.png --layout 1x4 \
  --chroma-key "#FF00FF" --fuzz 15 \
  --anchor bottom-center \
  --output ./output/processed/
```

### US-3：用內建模板降低 prompt 撰寫負擔

> 作為非美術背景的使用者，我選擇 `pixel_art` / `brutalism` / `retro_futurism` / `tech_futurism` 其中一個模板，輸入動作描述就能拿到風格穩定的素材。

### US-4：作為 Python 模組嵌入專案

> 作為其他 Python 專案的開發者，我能 `from sprite_kit.process import chroma_key_remove` 直接呼叫個別函式，不一定要走 CLI。

## 4. 驗收條件

### AC-1：CLI 命令完整

- [ ] `sprite-kit generate`：呼叫 OpenAI API 產出 raw PNG，存檔
- [ ] `sprite-kit process`：對既有 PNG 做去背 + 切格 + 對齊，輸出個別幀
- [ ] `sprite-kit export`：把幀資料夾轉成 PNG sheet / GIF / atlas JSON
- [ ] `sprite-kit pipeline`：generate + process + export 串接
- [ ] 所有命令支援 `--help`，參數有意義的預設值

### AC-2：色鍵去背正確性

- [ ] 預設 `#FF00FF` + `fuzz=15` 能去除 `tests/fixtures/sample_sheet.png` 的背景
- [ ] 邊緣無明顯洋紅殘留（despill 後肉眼檢查）
- [ ] 透明區域 alpha=0，內容區域 alpha=255

### AC-3：幀對齊正確性

- [ ] 給定 `1x3` layout，能切出 3 幀且每幀 canvas 大小一致
- [ ] `bottom-center` anchor 下，3 幀的角色腳底 y 座標一致（誤差 ≤ 1px）

### AC-4：匯出格式正確性

- [ ] PNG 個別幀檔名 `frame_001.png`、`frame_002.png` 序號補零
- [ ] GIF 透明背景、可在主流檢視器播放、FPS 與 `--fps` 參數一致
- [ ] Atlas JSON 結構符合第 6 節範例，能被 Phaser / PixiJS 解析

### AC-5：模板可用性

- [ ] 4 個內建模板（`pixel_art` / `brutalism` / `retro_futurism` / `tech_futurism`）載入無誤
- [ ] 模板自動補上色鍵背景、幀一致性、邊距、分隔指令
- [ ] 使用者可放自訂 YAML 在 `templates/` 並用 `--template my_style` 載入

### AC-6：模組化呼叫

- [ ] `from sprite_kit.generate import generate_sprite` 等 import 路徑可用
- [ ] 個別函式有 docstring 與 type hint

### AC-7：設定優先順序

- [ ] CLI 參數 > 環境變數 > `.env` > 預設值，順序正確
- [ ] 缺少 `OPENAI_API_KEY` 時 `generate` / `pipeline` 給出明確錯誤訊息（不是 traceback）

### AC-8：測試覆蓋

- [ ] `tests/test_process.py`：色鍵去背、切格、對齊三個函式都有測試
- [ ] `tests/test_export.py`：GIF、atlas JSON 匯出有測試
- [ ] `tests/fixtures/sample_sheet.png`：放一張可重現的測試素材
- [ ] `pytest` 在 CI 與本地都能通過

## 5. 相關檔案

### 5.1 預期目錄結構

```
sprite-kit/
├── README.md
├── README.zh-TW.md
├── LICENSE
├── requirements.txt
├── setup.py
├── .env.example
├── CLAUDE.md                    # 已存在（DDD + 使用指引合併版）
│
├── sprite_kit/                  # 主套件
│   ├── __init__.py
│   ├── cli.py                   # CLI 入口（argparse）
│   ├── config.py                # 設定管理
│   ├── generate.py              # 圖像生成
│   ├── process.py               # 後處理
│   ├── export.py                # 匯出
│   └── utils.py                 # 共用工具
│
├── templates/
│   ├── base.yaml
│   ├── pixel_art.yaml
│   ├── brutalism.yaml
│   ├── retro_futurism.yaml
│   ├── tech_futurism.yaml
│   └── custom.yaml.example
│
└── tests/
    ├── test_process.py
    ├── test_export.py
    └── fixtures/
        └── sample_sheet.png
```

> 註：原始規格書亦列出 `docs/api-reference.md` / `prompt-guide.md` / `integration-guide.md`。這些屬於 **使用者文件**，不在 MVP sprint 範圍，等核心 API 穩定後再開新 sprint 撰寫。

### 5.2 模組職責

| 檔案 | 職責 | 主要函式 |
|------|------|----------|
| `config.py` | 載入環境變數、`.env`、合併 CLI 參數 | `load_config()` |
| `generate.py` | 呼叫 OpenAI API、組裝 prompt、回傳 raw bytes | `generate_sprite()` |
| `process.py` | 色鍵去背、despill、切格、對齊、resize、QC | `chroma_key_remove()` `despill()` `split_frames()` `align_frames()` `resize()` `qc_check()` |
| `export.py` | 個別 PNG、sprite sheet、GIF、atlas JSON、metadata | `export_frames()` `export_sheet()` `export_gif()` `export_atlas()` `export_metadata()` |
| `cli.py` | argparse 入口、子命令分派 | `main()` |
| `utils.py` | 共用工具（檔名處理、路徑、log） | TBD |

## 6. 模組詳細規格

### 6.1 generate.py

呼叫範例（Standard API）：

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
    n=1,
)
image_bytes = base64.b64decode(result.data[0].b64_json)
```

關鍵設計：

- 接收使用者描述 + 模板名稱 → 組裝完整 prompt
- 自動附加色鍵背景指令（`Solid #FF00FF magenta background`）
- 自動附加幀一致性指令（`Consistent proportions and pixel scale across all frames`）
- 回傳 `(raw_png_bytes, used_prompt, metadata_dict)`

### 6.2 process.py — Pipeline 步驟

1. **色鍵去背 `chroma_key_remove(img, chroma="#FF00FF", fuzz=15) -> RGBA`**
   - 容差匹配處理邊緣洋紅殘留
   - 特別處理發光效果溢出到接近洋紅色的區域
2. **去色溢 `despill(img) -> RGBA`**
   - 對受影響像素做色彩校正
3. **幀切割 `split_frames(img, rows, cols) -> list[RGBA]`**
   - 支援指定 rows × cols 手動切割
   - 也支援 bounding box 自動偵測（後續可延伸）
4. **對齊 `align_frames(frames, anchor="bottom-center") -> list[RGBA]`**
   - 統一 canvas 大小
   - 錨點對齊
5. **縮放 `resize(img, scale=None, size=None, method="nearest")`**
   - nearest 保持像素風銳利，lanczos 保留紋理
6. **QC `qc_check(frames) -> dict`**
   - 空白幀、尺寸一致性、透明度檢查

### 6.3 export.py — 輸出格式

| 輸出 | 函式 | 細節 |
|------|------|------|
| 個別 PNG 幀 | `export_frames()` | `frame_001.png` 序號補零 |
| Sprite Sheet | `export_sheet(frames, columns)` | 透明背景 |
| 動畫 GIF | `export_gif(frames, fps)` | 透明背景、自動色盤 |
| Atlas JSON | `export_atlas(frames, name)` | 結構見下 |
| Pipeline metadata | `export_metadata()` | prompt、模型、品質、步驟 |

Atlas JSON 結構：

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

### 6.4 cli.py — 命令結構

```bash
sprite-kit generate  --prompt --template --frames --layout --size --quality --output
sprite-kit process   --input --layout --chroma-key --fuzz --anchor --output
sprite-kit export    --input --format --fps --columns --output
sprite-kit pipeline  --prompt --template --frames --layout --format --output
```

> `batch` 命令屬於 Phase 2，本 sprint 不實作。

## 7. Prompt 模板規格

### 7.1 base.yaml

所有模板繼承的基礎結構：

```yaml
version: 1
base:
  background: "Solid #FF00FF magenta background."
  consistency: "Consistent character proportions and pixel scale across all frames."
  margin: "Each frame must fit fully inside its cell with clear margin on all sides."
  separation: "No overlap between frames. Clear visual separation."

variables:
  subject: ""
  action: ""
  frame_count: 3
  layout: "1x3"
  view: "side-view"
```

### 7.2 四個內建模板

| 模板 | 風格關鍵字 | resize 方式 | 額外設定 |
|------|-----------|-------------|---------|
| `pixel_art` | 16-bit SNES、32-color palette、blocky、JRPG | nearest（target_scale 0.5） | — |
| `brutalism` | 水泥紋理、幾何造型、黑/白/銹橘三色、無漸層 | lanczos | size 1024×1024 |
| `retro_futurism` | 80s、chrome + 霓虹、CRT 掃描線、Tron / Blade Runner | lanczos | — |
| `tech_futurism` | 全息粒子、電弧、HUD、藍核紫邊 glow | lanczos | chroma_fuzz=20 |

詳細 YAML 內容見 `docs/00-source-spec.md` 第 5 節。

## 8. 邊界案例

| 案例 | 預期行為 |
|------|---------|
| `OPENAI_API_KEY` 未設定 | 明確錯誤訊息，提示如何設定 |
| API 回傳非 PNG / 截斷 | 拋出明確例外，不靜默繼續 |
| `--layout 1x3` 但圖實際只能切出 2 幀有效內容 | QC 報告標記空白幀，使用者可選擇繼續或停止 |
| 模板檔不存在 | 列出可用模板清單 |
| `--output` 目錄已存在檔案 | 預設詢問或加數字後綴（待 ADR-3 決定） |
| 透明圖再過一次 chroma key | 不破壞既有 alpha，no-op |
| 發光效果（tech_futurism）邊緣洋紅殘留 | 模板自動套用 `chroma_fuzz=20` |

## 9. ADR

### ADR-1：色鍵顏色固定為 `#FF00FF` 洋紅

- **背景**：洋紅在多數美術內容裡極少出現，去背容差高
- **決定**：MVP 預設 `#FF00FF`，但 `chroma_key_remove()` 仍接受參數可改其他顏色
- **影響**：所有內建模板都附加 `Solid #FF00FF magenta background.` 指令

### ADR-2：使用 Pillow + numpy，不引入 OpenCV

- **背景**：OpenCV 安裝體積大、跨平台 wheel 議題多
- **決定**：MVP 用 Pillow + numpy 完成所有像素處理
- **代價**：部分進階功能（自動 grid 偵測）實作會較繁瑣，但仍可行

### ADR-3：輸出檔衝突處理

- **狀態**：待決定
- **選項**：覆寫 / 詢問 / 自動加後綴 / `--force` flag
- **預設傾向**：自動加後綴 + `--force` 覆寫

### ADR-4：Lint / Format 與套件管理工具

- **狀態**：待決定
- **建議**：`ruff` + `ruff format`，套件管理用 `uv`（依 AGENTS.md 工具偏好）
- **確認方式**：在 `/ddd.tasks` 階段定下，否則 `tasks.md` 無法精確列出開發環境設置任務

## 10. 測試策略

- 用 `tests/fixtures/sample_sheet.png`（手動製作的 1×3 帶 #FF00FF 背景簡單圖）做 process / export 的單元測試
- `generate.py` 用 `unittest.mock` mock OpenAI client，不實際呼叫 API
- 整合測試（真的呼叫 API）標記為 `@pytest.mark.integration`，CI 預設不跑，本地用 `pytest -m integration` 觸發

## 11. 變更記錄

| 日期 | 變更 | 來源 |
|------|------|------|
| 2026-05-04 | 初版，從 `docs/00-source-spec.md` 切分 | 使用者提供原始規格書 |
