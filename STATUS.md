# 项目进度状态（STATUS）

最后更新：2026-11-24

## 在线资源与项目信息

- **GitHub 公开仓库**：https://github.com/lilychou725-cdk/daily-deals-hub
- **在线 `deals.json` 数据源**：https://raw.githubusercontent.com/lilychou725-cdk/daily-deals-hub/main/data/deals.json （已验证 HTTP 200，共 63 条，6/6 数据源抓取成功）
- **Caffeine 账号**：`lilychou725@gmail.com`
- **Caffeine 项目 ID**：`01a20d34-a094-7223-8b33-426208ad235b`（Cloud：`IC Mainnet` / `alias:mainnet`）
- **当前构建状态（记录时 `2026-11-24T11:12:49Z`）**：
  - 会话状态：`working`（应用代码 10 项 `build.*` 子任务均已 `completed`，云端正处于最终 `verification.qa-review` 自动化测试收尾阶段）
  - `draftState`：`no_draft`
  - `draftUrl`：`null`
  - `draftDomain`：`null`
- **浏览器直达打开项目命令**：
  ```powershell
  caffeine chat open --project-id 01a20d34-a094-7223-8b33-426208ad235b
  ```
- **查看最新草稿链接命令**：
  ```powershell
  caffeine projects show 01a20d34-a094-7223-8b33-426208ad235b
  ```

## 已完成

- [x] **接入 Caffeine 官方 MCP**：在 `C:\Users\程度康\.gemini\config\mcp_config.json` 中增量添加 `caffeine-official`（`https://mcp.caffeine.ai/mcp`），保留原有 `caffeine-main` 及全部配置。
- [x] **人工精选数据文件**：创建 `data/manual_deals.json`（预置 2 条置顶示例）。
- [x] **零依赖抓取脚本**：编写 `scripts/fetch_deals.py`（覆盖 6 个公开源 + 清洗分类 + 优惠码提取 + 标签打标 + URL 去重 + 置顶排序），实测生成 63 条规范数据。
- [x] **公开 GitHub 仓库与在线数据源**：创建并推送 `lilychou725-cdk/daily-deals-hub`（`main` 分支），验证 `raw.githubusercontent.com` 上的 `data/deals.json` 可免鉴权访问。
- [x] **工作流模板备份**：将定时刷新配置保存为仓库中的 `workflows_template/update-deals.yml`（同时本地磁盘保留 `.github/workflows/update-deals.yml`）。
- [x] **Caffeine 项目建项与全栈规格下发**：已用健康账号 `lilychou725@gmail.com` 创建项目 `01a20d34-a094-7223-8b33-426208ad235b` 并下发完整中文看板规格（含远程 JSON 读取、优雅回退、4 分类、已薅清单与退订提醒、`.ics` 与 JSON 备份导出）。
- [x] **文档与建站模板**：编写 `caffeine_prompts.md`、`README.md` 与 `STATUS.md`。

## GitHub Actions 定时抓取说明（需二选一补启用）

由于当前本机 `gh` OAuth Token 仅含 `gist`、`read:org`、`repo` 权限，缺少 GitHub 推送 `.github/workflows/` 所需的 `workflow` scope，因此首次推送时已将工作流从提交历史中剔除，并同时保留了本地 `.github/workflows/update-deals.yml` 与仓库里的 `workflows_template/update-deals.yml`。

任选以下一种方式即可启用每天自动更新：

1. **方式一（终端授权 `workflow` scope 后补推）**：
   ```powershell
   gh auth refresh -h github.com -s workflow
   git add .github/workflows/update-deals.yml
   git commit -m "ci: enable daily deals GitHub Actions schedule"
   git push
   ```
2. **方式二（GitHub 网页直接创建）**：
   打开仓库的 **Actions → New workflow → set up a workflow yourself**，将路径设为 `.github/workflows/update-deals.yml`，把仓库中 `workflows_template/update-deals.yml` 的内容粘贴提交即可。

## 下一步验收

1. 运行 `caffeine projects show 01a20d34-a094-7223-8b33-426208ad235b` 或 `caffeine chat open --project-id 01a20d34-a094-7223-8b33-426208ad235b` 打开网页端查看最终草稿。
2. 在网页端确认「每日羊毛新闻看板」交互、远程 JSON 拉取与 `.ics`/JSON 导出无误后，点击 **`Go Live`** 正式上线。
3. 体验月到期前 **3~5 天**，在项目菜单执行 **Export to GitHub** 备份源码（React/Vite 前端可直接免费部署至 Cloudflare Pages / Vercel）。
