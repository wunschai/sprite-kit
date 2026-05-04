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

## 變更記錄

| 日期 | 變更 |
|------|------|
| 2026-05-04 | 初版；記錄 Task 1.1 的 ADR 決策 |
| 2026-05-04 | 補上 Tasks 1.2–1.6 的開發紀錄與 Coordinator 驗收結果 |
