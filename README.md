# Daily Deals Hub（每日羊毛新闻看板数据源）

自动化聚合高纯度 AI 免费额度、黑五开发软件促销与中文技术社区福利，清洗去重后输出为标准静态 JSON（`data/deals.json`），供 **Caffeine.ai** 前端看板或任意静态网站直接消费，彻底避免链上爬虫消耗和跨站限制。

## 目录结构

```text
daily-deals-hub/
├── .github/workflows/
│   └── update-deals.yml      # GitHub Actions 每日两次自动抓取并提交更新
├── workflows_template/
│   └── update-deals.yml      # 工作流模板备份
├── data/
│   ├── manual_deals.json     # 人工维护置顶精选列表（脚本永不覆盖）
│   ├── deals.json            # 自动生成的聚合羊毛标准输出（前端直接读取）
│   └── ai_radar.json         # 自动生成的 AI 前沿源头情报输出（AI 前沿源头 Tab 读取）
├── scripts/
│   ├── fetch_deals.py        # 零依赖 Python 3 羊毛抓取与清洗脚本
│   └── fetch_ai_radar.py     # 零依赖 Python 3 AI 一手前沿源头抓取脚本
├── caffeine_prompts.md       # Caffeine.ai 两轮省积分建站 Prompt
├── README.md
└── STATUS.md                 # 当前进度与项目链接记录
```

## 已接入数据源（6 个高纯度公开源）

1. **AI 免费额度 (aihot)**（`https://aihot.news/free-tokens.md`，每日可领 / 每月可领 / 最新 AI 福利，最多 35 条）
2. **黑五 AI 工具 2026**（`Awesome-Black-Friday-Cyber-Monday` AI Tools 专区，前 15 条，自动提取折扣与优惠码）
3. **黑五开发与效率 2026**（`Awesome-Black-Friday-Cyber-Monday` Developer Tools & Productivity 专区，优先 `⭐` 高折条目，前 12 条）
4. **NodeSeek 精选福利**（官方 RSS + 严格黑白名单过滤二手出机/求助贴，最多 10 条）
5. **V2EX 优惠信息**（`/deals` API，过滤纯提问水贴，最多 10 条）
6. **V2EX 免费赠送**（`/free` API，过滤纯提问水贴，最多 10 条）

> **关于 Linux.do**：社区官方 RSS/JSON 均启用了 Cloudflare 防护（直接抓取返回 403）且核心福利帖需登录态，出于合规与稳定性考虑不做绕盾抓取；在浏览器看到优质神车时，可通过看板「快速新增」或写入 `data/manual_deals.json` 置顶。

## 本地运行

仅使用 Python 3 标准库，无需安装任何第三方依赖：

```bash
python scripts/fetch_deals.py
python scripts/fetch_ai_radar.py
```

执行后会分别刷新 `data/deals.json` 与 `data/ai_radar.json`，并在终端打印本次条数与成功数据源统计。

## 已接入 AI 前沿一手源头（`data/ai_radar.json`）

- **日报与周报（`briefings`）**：AI News（`https://news.smol.ai` → `latent.space` 最新动态）、The Batch（吴恩达团队周报）
- **热门与最新论文（`papers`）**：Hugging Face Daily Papers（按点赞排序 Top 12）、arXiv `cs.AI` 最新预印本（去重后 Top 8），每篇均附带 `arXiv 原文` 与 `alphaXiv 讨论区` 直达链接
- **常驻评测与源头入口（`benchmarks`）**：LMArena（真人盲测）、Artificial Analysis（质量/速度/价格横评）、alphaXiv、arXiv `cs.AI`

## 如何添加置顶精选羊毛

直接编辑 `data/manual_deals.json`（JSON 数组），每条推荐包含：

```json
{
  "id": "manual-example-1",
  "title": "活动标题",
  "category": "AI会员与额度",
  "summary": "一句话领取与避坑说明",
  "couponCode": "PROMO2026",
  "url": "https://example.com",
  "source": "人工精选置顶",
  "tags": ["免绑卡", "免费白嫖"],
  "worth": "免费",
  "status": "active",
  "pinned": true,
  "publishedAt": "2026-11-24T00:00:00Z",
  "expiresAt": null
}
```

每次运行 `scripts/fetch_deals.py` 时，人工条目都会自动合并且置顶显示，不会被抓取流程覆盖。

## 体验月到期后零成本迁移托管指南

1. 体验月到期前 **3~5 天**，在 Caffeine.ai 项目顶部点击项目名称 → **Export to GitHub**，导出完整源码（React/Vite 前端 + Motoko 后端）。
2. 将导出仓库中的前端目录直接部署到 **Cloudflare Pages**、**Vercel** 或 **GitHub Pages**（构建命令通常为 `pnpm build` / `npm run build`，输出目录为 `dist`）。
3. 数据源继续依赖本仓库 GitHub Actions 自动更新的 `https://raw.githubusercontent.com/<your-username>/daily-deals-hub/main/data/deals.json`，个人已薅清单与退订提醒数据保存在浏览器 `localStorage` 并支持随时导出 JSON 备份，实现整套系统 **0 元永久运行**。
