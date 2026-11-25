# 项目进度状态（STATUS）

最后更新：2026-11-26

## 在线资源与项目信息

- **GitHub 公开仓库**：https://github.com/lilychou725-cdk/daily-deals-hub
- **在线 `deals.json` 数据源**：https://raw.githubusercontent.com/lilychou725-cdk/daily-deals-hub/main/data/deals.json （高纯度 6 源）
- **在线 `ai_radar.json` 数据源（AI 前沿源头）**：https://raw.githubusercontent.com/lilychou725-cdk/daily-deals-hub/main/data/ai_radar.json （4/4 源成功，共 32 条情报 + 4 张评测工具卡）
- **GitHub Actions 自动更新**：`.github/workflows/update-deals.yml` 已升级为同时运行 `scripts/fetch_deals.py` 与 `scripts/fetch_ai_radar.py`，每天北京时间 08:30 / 20:30 自动提交 `data/deals.json` 与 `data/ai_radar.json`（云端手动触发验证 run [`45649042900`](https://github.com/lilychou725-cdk/daily-deals-hub/actions/runs/45649042900) 已 `success`）
- **Caffeine 账号**：`lilychou725@gmail.com`
- **Caffeine 项目名称 / ID**：`每日羊毛看板` / `01a20d34-a094-7223-8b33-426208ad235b`（Cloud：`IC Mainnet`）
- **草稿部署状态**：
  - Draft Version 2 已部署（`draftDomain`：`identical-salmon-9be-draft.caffeine.xyz`）
  - **草稿预览链接**：https://identical-salmon-9be-draft.caffeine.xyz/canister-login.html#t=BCkTa0YbjHb8
  - Draft Version 3（对齐 `data/ai_radar.json` Schema 与 4 张基准入口卡 + `briefings/papers` 卡片结构）已在 Caffeine 云端完成修改与编译，处于云端自动化验收收尾阶段（`verifying / testing`），切勿重复发送构建指令。
- **快捷命令行**：
  ```powershell
  # 打开网页聊天/编辑页查看验收结果并点 Go Live 正式上线
  caffeine chat open --project-id 01a20d34-a094-7223-8b33-426208ad235b
  # 查看最新项目状态
  caffeine projects show 01a20d34-a094-7223-8b33-426208ad235b
  ```

## 已完成

- [x] **新增 AI 前沿一手源头抓取脚本 `scripts/fetch_ai_radar.py`**：零第三方依赖，实测 4/4 源全部成功，生成 `data/ai_radar.json`（共 32 条 + 4 张基准入口卡）：
  - `ai_news`（AI News，通过 `https://news.smol.ai/` 重定向至 `latent.space/news/` 抓取最新文章与摘要）：8 条
  - `the_batch`（The Batch，吴恩达团队周报）：4 条
  - `hf_papers`（Hugging Face Daily Papers，按点赞排序 Top 12，自带 `arXiv` / `alphaXiv` / `GitHub` 链接）：12 条
  - `arxiv_ai`（arXiv `cs.AI` 最新预印本，已对 HF Papers 去重，0 重叠）：8 条
  - `benchmarks`（常驻模型评测与源头入口卡）：LMArena、Artificial Analysis、alphaXiv、arXiv `cs.AI` 共 4 张
- [x] **升级 GitHub Actions 与模板**：`.github/workflows/update-deals.yml` 与 `workflows_template/update-deals.yml` 同步运行 `fetch_deals.py` 与 `fetch_ai_radar.py` 并自动推送两份 JSON，云端运行 [`45649042900`](https://github.com/lilychou725-cdk/daily-deals-hub/actions/runs/45649042900) 验证通过。
- [x] **向 Caffeine 发送「AI 前沿源头」增量构建与对齐指令**：保留原有「羊毛看板」与「我的已薅 / 退订提醒」不变，新增第 3 个独立 Tab「AI 前沿源头」并已通过 Node CLI 无截断下发完整 `ai_radar.json` 对齐规范（记录于 `caffeine_prompts.md`）。

## 下一步验收

1. 几分钟后刷新草稿预览页（或运行 `caffeine chat open --project-id 01a20d34-a094-7223-8b33-426208ad235b`），切到第 3 个 Tab「AI 前沿源头」核对：
   - 顶部「模型评测与源头入口」是否展示 LMArena、Artificial Analysis、alphaXiv、arXiv cs.AI 共 4 张卡片；
   - 下方信息流是否已加载 32 条实时数据（日报/周报 + 论文，论文卡片含 `arXiv 原文` 与 `alphaXiv 讨论区` 按钮）；
   - 原有「羊毛看板」和「我的已薅 / 退订提醒」功能无回归问题后，点击 **`Go Live`** 正式上线。
2. 体验月到期前 **3~5 天**，在项目菜单执行 **Export to GitHub** 备份源码（React/Vite 前端可直接免费部署至 Cloudflare Pages / Vercel）。
