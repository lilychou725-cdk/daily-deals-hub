# Daily Deals Hub（每日羊毛新闻看板数据源）

自动化聚合公开羊毛、限免与促销线索，清洗去重后输出为标准静态 JSON（`data/deals.json`），供 **Caffeine.ai** 前端看板或任意静态网站直接消费，彻底避免链上爬虫消耗和跨站限制。

## 目录结构

```text
daily-deals-hub/
├── .github/workflows/
│   └── update-deals.yml      # GitHub Actions 每日两次自动抓取并提交更新
├── data/
│   ├── manual_deals.json     # 人工维护置顶精选列表（脚本永不覆盖）
│   └── deals.json            # 自动生成的聚合标准输出（前端直接读取）
├── scripts/
│   └── fetch_deals.py        # 零依赖 Python 3 抓取与清洗脚本
├── caffeine_prompts.md       # Caffeine.ai 两轮省积分建站 Prompt
├── README.md
└── STATUS.md                 # 当前进度与待办记录
```

## 已接入数据源（6 个公开源）

1. **V2EX 优惠信息**（`/deals` API，最新 15 条）
2. **V2EX 免费赠送**（`/free` API，最新 10 条）
3. **GamerPower 限免**（公开 Giveaways API，最新 12 条）
4. **Slickdeals 精选**（首页精选 RSS，最新 12 条）
5. **小众软件**（官网 RSS，最新 8 条）
6. **Hacker News 福利**（Algolia API 检索促销/免费额度/赠送讨论，最新 10 条）

## 本地运行

仅使用 Python 3 标准库，无需安装任何第三方依赖：

```bash
python scripts/fetch_deals.py
```

执行后会刷新 `data/deals.json`，并在终端打印本次条数与成功数据源统计。

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
