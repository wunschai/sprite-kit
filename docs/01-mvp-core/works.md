# Works: 01-mvp-core

> Sprint 開發日誌。每完成一個 milestone 補上技術決策、踩到的坑、解法。
> 對應規格：`docs/01-mvp-core/spec.md`、任務：`docs/01-mvp-core/tasks.md`

---

## Milestone 1: 專案骨架與設定基礎

### Task 1.1 — ADR-3 / ADR-4 定案

**日期**：2026-05-04

**ADR-3（輸出檔衝突處理）**

- 決定：預設「自動加數字後綴」，使用者加 `--force` flag 才直接覆寫
- 否決選項：
  - 「直接覆寫」風險過高，CI 重跑時會把上一輪輸出蓋掉
  - 「拋錯讓使用者手動處理」對自動化管線不友善，每次重跑都要手動清目錄
- 影響：`utils.py` 需要一個 `next_available_path(path)` helper；CLI parser 需要 `--force` 全域 flag

**ADR-4（lint / format / package manager）**

- 決定：`ruff check` + `ruff format` + `uv`
- 理由：
  - 符合 `.claude/references/AGENTS.md` 工具偏好（Rust 實作，速度快）
  - `ruff` 一次取代 `black` / `flake8` / `isort` / `pyupgrade`，配置只在 `pyproject.toml` 裡
  - `uv` 提供 lockfile（`uv.lock`）與快速安裝，可同時取代 `pip` 與 `venv`
- 後備：保留 `requirements.txt` + `setup.py`，使用者沒裝 uv 也能 `pip install -e .`

### Tasks 1.2–1.6 — 套件骨架 + config loader

**日期**：2026-05-04
**派發**：`ddd-developer` (Opus, isolation: worktree)

**結果**：15 tests passed、`ruff check` clean、`ruff format --check` clean、`uv pip install -e .` 成功。

**技術決策與細節**

- `config.py` 用 `dotenv_values(path)` 而非 `dotenv.load_dotenv()`，避免汙染 `os.environ`，讓測試可以用 `monkeypatch` 完全隔離。設一條測試 `test_dotenv_does_not_pollute_os_environ` 守住此不變式
- `_resolve` 對普通 config key 用 `is not None` 判斷，但 `_resolve_api_key` 用 truthiness — 故意不對稱：讓 `.env.example` 中的 `OPENAI_API_KEY=`（空字串）被視為「未設定」，使用者 copy 模板不會立刻觸發 `require_api_key` 的錯誤
- `chroma_fuzz` 走 `_INT_KEYS` 白名單做 cast；非整數值會拋 `ConfigError` 帶具體錯誤訊息（含環境變數名與原始值）
- `pyproject.toml` 用 `[project.scripts]` 註冊 `sprite-kit = "sprite_kit.cli:main"`，所以 `cli.py` 必須存在 `main()` 即使是 stub（NotImplementedError）。Milestone 3 會填正式邏輯

**Coordinator 驗收**

於主分支 merge 後親跑（`.venv-coord`）：
- `pytest tests/ -v` → 15 passed
- `ruff check .` → All checks passed
- `ruff format --check .` → 20 files already formatted

**檔案清單**：見 commit `feat(01-mvp-core): scaffold package and implement config loader (M1)`

---

## Milestone 2: 核心模組（平行 [A] / [B] / [C]）

### 派發決策

**日期**：2026-05-04
**模式**：平行（coordinator 派發 3 個 ddd-developer 到獨立 worktree）
**模型**：Opus（Sonnet quota 那天用罄；M1 經驗顯示 Opus 對複雜邏輯較穩）

三條工作線檔案範圍互不重疊，介面契約全部在 spec 第 5.2、6.2、6.3、7 節定義。Worker 被明確禁止動 `__init__.py` — 由 coordinator 在匯合點統一更新公開 API，避免並行 merge conflict。

### Worker 結果

| 工作線 | 函式 / 檔案 | 測試 | Lint |
|--------|-------------|------|------|
| [A] process.py | `chroma_key_remove`, `despill`, `split_frames`, `align_frames`, `resize`, `qc_check` + `tests/fixtures/sample_sheet.png` | 34 passed | clean |
| [B] export.py | `export_frames`, `export_sheet`, `export_gif`, `export_atlas`, `export_metadata` | 38 passed | clean |
| [C] generate.py + templates | `load_template`, `assemble_prompt`, `generate_sprite` + 4 模板 + custom example | 23 passed | clean |

### 合併過程

逐一 merge（每次跑全測試確認沒破壞既有功能）：

1. merge [A] → 49 passed (15 config + 34 process)
2. merge [B] → 87 passed (+38 export)
3. merge [C] → 110 passed (+23 generate)

無 merge conflict — 檔案範圍劃分有效。

### Coordinator 匯合點工作

更新 `sprite_kit/__init__.py`：re-export 三個 worker 模組的所有公開 API（4 個 exception class + 17 個函式），同時保持 AC-6「`from sprite_kit.process import chroma_key_remove` 等直接 module import」可用。

### 技術決策

- **`process.chroma_key_remove`**：用 numpy vectorized RGB Euclidean distance（避免 per-pixel Python loop）；fuzz 百分比換算為 RGB 空間距離閾值
- **`process.align_frames`**：對每幀計算 alpha>0 的 bounding box，找出最大 bbox 作為統一 canvas size；bottom-center 對齊保證 AC-3「腳底 y 一致 ≤ 1px」
- **`export.export_gif`**：透明背景靠 Pillow `quantize` + `disposal=2` + `transparency` index 實現；單色透明（GIF 限制），測試明確標記 10ms-tick 儲存粒度
- **`export.export_atlas`**：MVP 假設水平單列佈局；多列 atlas 由呼叫端組合
- **`generate.load_template`**：支援單層 `extends: base` 繼承，`style.post_process` 用 deep-merge（dict update）；MVP 不支援多層繼承避免複雜化
- **`generate.generate_sprite`**：reuse `config.require_api_key`；測試用 `MagicMock` mock OpenAI client 避免真實 API 呼叫；CLI override > template recommendation > config default 的優先順序
- **ADR-3 延後**：worker 都不處理輸出檔衝突（直接覆寫），M3 補 utils.py 的 `next_available_path` helper 後再決定怎麼包裝

### Coordinator 驗收

於主分支 merge 完成後親跑（`.venv-coord`）：
- `pytest tests/ -v` → **110 passed in 0.66s**
- `ruff check .` → All checks passed
- `ruff format --check .` → 14 files already formatted
- 公開 API smoke test：`from sprite_kit import ...` 與 `from sprite_kit.process import ...` 皆 OK（AC-6）

---

## Milestone 3: CLI 整合 + pipeline + utils + README

### 派發決策

**日期**：2026-05-04
**模式**：序列（單一 ddd-developer worker，依賴 M1+M2 全部已合併）
**模型**：Opus（與 M2 同）

M3 內部 task 之間有強依賴（CLI 需要 utils 的 `next_available_path`、pipeline 需要 CLI dispatch 才能被測），所以不切平行線。Worker 自行依 TDD 順序：3.5 utils → 3.1/3.2 CLI → 3.3/3.4 pipeline → 3.6 README → 3.7 mark integration → 3.8 docs。

### Worker 結果

| 區塊 | 檔案 | 測試數 |
|------|------|--------|
| utils | `sprite_kit/utils.py` + `tests/test_utils.py` | 16 |
| CLI dispatch | `sprite_kit/cli.py` + `tests/test_cli.py` | 17 |
| Integration smoke | `tests/integration/test_pipeline.py`（mock-based 3 + real-API 4） | 3 default + 4 marked |
| README | `README.md`（重寫）+ `README.zh-TW.md`（新增） | — |

合計 M3 新增 **36 測試**：M1 15 + M2 95 + M3 36 = 146 全綠（4 個 `@pytest.mark.integration` 預設 deselected）。

### 技術決策與細節

- **Pipeline 寫在 `cli.py`**：不另開 `sprite_kit/pipeline.py`。MVP 流程簡單（generate → split → chroma+despill → align → qc → export），抽出獨立模組會增加一層導引但無實質好處；`run_pipeline(args, log)` 已從 `__init__.py` re-export，需要時可直接呼叫。
- **ADR-3 包裝層在 cli.py**：`_safe_export_frames()` / `_export_formats()` 分別在每個寫檔點呼叫 `next_available_path()`，避免侵入凍結的 `export.py`。`--force` flag 統一在 dispatch 層攔截。
- **Pytest marker 預設過濾**：在 `pyproject.toml` 的 `[tool.pytest.ini_options]` 加 `addopts = "-m 'not integration'"`，讓 `pytest tests/` 預設跳過真實 API 測試；本地要跑時用 `pytest -m integration`。這是新增 key、不改 M1/M2 既有條目，符合凍結邊界。
- **`fake_api_key` 改 explicit fixture（非 autouse）**：原本 autouse 會把 `OPENAI_API_KEY` 強蓋成 `sk-test-fake`，連帶讓 `pytest -m integration` 也用到假 key；改成 explicit，讓 mocked 測試明確要求 fixture，real-API 測試保留使用者真實環境。
- **Friendly errors**：`main()` catch `ConfigError` / `TemplateError` / `GenerateError` / `FileNotFoundError` / `ValueError` → 印 `Error: <msg>` 單行 + return 1，**不**印 traceback；通過 AC-7 友善錯誤要求。
- **Logger idempotent**：`get_logger` 用 `logger._sprite_kit_configured` 旗標避免重複 attach handler，多次呼叫安全（測試 `test_does_not_duplicate_handlers_when_called_repeatedly` 守住）。
- **Real-API smoke 結構就位但不執行**：`@pytest.mark.integration` parametrize 4 模板各 1 個 test；測試本身會在缺 `OPENAI_API_KEY` 時 `pytest.skip`，避免誤觸真實費用。Coordinator 不在 worker 流程中跑，等使用者手動觸發（spec 第 10 節說明）。

### 遇到的問題

1. **autouse fixture 影響 real-API 測試**：第一次 worker 把 `_api_key` 設成 autouse，導致 `pytest -m integration` 把使用者的真實 key 蓋成 `sk-test-fake`。改成 explicit `fake_api_key` fixture 後 mocked 與 real-API 測試完全隔離。
2. **ruff `I001` import 排序**：`tests/test_utils.py` 與 cli.py 等三檔被 `ruff format` 格式化；用 `ruff check . --fix` + `ruff format .` 一次清掉。
3. **沒踩到 M1/M2 凍結檔案**：唯一 `pyproject.toml` 改動只新增 `addopts` key（無修改既有條目），符合 worker 邊界規範。

### Coordinator 驗收（在 worker worktree 內）

- `pytest tests/ -v` → **146 passed, 4 deselected in 0.64s**
- `ruff check .` → All checks passed
- `ruff format --check .` → 18 files already formatted
- `sprite-kit --help` / `generate|process|export|pipeline --help` → 全部正常列出 usage

---

## 變更記錄

| 日期 | 變更 |
|------|------|
| 2026-05-04 | 初版；記錄 Task 1.1 的 ADR 決策 |
| 2026-05-04 | 補上 Tasks 1.2–1.6 的開發紀錄與 Coordinator 驗收結果 |
| 2026-05-04 | M2 完成：[A]/[B]/[C] 三條工作線平行開發；110 tests 全綠 |
| 2026-05-04 | M3 完成：CLI + pipeline + utils + README + integration test 結構；146 tests 全綠（4 deselected） |
| 2026-05-04 | Post-review Hardening：9 條 cross-review findings 全修；165 tests 全綠（4 deselected） |

---

## Post-review Hardening（2026-05-04）

**背景**：`/ddd.xreview` 平行派 opus + haiku reviewer 審查 c312626..d02809a，找出 9 條 findings（3 Critical + 3 Important + 3 Nice-to-have），coordinator 全驗證為真，使用者授權「全部修」。

**模式**：序列（單一 worker），TDD（每條 finding 先 Red 再 Green）。

### 修正清單

| ID | 嚴重度 | 修正點 | 測試 |
|----|--------|--------|------|
| F1 | Critical | `run_pipeline()` 讀 template `post_process.chroma_fuzz` / `resize_method` / `target_scale`；新增 `_resolve_fuzz()` 套用 CLI > template > config 三層優先順序；`target_scale` 觸發 `resize()` step | `TestPipelineTemplatePostProcess` × 4 |
| F2 | Critical | `chroma_key_remove` 用 `np.minimum(existing, mask)` 保留輸入 alpha；spec §8 idempotent 承諾兌現 | `test_preserves_existing_transparent_pixels` / `test_preserves_partial_alpha_on_non_chroma` / `test_idempotent_on_rgba_input` |
| F3+F4 | Critical | 4 個 subcommand 的 `--output`、process / pipeline 的 `--fuzz` / `--chroma-key` 全部改 `default=None`；4 個 handler 在缺值時查 `cfg`，恢復 AC-7 優先順序 | `TestCliEnvOverrides` × 4 |
| F5 | Important | `main()` 增 `except (yaml.YAMLError, OSError)` → 印 `Error: <msg>` 不噴 traceback；涵蓋 `PIL.UnidentifiedImageError` / 畸形 YAML | `TestFriendlyErrors` × 2 |
| F6 | Important | `_cmd_process` 在對齊後加 `qc_check` + `log.warning`，與 pipeline 對齊 | `test_process_logs_qc_warning_for_blank_frames` |
| F7 | Important | `_load_frames_from_input` directory 模式改 `frame_*.png` glob，避免把 sheet PNG 當 frame | `test_load_frames_skips_non_frame_pngs_in_directory` |
| F8 | Nice | `generate_sprite` 的 except 把 SDK `status_code` / `request_id` 包進 `GenerateError` | `test_generate_sprite_includes_status_code_and_request_id_in_error` / `test_generate_sprite_omits_diagnostic_fields_when_absent` |
| F9 | Nice | `_quantize_for_gif` 在二值化前 blend 到 `bg_color`（預設白）；只有 alpha=0 才透明，半透明邊緣不再鋸齒；`export_gif` 新增 `bg_color` 參數 | `test_only_alpha_zero_pixels_become_transparent` / `test_custom_bg_color_blends_semi_transparent_edges` |
| F10 | Nice | 補 `TestCliEnvOverrides` 4 條 e2e env-var 測試守住 F3+F4 不回歸 | 含於 F3+F4 行 |

### 影響範圍

- `sprite_kit/cli.py`：F1（pipeline 讀 template post_process）、F3+F4（4 default 改 None + handler 端 fallback 至 cfg）、F5（main 多 except）、F6（_cmd_process 加 qc）、F7（glob 改 `frame_*.png`），新增 helper `_resolve_output` / `_resolve_fuzz`
- `sprite_kit/process.py`：F2（`chroma_key_remove` `np.minimum`）
- `sprite_kit/generate.py`：F8（SDK 例外擴充 detail）
- `sprite_kit/export.py`：F9（`_quantize_for_gif` blend + `export_gif` 新增 `bg_color` 參數）
- `tests/test_*.py`：對應 19 條新測試
- `docs/01-mvp-core/tasks.md`：勾選 9 條 fixes
- `docs/01-mvp-core/works.md`：本章節

### 驗收結果

- `pytest tests/ -v` → **165 passed, 4 deselected in 0.95s**（146 baseline + 19 新測試）
- `ruff check .` → All checks passed
- `ruff format --check .` → 18 files already formatted
- `sprite-kit --help` / 4 個 subcommand `--help` → 全部正常列出 usage、`--output` help 文字提到 `$SPRITE_KIT_OUTPUT_DIR` fallback

### 技術決策

- **F1 優先順序明確化**：`_resolve_fuzz()` helper 把「CLI > template post_process > config」寫成單函式，避免散落在 if/else。process subcommand 沒有 template 概念，所以走 `_cmd_process` 的「CLI > config」兩層；pipeline 才走三層。
- **F2 用 `np.minimum`**：保證單調遞減，是 idempotent 的最直觀寫法（`min(existing, 0) = 0` 對 chroma 像素；`min(existing, 255) = existing` 對非 chroma 像素）。原本 RGB 輸入經 `convert("RGBA")` 自帶 alpha=255，與 `min(255, 255) = 255` 不衝突，所以不影響舊測試。
- **F5 例外順序**：`yaml.YAMLError` / `OSError` 放在 `ValueError` 之後維持風格；class 不重疊故順序不影響語意。
- **F7 glob 範圍**：選 `frame_*.png` 與 `export_frames` 的預設 prefix 對齊。需求若日後需要 custom prefix 可再加 flag，目前不擴大 surface。
- **F9 `bg_color` 參數而非 CLI flag**：保持 CLI 簡潔，純函式介面提供給 Python API 使用者；測試用 explicit kwarg 驗證。
- **沒動 `__init__.py` 公開介面**：`export_gif` 新增的 `bg_color` 是 keyword-only 帶 default，向下相容；`load_template` 已 export，cli.py 直接 import 即可。

### 邊界遵守

- 沒動 `sprite_kit/config.py` / `sprite_kit/utils.py` / `templates/*.yaml` / `pyproject.toml` / `requirements.txt` / spec.md / PRD.md / TECHSTACK.md / CLAUDE.md / README*.md / `.claude/`
- 沒新增依賴
- 沒刪除既有測試（F2 修正後原 `test_pure_chroma_pixels_become_transparent` 等仍綠）
