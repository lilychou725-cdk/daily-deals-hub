# Caffeine.ai 每日羊毛新闻看板建站 Prompt（省积分两轮模板）

> 使用方法：先发「第一轮」，确认 Caffeine 复述的页面结构和数据 Schema 完全无误后，再发「第二轮」一次性生成完整应用。
> 通过 `caffeine chat send` 或网页对话发送均可。

---

## 第一轮：需求对齐（不写代码、不扣构建积分）

```text
我们现在只做需求梳理和架构确认（Brainstorming），在我明确回复“开始构建”之前，不要写任何代码，也不要生成草稿。

我要创建一个中文界面的「每日羊毛新闻看板（Daily Deals Hub）」，用于个人日常追踪 AI 免费额度、软件限免、黑五促销和生活优惠。请严格按以下数据结构与功能规划：

1. 外部数据源对接（含优雅降级）：
   - 默认数据源 URL：https://raw.githubusercontent.com/lilychou725-cdk/daily-deals-hub/main/data/deals.json
   - 在页面顶部或设置弹窗中支持：查看/修改外部 JSON URL（持久化在 localStorage）、一键手动刷新、显示最近更新时间（updatedAt）与各来源抓取状态（sources）。
   - 如果外部请求失败或超时，自动优雅回退到内置的 8 条真实感中文示例数据（涵盖 4 个分类，含 pinned 置顶和即将到期示例），并在页面给出轻提示而非报错崩溃。
   - 严格兼容如下 JSON Schema：
     顶层：{ "schemaVersion": "1.0", "updatedAt": "ISO-8601", "total": number, "sources": [{ "id": string, "name": string, "ok": boolean, "count": number, "error": string | null }], "deals": Deal[] }
     Deal：{ "id": string, "title": string, "category": "AI会员与额度" | "软件与云服务" | "黑五与促销" | "生活与工具", "summary": string, "couponCode": string | null, "url": string, "source": string, "tags": string[], "worth": string | null, "status": "active" | "expired", "pinned": boolean, "publishedAt": "ISO-8601", "expiresAt": "ISO-8601" | null }

2. 看板展示与筛选能力：
   - 顶部统计概览卡：今日/总有效条数、置顶精选数、24 小时内即将到期数、我的待退订提醒数。
   - 筛选与排序：支持按 4 个固定分类切换（全部 / AI会员与额度 / 软件与云服务 / 黑五与促销 / 生活与工具）、按门槛标签筛选（如 免绑卡 / 需绑卡记得取消 / 免费白嫖 / 限量 / 仅新用户 / 黑五特惠）、“仅看有效”、“隐藏已薅”开关、关键词搜索（搜标题/摘要/来源/优惠码）、排序（默认置顶优先最新 / 即将到期优先）。
   - 单条卡片字段：置顶角标（pinned）、分类徽章、价值标注（worth）、标题、简明攻略（summary）、来源与相对发布时间、截止倒计时（expiresAt，已过期自动置灰并折叠到列表末尾或支持切换隐藏）、门槛标签、优惠码（带一键复制按钮与复制成功提示）、直达链接（新标签页打开）。
   - 简易本地补录：提供一个“快速新增一条羊毛”弹窗（存入 localStorage 自定义列表并与远程 feed 合并展示），方便临时手动记录。

3. 个人「已薅清单 + 防反薅（退订）提醒」（全部存 localStorage）：
   - 每张卡片提供「标记已领」和「收藏」按钮。
   - 点击「标记已领」时弹出轻量表单，可填写：使用账号备注（例如：主力号 / 体验号2 / 邮箱前缀）、退订提醒日期（可选，默认可快捷选 +25 天或自定义日期）、补充笔记。
   - 独立 Tab 页「我的已薅 / 退订提醒」：按退订提醒日期升序排列，距离提醒日 <= 3 天或已超期自动标红警示，支持标记“已取消续订/已完结”。
   - 资产备份与日历导出：支持一键导出/导入个人已薅与配置 JSON 备份；针对有退订提醒日期的条目，支持一键下载标准 `.ics` 日历文件（包含提醒事件与账号备注），可直接导入系统日历或 Google Calendar。

4. 视觉与交互风格：
   - 支持深色/浅色双主题切换（默认极客深色高对比护眼风格）。
   - 高信息密度极客卡片网格（PC 端 2~3 列自适应，手机端单列紧凑布局），无多余营销废话，交互响应迅速。

请先向我复述你的页面结构、状态管理方案、JSON 字段兼容细节和 UI 布局，等待我的“开始构建”指令。
```

---

## 第二轮：一次性生成构建（确认上一轮无遗漏后发送）

```text
方案确认无误，请一次性完整构建上述「每日羊毛新闻看板（Daily Deals Hub）」的所有页面、组件与交互逻辑。

额外交付检查要求：
1. 外部拉取 https://raw.githubusercontent.com/lilychou725-cdk/daily-deals-hub/main/data/deals.json 时禁止写死硬编码 CORS 代理失败就白屏，务必在 fetch 异常时无缝回退到本地示例数据，并在头部保留“切换本地示例 / 重新拉取远程数据”的开关。
2. 优惠码一键复制、JSON 备份导出/导入、`.ics` 日历文件生成与下载必须在浏览器端纯前端闭环可用，不能只做假按钮。
3. 支持在未配置后端数据时也完全独立运行，便于后续导出源码后直接部署到 Cloudflare Pages / Vercel / GitHub Pages。

开始构建。
```

---

## 迭代增量：新增独立「AI 前沿源头」Tab（方案 B，单轮直接构建）

```text
请基于现有的「每日羊毛新闻看板」进行一次增量迭代，严格保持原有功能不变，并在顶部导航新增第 3 个独立 Tab「AI 前沿源头」（无需再次确认，直接修改代码并重新构建部署草稿）。

一、严格保留原有功能（不要改动或污染）
1. 原有的「羊毛看板」Tab、「我的已薅 / 退订提醒」Tab、4 个固定羊毛分类、deals.json 远程拉取与本地回退、快速新增、标记已领/退订提醒、JSON 备份、.ics 日历导出、深浅色主题全部原样保留。
2. 绝对不要把 AI 新闻或论文混进「羊毛看板」的 deals 列表中。

二、「AI 前沿源头」Tab 独立数据源（含优雅降级）
1. 默认远程 JSON URL：https://raw.githubusercontent.com/lilychou725-cdk/daily-deals-hub/main/data/ai_radar.json
2. 在原有设置弹窗中新增一个「AI 前沿源头 JSON URL」输入框（持久化到 localStorage，支持重置回默认地址）。
3. Tab 顶部显示该数据源的最近更新时间（updatedAt）、各来源抓取状态徽章（sources）与「手动刷新」按钮；若 fetch 失败或超时，自动优雅回退到内置的示例数据（含 4 张基准入口卡 + 4 条资讯/论文示例）并给出轻提示，绝不白屏。
4. 严格兼容以下 JSON Schema：
   顶层：{ "schemaVersion": "1.0", "updatedAt": "ISO-8601", "total": number, "sources": [{ "id": string, "name": string, "ok": boolean, "count": number, "error": string | null }], "benchmarks": BenchmarkTool[], "items": RadarItem[] }
   BenchmarkTool：{ "id": string, "name": string, "category": string, "description": string, "url": string, "mirrorUrl": string | null, "mirrorLabel": string | null, "tags": string[] }
   RadarItem：{ "id": string, "section": "briefings" | "papers", "sourceId": "ai_news" | "the_batch" | "hf_papers" | "arxiv_ai", "sourceName": string, "title": string, "summary": string, "url": string, "arxivId": string | null, "arxivUrl": string | null, "alphaXivUrl": string | null, "githubUrl": string | null, "upvotes": number | null, "readTime": string | null, "tags": string[], "publishedAt": "ISO-8601" }

三、「AI 前沿源头」Tab 页面结构与交互（沿用当前极客高对比深/浅色卡片风格）
1. 顶部常驻区「模型评测与源头入口」：
   - 以 PC 端 2×2 / 4 列、手机端单列紧凑网格展示 benchmarks（LMArena、Artificial Analysis、alphaXiv、arXiv cs.AI）。
   - 每张卡片展示：分类徽章、名称、简介、标签、主直达按钮（新标签页打开 `url`）；若 `mirrorUrl` 非空，额外显示次级跳转按钮（文案用 `mirrorLabel`）。
2. 筛选与搜索栏：
   - 板块切换：全部 / 日报与周报（briefings）/ 热门论文（papers）
   - 来源筛选：全部 / AI News / The Batch / HF Papers / arXiv cs.AI
   - 关键词搜索（匹配 title / summary / tags / arxivId）
   - 「仅看已收藏」开关（AI 前沿收藏列表单独存 localStorage，不与羊毛已薅清单混淆）
3. 信息流卡片网格（PC 端 2~3 列自适应，手机端单列）：
   - 日报/周报（briefings）卡片：显示来源徽章、相对与精确时间、readTime（如有）、标题、摘要、标签、收藏按钮、直达原文按钮。
   - 论文（papers）卡片：显示来源徽章、点赞数徽章（upvotes 非空时显示，如 `👍 32`）、arxivId 徽章、标题、摘要、标签、收藏按钮，以及底部的快捷按钮组：主链接（url）、`arXiv 原文`（arxivUrl）、`alphaXiv 讨论区`（alphaXivUrl）、`GitHub 代码`（githubUrl 非空时显示）。

请直接完成编码、构建并部署新的草稿。
```
