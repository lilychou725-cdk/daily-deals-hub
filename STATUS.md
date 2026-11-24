# 项目进度状态（STATUS）

最后更新：2026-11-24

## 已完成

- [x] **接入 Caffeine 官方 MCP**：在 `C:\Users\程度康\.gemini\config\mcp_config.json` 中增量添加 `caffeine-official`（`https://mcp.caffeine.ai/mcp`），保留原有 `caffeine-main` 及全部配置。
- [x] **人工精选数据文件**：创建 `data/manual_deals.json`（预置 2 条置顶示例）。
- [x] **零依赖抓取脚本**：编写 `scripts/fetch_deals.py`（覆盖 6 个公开源 + 清洗分类 + 优惠码提取 + 标签打标 + URL 去重 + 置顶排序）。
- [x] **GitHub Actions 自动刷新**：编写 `.github/workflows/update-deals.yml`（每天北京时间 08:30 / 20:30 自动抓取并提交更新，支持手动触发）。
- [x] **Caffeine 省积分建站 Prompt**：编写 `caffeine_prompts.md`，完整对齐 `data/deals.json` Schema。
- [x] **项目说明文档**：编写 `README.md`（含本地运行、手动置顶和体验月到期零成本迁移指南）。

## 关键决策

- **架构解耦**：不让 Caffeine 后端直接爬取易触发反爬的外部网站；改由 GitHub Actions 免费定时输出 `data/deals.json`，Caffeine 前端纯读取并把个人已薅/退订提醒存本地 `localStorage`（支持 JSON 导出与 `.ics` 日历导出），实现体验月到期后可无痛迁往 Cloudflare Pages / Vercel 永久免费运行。
- **风控保护**：未触碰当前处于 Gmail 风控申诉状态的 `balfoursarpy@gmail.com` 登录态，等待用户切至健康体验号后再建项目。
- **未提前推远端**：按操作规范先初始化本地 Git 仓库，等待用户确认后再执行 `gh repo create` 与 `git push`。

## 待办清单（下一步）

1. **切换健康的 Caffeine 账号**（用户终端操作）：
   ```powershell
   caffeine auth logout
   caffeine auth login
   caffeine auth status
   ```
2. **确认推送 GitHub 公开仓库**（需公开仓库，Caffeine 前端才可免鉴权读取 `raw.githubusercontent.com/.../data/deals.json`）：
   ```powershell
   gh repo create lilychou725-cdk/daily-deals-hub --public --source . --remote origin --push
   ```
3. **用 Caffeine CLI 创建并构建看板项目**：
   - 执行 `caffeine projects create` 获取新项目 ID。
   - 按 `caffeine_prompts.md` 分两轮发送 `caffeine chat send`，盯到 Draft 构建完成并验收上线。
