# Sprite Kit

獨立的 2D 遊戲素材生成與後處理工具包：用 OpenAI Image API 產出 sprite sheet，再用本地 Python 管線輸出透明 PNG / GIF / atlas JSON。詳細目標見 `docs/PRD.md`，技術棧見 `docs/TECHSTACK.md`。

---

## Part 1 — 開發本專案的 Claude Code 看這裡（DDD Workflow）

本專案採用 **DDD（Document Driven Development）工作流**進行開發。

### 工作流入口

所有開發行為（規格、任務拆解、實作、Review）都遵循 `.claude/references/AGENTS.md`。請在開始任何工作前先閱讀該檔案。

核心原則摘要：

- **SSOT**：每個需求對應一個 `docs/<編號>-<名稱>/` 文件包
- **No Code Without Docs**：`spec.md` 與 `tasks.md` 獲使用者確認前，禁止寫程式碼
- **No Code Without Tests**：修改 production code 前必須先有測試
- **Sync on Finish**：完成任務前先更新 `tasks.md` 與 `works.md`
- **Show Must Go On**：每次回合結束時用 Question Tool 提供 2–4 個下一步選項

### 角色

Main agent = **Coordinator**：負責規劃、派工、驗收，不寫 production code、不 debug、不做 review。

- 實作交給 `ddd-developer` subagent
- Code review 交給 `ddd-reviewer` subagent

### 可用 Slash Commands

主流程：

| 指令 | 用途 |
|------|------|
| `/ddd.plan` | 需求模糊時釐清方向 |
| `/ddd.spec` | 撰寫正式規格書 |
| `/ddd.tasks` | 拆解 milestone + task |
| `/ddd.work` | TDD 循環實作 |
| `/ddd.xreview` | 多模型 cross review |

輔助：

| 指令 | 用途 |
|------|------|
| `/ddd.architect-refactor` | 架構層級重構 |
| `/ddd.agent-browser` | 瀏覽器自動化除錯 |
| `/ddd.brainstorming` | 需求發想 |
| `/ddd.create-hooks` | 設定 Claude Code hooks |
| `/ddd.e2e` | E2E 測試（在 main agent 執行） |

### 文件結構

```
docs/
├── PRD.md                # 產品需求（專案層級）
├── TECHSTACK.md          # 技術棧 + 整合方式
├── 00-source-spec.md     # 原始規格書備份（使用者初始輸入）
└── <編號>-<名稱>/         # Sprint 文件包
    ├── plan.md           # (optional) 前置規劃
    ├── research.md       # (optional) 技術調研
    ├── spec.md           # 規格：User Story、驗收條件、ADR
    ├── tasks.md          # Milestone + task checklist
    └── works.md          # 開發日誌
```

### Workflow 來源

DDD Workflow plugin 來自 https://github.com/applepig/ddd-workflow （MIT），檔案位於 `.claude/`。

---

## Part 2 — 把 sprite-kit 整合進別的專案的 Claude Code 看這裡（使用指引）

> ⚠️ 以下指引描述 **完成後** 的使用方式。MVP 尚未實作，目前指令還不可用。
> 進度追蹤見 `docs/01-mvp-core/tasks.md`。

### 環境設定

確保 `OPENAI_API_KEY` 環境變數已設定。完整環境變數列表見 `docs/TECHSTACK.md` 第 3 節。

### 生成素材

```bash
python -m sprite_kit.cli generate --prompt "描述" --template pixel_art --output ./output/
```

### 僅後處理已有圖片

```bash
python -m sprite_kit.cli process --input raw.png --layout 1x4 --output ./output/
```

### 批次生成（省 50% 費用，Phase 2 提供）

```bash
python -m sprite_kit.cli batch --input requests.yaml --output ./output/
```

### 可用模板

- `pixel_art`：像素風（16-bit, SNES 風格）
- `brutalism`：粗獷主義（水泥質感、幾何造型）
- `retro_futurism`：復古未來主義（80s, Tron / Blade Runner）
- `tech_futurism`：科技未來風（全息、電弧、能量環）

### 整合方式

此工具設計為可作為 git submodule、pip install 或直接 CLI 呼叫引入任何專案。詳細指令見 `docs/TECHSTACK.md` 第 5 節。
