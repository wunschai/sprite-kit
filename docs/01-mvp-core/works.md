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

## 變更記錄

| 日期 | 變更 |
|------|------|
| 2026-05-04 | 初版；記錄 Task 1.1 的 ADR 決策 |
| 2026-05-04 | 補上 Tasks 1.2–1.6 的開發紀錄與 Coordinator 驗收結果 |
| 2026-05-04 | M2 完成：[A]/[B]/[C] 三條工作線平行開發；110 tests 全綠 |
