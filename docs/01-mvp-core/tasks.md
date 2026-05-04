# Tasks: 01-mvp-core

> Sprint：Sprite Kit 核心 MVP（Phase 1）
> 對應規格：`docs/01-mvp-core/spec.md`
> 拆解原則：TDD（Red → Green）、平行可派發、每個 milestone 可獨立交付驗證

---

## Milestone 1: 專案骨架與設定基礎（序列）

> **預期結果**：repo 可 `uv pip install -e .` 安裝；`pytest` 能執行；lint/format 命令可用；`config.load_config()` 能依優先順序載入設定。
> **驗證方式**：`uv run pytest tests/test_config.py -v` 全過 + `ruff check .` 無錯誤
> **涵蓋 AC**：AC-7（設定優先順序），鋪路給後續 milestone

- [x] **Task 1.1**：定下 ADR-3（輸出檔衝突）與 ADR-4（lint / format / package manager）— 更新 `spec.md` 與 `works.md` 記錄決策
- [x] **Task 1.2**：建立 `pyproject.toml`（依 ADR-4 結果使用 uv + ruff）+ `requirements.txt` 後備 + `setup.py`（pip install 相容）
- [x] **Task 1.3**：建立 `sprite_kit/` 套件骨架（空模組檔 + `__init__.py` 註冊公開 API）+ `tests/` 目錄結構 + `tests/__init__.py`
- [x] **Task 1.4**：建立 `.env.example`（列出 spec 第 6.1 節環境變數）+ 補強 `.gitignore`（venv、`*.egg-info`、output、cache）
- [x] **Task 1.5**：撰寫 `tests/test_config.py`（CLI 參數 > env > .env > default 優先順序、缺 `OPENAI_API_KEY` 錯誤訊息）(Red)
- [x] **Task 1.6**：實作 `sprite_kit/config.py` 通過 Task 1.5 測試 (Green)

---

## Milestone 2: 核心模組（平行 A / B / C）

> **預期結果**：process、export、generate 三個模組獨立可用、各自有測試覆蓋；4 個 prompt 模板載入無誤。
> **介面契約**：已在 `spec.md` 第 5.2、6.1–6.3、7 節定義，平行工作線可獨立開發不衝突。
> **涵蓋 AC**：AC-2、AC-3、AC-4、AC-5、AC-6（部分）

### 🔀 可平行工作線

**[A] process.py — 後處理管線** — `isolation: worktree`

> **範圍**：`sprite_kit/process.py`、`tests/test_process.py`、`tests/fixtures/sample_sheet.png`
> **依賴**：M1 完成（package 骨架、Pillow / numpy 已安裝）
> **介面契約**：`spec.md` 第 6.2 節 — 6 個函式 `chroma_key_remove(img, chroma, fuzz) -> RGBA`、`despill(img) -> RGBA`、`split_frames(img, rows, cols) -> list[RGBA]`、`align_frames(frames, anchor) -> list[RGBA]`、`resize(img, scale, size, method) -> RGBA`、`qc_check(frames) -> dict`
> **驗證方式**：`uv run pytest tests/test_process.py -v` 全過
> **涵蓋 AC**：AC-2、AC-3

- [x] **Task 2.A.1**：製作 `tests/fixtures/sample_sheet.png`（1×3 grid、#FF00FF 背景、簡單形狀，可重現）
- [x] **Task 2.A.2**：撰寫 `chroma_key_remove` + `despill` 測試（背景消除、邊緣 alpha、despill 後無洋紅暈）(Red)
- [x] **Task 2.A.3**：實作 `chroma_key_remove` + `despill` (Green)
- [x] **Task 2.A.4**：撰寫 `split_frames` + `align_frames` 測試（rows×cols 切割、anchor 對齊、AC-3 腳底 y 一致誤差 ≤ 1px）(Red)
- [x] **Task 2.A.5**：實作 `split_frames` + `align_frames` (Green)
- [x] **Task 2.A.6**：撰寫 `resize` + `qc_check` 測試（nearest vs lanczos、空白幀偵測、尺寸一致性）(Red)
- [x] **Task 2.A.7**：實作 `resize` + `qc_check` (Green)

**[B] export.py — 匯出管線** — `isolation: worktree`

> **範圍**：`sprite_kit/export.py`、`tests/test_export.py`
> **依賴**：M1 完成（package 骨架、Pillow 已安裝）
> **介面契約**：`spec.md` 第 6.3 節 — 5 個函式 `export_frames(frames, output_dir)`、`export_sheet(frames, columns, output)`、`export_gif(frames, output, fps)`、`export_atlas(frames, name, output)`、`export_metadata(meta, output)`
> **驗證方式**：`uv run pytest tests/test_export.py -v` 全過
> **涵蓋 AC**：AC-4

- [x] **Task 2.B.1**：撰寫 `export_frames` + `export_sheet` 測試（檔名 `frame_001.png` 序號補零、sheet 透明背景、columns 對齊）(Red)
- [x] **Task 2.B.2**：實作 `export_frames` + `export_sheet` (Green)
- [x] **Task 2.B.3**：撰寫 `export_gif` 測試（透明背景、FPS 與參數一致、可被 PIL 重新讀取驗證幀數）(Red)
- [x] **Task 2.B.4**：實作 `export_gif` (Green)
- [x] **Task 2.B.5**：撰寫 `export_atlas` + `export_metadata` 測試（JSON schema 符合 spec 第 6.3 節範例、可被 `json.loads` 解析）(Red)
- [x] **Task 2.B.6**：實作 `export_atlas` + `export_metadata` (Green)

**[C] generate.py + templates — 生成與 prompt 模板** — `isolation: worktree`

> **範圍**：`sprite_kit/generate.py`、`tests/test_generate.py`、`templates/base.yaml`、`templates/pixel_art.yaml`、`templates/brutalism.yaml`、`templates/retro_futurism.yaml`、`templates/tech_futurism.yaml`、`templates/custom.yaml.example`
> **依賴**：M1 完成（config.py 可讀 `OPENAI_API_KEY`）
> **介面契約**：`spec.md` 第 6.1、7 節 — `generate_sprite(prompt, template, frames, layout, size, quality) -> (raw_png_bytes, used_prompt, metadata_dict)`；模板透過 `extends: base` 繼承基礎結構
> **驗證方式**：`uv run pytest tests/test_generate.py -v` 全過（OpenAI client 用 `unittest.mock`）
> **涵蓋 AC**：AC-5、AC-7（部分）

- [x] **Task 2.C.1**：撰寫模板載入器測試（base.yaml 解析、extends 繼承、自訂模板從 `templates/` 載入）(Red)
- [x] **Task 2.C.2**：實作模板載入器 + 撰寫 `base.yaml` 與 4 個內建模板 YAML（依 spec 第 7.2 節規格）(Green)
- [x] **Task 2.C.3**：撰寫 prompt 組裝測試（自動附加色鍵背景、幀一致性指令、模板 style_keywords 注入）(Red)
- [x] **Task 2.C.4**：實作 prompt 組裝邏輯 (Green)
- [x] **Task 2.C.5**：撰寫 `generate_sprite` 測試（mock OpenAI client、回傳 tuple 結構、缺 API key 錯誤訊息）(Red)
- [x] **Task 2.C.6**：實作 `generate_sprite` (Green)

---

## Milestone 3: CLI 整合與 pipeline（序列、依賴 M2）

> **預期結果**：4 個 CLI 子命令可用；`sprite-kit pipeline` 能從 prompt 串接到匯出；至少一個畫風模板用真實 API 跑通 smoke test。
> **驗證方式**：`uv run pytest tests/test_cli.py tests/integration/ -v` 全過 + 手動 `sprite-kit pipeline` smoke test
> **涵蓋 AC**：AC-1、AC-6、AC-8（最終確認）、AC-7（最終確認）

### 🔗 匯合點

- [x] **Task 3.1**：撰寫 `tests/test_cli.py`（argparse 子命令分派、`--help` 可用、缺必要參數錯誤訊息）(Red)
- [x] **Task 3.2**：實作 `sprite_kit/cli.py` — `generate` / `process` / `export` / `pipeline` 4 個子命令分派 (Green)
- [x] **Task 3.3**：撰寫 `tests/integration/test_pipeline.py`（mock generate、串接真實 process + export，驗證 fire-mage smoke 案例端到端可跑）(Red)
- [x] **Task 3.4**：實作 `pipeline` 串接邏輯 (Green)
- [x] **Task 3.5**：補 `sprite_kit/utils.py`（共用工具：檔名序號、輸出目錄處理、log helper）+ 對應測試
- [x] **Task 3.6**：撰寫 `README.md`（英文總覽 + 5 種整合方式）+ `README.zh-TW.md`（繁中對照）
- [x] **Task 3.7（部分）**：在 `tests/integration/test_pipeline.py` 寫好 `@pytest.mark.integration` 真實 API 測試骨架（4 模板各 1 次）— 標記 + 結構就位，使用者本地手動跑 `pytest -m integration` 觸發
- [x] **Task 3.8**：更新 `tasks.md`（勾選完成項）+ `works.md`（記錄各 milestone 決策與遇到的問題）

---

## Post-review Hardening（cross review 後修正、序列）

> **背景**：`/ddd.xreview` 派 opus + haiku reviewer 平行審查 c312626..d02809a，找出 9 條 findings（3 Critical + 3 Important + 3 Nice-to-have），coordinator 全驗證為真、無 false positive。使用者決定全部修。
> **預期結果**：spec §8 邊界承諾、AC-7 設定優先順序、AC-2 透明圖 no-op 全部到位；CLI 對所有壞輸入給友善訊息；模板 `post_process` 區塊真的被生產 code 讀取。
> **驗證方式**：`uv run pytest tests/ -v` 全綠 + `ruff check .` 無錯誤 + 手動 `SPRITE_KIT_OUTPUT_DIR=/tmp/foo sprite-kit generate --prompt "..."` 行為驗證
> **涵蓋 AC**：AC-2、AC-5、AC-7（補強）

### 🔗 修正清單

- [ ] **Fix F1**：`run_pipeline()` 載入模板後讀 `post_process.chroma_fuzz` / `resize_method` / `target_scale`，套用到 process / resize 步驟。優先順序：CLI flag > template post_process > config default。補測試：`tech_futurism` 預設 fuzz=20。
- [ ] **Fix F2**：`chroma_key_remove` 改為「只把符合 chroma 的 alpha 設 0」，保留既有 alpha；補兩條測試（全透明輸入維持 alpha=0、半透明非洋紅輸入 alpha 保留）。
- [ ] **Fix F3+F4**：4 個 subcommand 的 `--output` 改 `default=None`、handler 在 None 時查 `cfg["output_dir"]`；同樣處理 process 的 `--fuzz` 與 `--chroma-key`。確保 argparse default 不會蓋過環境變數。
- [ ] **Fix F5**：`main()` 加 `except (OSError, yaml.YAMLError)` → 印 `Error: <msg>` 不印 traceback；補測試（0-byte PNG 輸入應 rc=1 且 stderr 無 "Traceback"）。
- [ ] **Fix F6**：`_cmd_process` 對齊後跑 `qc_check`、`log.warning` 印 issues；考慮寫 `process_meta.json`。補測試。
- [ ] **Fix F7**：`_load_frames_from_input` directory 模式只撈 `frame_*.png`（或加 `--name-prefix`），避免把上輪 sheet 當 frame。
- [ ] **Fix F8**：`generate_sprite` 的 `except Exception` 把 OpenAI SDK 的 `status_code` / `request_id` / 訊息一併包進 `GenerateError`，提升可診斷性。
- [ ] **Fix F9**：`_quantize_for_gif` alpha 二值化前先做 alpha-blend 到中性背景色（或讓使用者用 `--gif-bg-color` 指定），減少半透明邊緣鋸齒；補相容性測試。
- [ ] **Fix F10**：`tests/test_cli.py` 補 CLI 層環境變數優先順序測試（覆蓋 `SPRITE_KIT_OUTPUT_DIR` / `SPRITE_KIT_CHROMA_FUZZ` 等核心 key），守住 F3+F4 修正不回歸。
- [ ] **Fix Docs**：在 `works.md` 加「Post-review Hardening」章節記錄修正內容、驗收結果。


### 1. Spec 覆蓋度

| AC | 對應 Task |
|----|-----------|
| AC-1 CLI 命令完整 | M3 T3.1 / T3.2 / T3.4 |
| AC-2 色鍵去背正確性 | M2 [A] T2.A.2 / T2.A.3 |
| AC-3 幀對齊正確性 | M2 [A] T2.A.4 / T2.A.5 |
| AC-4 匯出格式正確性 | M2 [B] T2.B.1–T2.B.6 |
| AC-5 模板可用性 | M2 [C] T2.C.1 / T2.C.2、M3 T3.7 |
| AC-6 模組化呼叫 | M1 T1.3、M3 T3.2（最終確認） |
| AC-7 設定優先順序 | M1 T1.5 / T1.6、M3 T3.7（最終確認） |
| AC-8 測試覆蓋 | 全 milestone Red task + M3 T3.7 |

✅ 8 條 AC 全部對應到至少一個 task。

### 2. Task 完整性檢查

- ✅ 所有 task 具體（含模組名稱、函式名稱、預期行為）
- ✅ 測試與實作分離（Red / Green 標記）
- ✅ 每個 milestone 有預期結果 + 驗證方式
- ✅ 平行工作線都有上下文卡片（範圍、依賴、介面契約、驗證方式）

### 3. 依賴一致性

- ✅ M1 → M2 線性依賴（package 骨架、config）
- ✅ M2 [A] / [B] / [C] 檔案集合不重疊：
  - [A] `sprite_kit/process.py`、`tests/test_process.py`、`tests/fixtures/sample_sheet.png`
  - [B] `sprite_kit/export.py`、`tests/test_export.py`
  - [C] `sprite_kit/generate.py`、`tests/test_generate.py`、`templates/*.yaml`
  - 共用點：`sprite_kit/__init__.py`（M1 已預先建立空骨架）
- ✅ 介面契約全部在 spec.md 已寫死（第 5.2、6.1–6.3、7 節），分線前不需再協調
- ✅ M3 匯合點有整合測試（T3.3）驗證 process + export 串接

### 4. 風險前置

- ✅ ADR 決策（Task 1.1）放在最前，避免後續返工
- ✅ M2 [C] generate.py 涉及 OpenAI API（技術風險最高）已平行起跑，不會卡到 [A][B]
- ✅ Smoke test（T3.7）放在最後，但本身是可選驗證，不會阻擋 MVP 完成

---

## 變更記錄

| 日期 | 變更 | 來源 |
|------|------|------|
| 2026-05-04 | 初版 | `/ddd.tasks` 依 spec.md 拆解 |
