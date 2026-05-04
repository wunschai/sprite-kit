# Sprite Kit — 產品需求文件（PRD）

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

## 2. 設計原則

1. **零耦合**：不綁定任何遊戲引擎、AI agent 框架或特定專案結構
2. **CLI 優先**：所有功能都可透過命令列呼叫，方便整合
3. **模組化**：生成、後處理、匯出三層分離，可獨立使用
4. **可擴展**：prompt 模板和後處理 pipeline 都可自訂

## 3. 目標使用者與情境

- **遊戲開發者**：需要快速產出 prototype 期的 placeholder 美術或量產角色動畫
- **AI agent / 自動化流程**：n8n、Claude Code、shell script 需要程式化的素材產生介面
- **獨立開發者 / 小團隊**：沒有專屬美術，需要可控、可重現的素材生產 pipeline

## 4. 開發階段（Phase 規劃）

> 詳細的模組規格與實作順序在各 sprint 的 `spec.md`。

| Phase | 範圍 | Sprint 文件包 |
|-------|------|--------------|
| 1（MVP） | config / generate / process / export / cli + 4 個模板 | `docs/01-mvp-core/` |
| 2 | Batch API、CLI batch 命令、reference image 支援 | 待開 |
| 3 | MCP Server 封裝、方向性 sprite sheet、atlas 合併 | 待開 |

## 5. 已驗證的測試結果

以下四種畫風已透過 ChatGPT Plus 手動測試，確認 gpt-image-2 可穩定產出，作為 MVP 模板的基準：

1. **像素風** — 角色 idle 動畫（3 幀），角色一致性高，色鍵背景乾淨
2. **粗獷主義** — UI icon set（3×2 grid），水泥質感和幾何造型到位
3. **復古未來主義** — 角色 walk cycle（4 幀），chrome + 霓虹配色佳，幀間動作差異需注意
4. **科技未來風** — 技能特效（charge/fire/dissipate），發光效果邊緣需較高色鍵容差

主要需後處理解決的問題：

- 幀間對齊和比例校正（walk cycle 最明顯）
- 色鍵去背的發光溢出邊緣處理
- 幀間動作差異不足時需重新生成

## 6. 費用估算

基於 gpt-image-2 API，1024×1024 medium quality：

| 場景 | Standard API | Batch API |
|------|-------------|-----------|
| 單張 sprite sheet | $0.053 | $0.027 |
| 一個角色完整素材（8 張） | $0.42 | $0.21 |
| 20 個角色 | $8.48 | $4.24 |
| 探索階段試 30 種風格 | $1.59 | $0.80 |

API key 最低儲值 $5，足夠生成約 90 張中品質 sprite sheet（Standard）或 180 張（Batch）。
