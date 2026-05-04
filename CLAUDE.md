# Sprite Kit

本專案採用 **DDD（Document Driven Development）工作流**進行開發。

## 工作流入口

所有開發行為（規格、任務拆解、實作、Review）都遵循 `.claude/references/AGENTS.md` 定義的規範。請在開始任何工作前先閱讀該檔案。

核心原則摘要：

- **SSOT**：每個需求對應一個 `docs/<編號>-<名稱>/` 文件包
- **No Code Without Docs**：`spec.md` 與 `tasks.md` 獲使用者確認前，禁止寫程式碼
- **No Code Without Tests**：修改 production code 前必須先有測試
- **Sync on Finish**：完成任務前先更新 `tasks.md` 與 `works.md`
- **Show Must Go On**：每次回合結束時用 Question Tool 提供 2–4 個下一步選項

## 角色

Main agent = **Coordinator**：負責規劃、派工、驗收，不寫 production code、不 debug、不做 review。

- 實作交給 `ddd-developer` subagent
- Code review 交給 `ddd-reviewer` subagent

## 可用 Slash Commands

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

## 文件結構

```
docs/
├── PRD.md                # 產品需求（專案層級）
├── TECHSTACK.md          # 技術棧 + 參考連結
└── <編號>-<名稱>/
    ├── plan.md           # (optional) 前置規劃
    ├── research.md       # (optional) 技術調研
    ├── spec.md           # 規格：User Story、驗收條件、ADR
    ├── tasks.md          # Milestone + task checklist
    └── works.md          # 開發日誌
```

## Workflow 來源

DDD Workflow plugin 來自 https://github.com/applepig/ddd-workflow （MIT License），檔案位於 `.claude/`。
