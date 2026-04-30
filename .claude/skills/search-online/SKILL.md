---
name: search-online
description: 统一网络搜索入口。使用 brave_web_search 搜索，用 brave_llm_context 提取高价值长文全文。由 stock-research、stock-fetch 等技能在需要搜索时内部调用。
---

# 在线搜索技能

## 核心定位

**本技能是项目所有在线搜索工作的唯一入口。** 任何需要从互联网获取信息的场景，都应通过本技能而非直接调用 MCP 搜索工具。

- 负责：执行搜索、按 L1-L7 筛选来源、将高价值长文提取归档
- 不负责：数据分析、投资判断（由调用方处理）

## 触发方式

本技能由其他技能内部调用，也可由用户直接触发：

- `stock-research` → 分析过程中需要搜索补充信息时调用本技能
- `stock-fetch` → 搜集过程中需要查找特定数据来源时调用本技能
- `knowledge-index` → 入库时需要搜索来源信息验证可信度时调用本技能
- 用户直接要求搜索、查找在线信息时触发

## 搜索工具

| 工具 | 用途 | 说明 |
|------|------|------|
| `brave_web_search` | **所有搜索查询** | 返回链接+标题+摘要列表。必须使用 `search_lang` 参数：中文查询用 `zh`，英文查询用 `en`。Agent 自行按 L1-L7 筛选可信度、发现意外角度 |
| `brave_llm_context` | **已知 URL 的全文提取** | 对高价值页面（研报、官方公告、长文）提取 LLM 优化的清洁正文 |
| `brave_rich_search` | **实时结构化数据** | 股价/汇率/天气等，需配合 `brave_web_search` 的 callback_key 使用 |
| `brave_local_search` | **本地商业/地点搜索** | 特定地点商家、服务查询 |

## 搜索决策：两步走

```
提出信息需求
│
├── 你知道具体 URL？
│   └── 是 → brave_llm_context（提取该页面全文）
│
├── 你需要实时结构化数据（股价/汇率）？
│   └── 是 → brave_web_search(enable_rich_callback=true) → brave_rich_search
│
└── 其他一切搜索 →
    brave_web_search
    │
    ├── 浏览结果列表 → 按 L1-L7 判断来源可信度
    ├── 需要多源交叉验证？→ 调整搜索词再搜 1-2 轮
    ├── 需要中英文双语来源？
    │   └── 是 → 对同一信息需求执行两轮搜索：
    │         brave_web_search(中文关键词, search_lang=zh)
    │         brave_web_search(英文关键词, search_lang=en)
    │         合并结果 → 按 L1-L7 筛选 → 确保英文来源覆盖
    └── 发现高价值长文页面？→ brave_llm_context 提取全文
```

**核心原则**：`brave_web_search` 是唯一的搜索工具。Agent 通过浏览结果列表自行判断来源可信度、发现不同角度、识别高价值页面。多源交叉验证通过调整搜索词、多轮搜索实现，而非依赖 AI 合成答案。

## 为什么只用 web_search

1. **来源可见** — 每条结果标注网站，Agent 在点击前就能按 L1-L7 筛选，而非信任 AI 合成的匿名文本
2. **多样性即信息** — 不同来源的标题排列本身就是"信息地图"，一眼看出高频话题和不同立场
3. **意外发现** — 搜索结果可能冒出意料之外的关键词和方向
4. **URL 是操作入口** — 找到高价值页面后，用 `brave_llm_context` 提取全文并归档

## 与 L1-L7 可信度体系的集成

| 可信度要求 | 搜索策略 |
|-----------|---------|
| **L1-L2**（官方/国际机构） | `brave_web_search` → 筛选官方页面 → `brave_llm_context` 从原始页面提取，避免二次引用 |
| **L3-L4**（投行/券商） | `brave_web_search` 了解市场共识，注意承销/做市利益冲突 |
| **L5-L7**（低可信度） | 仅作为 web_search 探索线索，不入知识库 |

**重要原则**：
- 优先定位 L1-L2 来源的官方页面，用 `brave_llm_context` 提取全文
- 来自 L6-L7 来源的数据不出现在研报正文中（仅作探索线索）
- 单一来源的结论必须注明"需进一步验证"
- 多来源数据不一致时，优先采信 L1 官方数据

## 搜索请求协议

调用方在调用本技能时，应提供以下上下文：

| 参数 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `research_layer` | `"macro"` / `"industry"` / `"company"` | 可选。分析层级，影响搜索关键词构建 | `"industry"` |
| `min_credibility` | `L1`-`L7` | 可选。来源最低可信度要求，默认不限制 | `L4` |
| `reason` | 简短说明 | 可选。为什么搜、用于什么目的 | `"行业研报需要市场规模数据"` |
| `cross_validate` | boolean | 可选。是否需要多轮交叉验证，默认 false | `true` |
| `require_english_sources` | boolean | 可选。是否必须包含英文来源，默认 false。为 true 时搜索过程必须至少执行一轮英文搜索，宏观和行业分析应设为 true | `true` |

## 搜索后处理

### brave_web_search 的后处理

1. 浏览搜索结果列表，按 L1-L7 判断来源可信度
2. 识别高价值长文页面（研报全文、官方公告、深度分析）→ 用 `brave_llm_context` 提取全文
3. 提取的全文以 `.md` 格式保存在 `research/` 对应项目目录
4. 若 `cross_validate=true`，调整搜索词再搜 1-2 轮，对比多源一致性
5. 若 `require_english_sources=true`，检查搜索结果中英文来源数量和比例：
   - 英文来源为 0 → 调整英文关键词再搜索，直到至少获得 1 条高可信度英文来源
   - 英文来源不足（< 30%）→ 评估是否需要补充英文搜索
6. 最终搜索记录中注明每轮搜索使用的 `search_lang` 值

### brave_llm_context 的后处理

1. 提取的全文以 `.md` 格式保存至 `research/{项目}/` 目录
2. 文件命名：`{来源}-{日期}-{标题}.md`
3. 在知识条目"信息来源"节中引用原文 URL

## 完整示例

### 示例 1：双语探索性搜索

```
调用 search-online：
  research_layer: "industry"
  min_credibility: L4
  require_english_sources: true
  reason: "需要了解2026年白酒行业竞争格局，需中英文双语来源"

search-online 执行：
  1. brave_web_search("2026 白酒行业 竞争格局 研报", search_lang=zh)
  2. 浏览中文结果 → 筛选 L1-L4 来源 → 发现酒业协会报告
  3. brave_web_search("China baijiu industry competitive landscape 2026 report", search_lang=en)
  4. 浏览英文结果 → 筛选 L1-L4 来源 → 发现 Goldman Sachs 行业报告
  5. 两轮合并筛选 → 各选 1-2 条中英文高价值来源
  6. brave_llm_context(英文报告URL) → 提取全文
  7. 返回给调用方："已找到行业报告（中文+英文）并提取全文，可继续分析"
```

### 示例 2：数据查询

```
调用 search-online：
  research_layer: "company"
  reason: "需要对比茅台和五粮液2025年盈利能力"

search-online 执行：
  1. brave_web_search("茅台 五粮液 2025 营收 净利 毛利率 对比", search_lang=zh)
  2. 浏览结果 → 筛选官方财报页面和权威财经数据源
  3. 对关键数据点用 brave_llm_context 提取原文验证
  4. 标注"具体数据需与年报原文验证"，返回给调用方
```

### 示例 3：交叉验证

```
调用 search-online：
  research_layer: "cross_validation"
  cross_validate: true
  reason: "Q3净利数据来自单一来源，需要多源确认"

search-online 执行：
  1. brave_web_search("五粮液 2025 Q3 净利润", search_lang=zh) → 第1轮
  2. 浏览多个来源 → 数据基本一致 → 仍有疑虑
  3. brave_web_search("五粮液 2025 三季报 归母净利润", search_lang=zh) → 第2轮（调整搜索词）
  4. 多源一致确认 → 返回给调用方
```

## 英文关键词翻译指南

将中文搜索意图转化为英文关键词时，遵循以下模式：

| 中文搜索意图 | 英文对应搜索词 |
|-------------|---------------|
| 行业竞争格局 | `{Industry} competitive landscape China 2026` |
| 市场规模数据 | `{Industry} market size China 2026 report` |
| 政策影响分析 | `{Industry} regulation policy impact China` |
| 产业链分析 | `{Industry} supply chain value chain analysis` |
| 国际对比 | `global {industry} market comparison 2026` |
| 财务数据对比 | `{Company-A} vs {Company-B} financial comparison 2025` |
| 宏观经济指标 | `China {indicator} 2026 latest data` |
| 技术路线差异 | `{technology} China vs global technology roadmap` |
| 进出口数据 | `China {product} import export 2026 data` |
| 投行研报 | `{Company} {industry} equity research report 2026` |

**原则**：
- 使用行业通行的英文术语 + `China` 限定词，确保搜索结果聚焦中国相关但来源语言为英文
- 对于宏观和行业层搜索，`require_english_sources` 应默认设为 `true`
- 英文关键词应比中文关键词更具体，以补偿英文搜索对中文市场覆盖的不足
- 若首轮英文搜索结果不理想，调整术语（如 `spirits` → `baijiu`，`tourism` → `travel industry`）
