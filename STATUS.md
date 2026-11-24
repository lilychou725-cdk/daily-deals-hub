# 项目进度状态（STATUS）

最后更新：2026-11-24

## 在线资源与项目信息

- **GitHub 公开仓库**：https://github.com/lilychou725-cdk/daily-deals-hub
- **在线 `deals.json` 数据源**：https://raw.githubusercontent.com/lilychou725-cdk/daily-deals-hub/main/data/deals.json （已升级为高纯度 6 源共 84 条）
- **GitHub Actions 自动更新**：已启用 `.github/workflows/update-deals.yml`（每天北京时间 08:30 / 20:30 自动抓取并提交变动，支持手动触发）
- **Caffeine 账号**：`lilychou725@gmail.com`
- **Caffeine 项目名称 / ID**：`每日羊毛看板` / `01a20d34-a094-7223-8b33-426208ad235b`（Cloud：`IC Mainnet`）
- **草稿部署状态**：
  - `draftState`：`deployed`（`lastDeployedDraftId: 1`）
  - `draftDomain`：`identical-salmon-9be-draft.caffeine.xyz`
  - **草稿预览链接**：https://identical-salmon-9be-draft.caffeine.xyz/canister-login.html#t=BCkTa0YbjHb8
- **快捷命令行**：
  ```powershell
  # 打开网页聊天/编辑页点 Go Live 正式上线
  caffeine chat open --project-id 01a20d34-a094-7223-8b33-426208ad235b
  # 查看最新项目状态
  caffeine projects show 01a20d34-a094-7223-8b33-426208ad235b
  ```

## 已完成

- [x] **接入 Caffeine 官方 MCP**：在 `C:\Users\程度康\.gemini\config\mcp_config.json` 中增量添加 `caffeine-official`（`https://mcp.caffeine.ai/mcp`），保留原有 `caffeine-main` 及全部配置。
- [x] **数据源高纯度重构（路线 A）**：升级 `scripts/fetch_deals.py`，砍掉日用品/游戏杂谈源，接入 `aihot.news/free-tokens.md`（最多 35 条）、`Awesome-Black-Friday-Cyber-Monday` AI 工具（15 条）与开发/效率工具（12 条）、黑白名单去水后的 `NodeSeek` RSS、以及过滤纯提问贴的 `V2EX /deals` 与 `/free`，实测生成 84 条规范数据（含 20 个有效优惠码）。
- [x] **GitHub Actions 每日定时更新启用**：已补充 `workflow` scope 并推送 `.github/workflows/update-deals.yml`。
- [x] **Caffeine 草稿已部署**：项目 `每日羊毛看板` 已完成云端部署，可直接在网页点击「手动刷新」拉取新版高纯度 `deals.json`，无需改前端代码。

## 关于 Linux.do 的说明

- 实测 `linux.do` 官方 RSS（`/c/welfare/36.rss`）及 `/latest.json` 均受 Cloudflare 防护返回 `403 Forbidden`，且社区核心福利帖依赖登录态，因此未做绕盾或模拟指纹爬取。
- 推荐替代用法：日常在浏览器刷到 Linux.do 神车时，直接点看板「快速新增」记录到本地，或追加到仓库 `data/manual_deals.json` 实现永久置顶。

## 下一步验收

1. 打开草稿链接或在 Caffeine 网页点击「手动刷新」，验证 84 条新版 AI / 黑五羊毛已加载，并手动复测「已薅清单完结标记 / JSON 备份 / `.ics` 导出」及深浅色切换后点击 **`Go Live`** 正式上线。
2. 若想进一步接 **X（Twitter）博主列表**（路线 B），可建立一个公开 X List 并接入 `TwitterAPI.io` 或 `RSS.app` 作为第 7 个源。
3. 体验月到期前 **3~5 天**，在项目菜单执行 **Export to GitHub** 备份源码（React/Vite 前端可直接免费部署至 Cloudflare Pages / Vercel）。
