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

---

## 變更記錄

| 日期 | 變更 |
|------|------|
| 2026-05-04 | 初版；記錄 Task 1.1 的 ADR 決策 |
