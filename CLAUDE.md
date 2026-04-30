# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概要

股票调研项目。对特定行业/公司进行自上而下（Top-Down）的调研分析：宏观经济 → 行业 → 公司。采用三层架构：`pipeline/` 获取原始数据，`knowledge/` 存储原子化、可复用的知识条目（原始研报及其解读），`research/` 按调研任务场景组织知识并进行分析，形成可积累、可复用、可验证的研究体系。

## 核心原则

1. **审慎采信** — 对每条信息的来源进行资质评估和可信度标注，宁可标注"待验证"也不虚构确信度
2. **证据可追溯** — 每个知识条目关联原始资料存档，每份原始资料可反向追溯到使用它的条目
3. **自上而下** — 调研从宏观出发，逐层下沉到行业和公司，不跳过任何层级
4. **持续积累** — INDEX.md 从 entries.json 渲染生成，每次入库都要更新索引以反映知识库最新状态
5. **语言多样性** — 每次搜索必须同时使用中文和英文执行，确保知识库来源中英文比例接近 50/50。宏观经济与行业分析至少包含一条英文来源

## 三层架构

```
stock/
├── CLAUDE.md                        # 本文件 — 项目总指引
├── pipeline/                        # 数据获取层 — Python 脚本/爬虫获取年报等原始数据
│   ├── README.md                    #   架构说明与使用指南
│   ├── examples/                    #   可复用的 API/爬虫 示例模板
│   │   └── template.py             #     通用模板 — 复制到 tasks/ 后按需调整
│   ├── lib/                         #   共享工具库
│   │   ├── logger.py               #     任务级日志
│   │   ├── fetcher.py              #     HTTP 请求（限速、重试、UA）
│   │   └── filing_db.py            #     本地获取记录索引（去重）
│   ├── tasks/                       #   活跃任务脚本（gitignored）
│   ├── staging/                     #   原始下载暂存区（gitignored）
│   └── logs/                        #   任务执行日志（gitignored）
├── knowledge/                       # 知识存储层（三级分层）— 原子化知识条目
│   ├── macro/                       #   宏观经济知识
│   │   ├── INDEX.md                 #     知识条目索引（从 entries/entries.json 渲染）
│   │   └── entries/                 #     单条知识文件 + entries.json 主索引
│   ├── industry/                    #   行业知识（按行业分子目录）
│   │   ├── INDEX.md                 #     知识条目索引（从 entries/entries.json 渲染）
│   │   └── entries/
│   │       ├── entries.json         #       程序化条目主索引
│   │       └── {行业名}/             #       按行业分子目录（如 旅游/）
│   └── company/                     #   公司知识
│       ├── INDEX.md                 #     知识条目索引（从 entries/entries.json 渲染）
│       ├── entries/                 #     单条知识文件 + entries.json 主索引
│       └── raw/                     #     原始资料存档（年报PDF + 财务CSV）
│           ├── index.json            #       程序化检索主索引
│           └── {代码}-{公司名}/       #       按公司分子目录
├── research/                        # 分析应用层 — 按任务场景组织知识进行分析
│   └── [项目名]/                    #   单个调研项目（如 tourism）
│       ├── README.md                #     项目概述、范围、核心问题
│       ├── reports/                 #     调研报告输出
│       └── notes/                   #     调研过程笔记
├── TASKS.md                         # 项目级任务管理（大方向与子任务）
└── .claude/
    └── skills/
        ├── stock-research/          # 股票调研技能（含可信度评估 + 证据归档）
        ├── stock-fetch/             # 统一数据搜集技能
        ├── search-online/           # 统一网络搜索技能（探索/提问/验证分流）
        ├── knowledge-index/         # 知识索引管理技能（含可信度框架）
        ├── task-manager/            # 任务管理技能
        └── pipeline/                # 数据获取管道技能
```

## 三层架构：数据获取 → 知识存储 → 分析应用

| 层级 | 目录 | 定位 | 关系 |
|------|------|------|------|
| 数据获取层 | `pipeline/` | Python 脚本/爬虫从公开数据源获取年报等原始信息 | 为 knowledge/ 供给原材料 |
| 知识存储层 | `knowledge/` | 原子化、可复用的知识条目（原始研报信息 + 解读 + 可信度评估） | 消费 pipeline 产出，服务于 research/ |
| 分析应用层 | `research/` | 按任务场景组织知识进行投资分析 | 消费 knowledge/，产出报告 + 新知识回写 |

**工作流**：`pipeline/` 获取原始数据 → `knowledge/` 存储结构化知识 → `research/` 消费知识进行分析 → 新知识回写入 `knowledge/` 入库

## 知识库索引体系：entries.json → INDEX.md

> 条目程序化主索引：`entries/entries.json` → 渲染生成 `INDEX.md`（人类可读）。
> 原始资料索引（仅 company/ 层）：`raw/index.json`（程序化主索引）。
> **数据搜集前必须校验 index.json**：先查 entries.json 确认已有条目范围；company/ 层额外查 raw/index.json 确认已下载年报/财务数据，若已存在则跳过，若部分存在则只补足缺失部分。

## 来源可信度体系

> 权威定义见 `knowledge/sources.yaml` — 项目单一可信度白名单，CLAUDE.md 和 knowledge-index 技能均从此引用。

### 资质等级 (L1-L7)

| 等级 | 类别 | 默认可信度 | 示例 |
|------|------|-----------|------|
| L1 | 官方一手数据 | 高 | 央行公告、统计年鉴、SEC/港交所文件、审计年报 |
| L2 | 国际权威机构 | 高 | IMF, World Bank, BIS, WTO |
| L3 | 顶级投行 | 中高 | Goldman Sachs, Morgan Stanley, JPMorgan, UBS |
| L4 | 国内头部券商 | 中 | 中金、中信、华泰、国泰君安 |
| L5 | 中小研究机构 | 中低 | 区域性券商、小型研究机构 |
| L6 | 财经媒体/数据平台 | 低 | Bloomberg, Reuters, 财新, AKShare |
| L7 | 自媒体/论坛 | 低 | 仅作线索参考，不作为知识依据 |

### 采信规则

- L1-L2 为高可信度基础，可独立支撑宏观判断
- L3-L4 可作为行业和公司分析的主要参考，但需考虑利益冲突
- L5 及以下不能独立支撑投资判断，须有更高级别来源交叉验证
- 单一来源的结论必须在报告中注明"需进一步验证"
- 多来源数据不一致时，优先采信 L1 官方数据，并记录分歧

### 语言多样性要求

在搜索和知识入库阶段，必须同时考虑中文和英文来源：

- 每个信息需求必须分别用中文和英文搜索
- 宏观和行业层知识条目要求至少包含一条英文来源
- 最终知识来源的中英文比例应接近 50/50
- 创建条目时在元数据中标注 `source_language` 字段

## 核心工作流

### 两个独立阶段

阶段一：**数据搜集**（`stock-fetch` 技能 — 只搜集，不分析）
阶段二：**数据分析**（`stock-research` 技能 — 只分析，不搜集）

两个阶段独立触发，不自动串联。用户说"获取/搜集/下载"只执行阶段一；用户说"分析/评估/研判"才执行阶段二。

### 阶段一：数据搜集

当用户要求获取某只股票/公司的数据时，调用 `stock-fetch` 技能：
1. 年报 PDF 下载（annual_report_crawler）→ `knowledge/company/raw/`
2. 财务指标获取（AKShare / pipeline）→ `pipeline/staging/`
3. 结构化入库（knowledge-index）→ `entries/` + `INDEX.md`

数据搜集完成后告知用户：已获取数据的年份范围、关键指标一览、告知如需分析可继续。

### 阶段二：数据分析（用户明确要求时才执行）

当用户要求分析/评估/研判时，调用 `stock-research` 技能：
1. **查阅本地知识库** — 先查 entries.json 确认已有数据范围，再查 INDEX.md 找相关条目
2. **宏观经济分析** — 全球/区域经济环境、货币政策、地缘政治等
3. **行业分析** — 市场规模、竞争格局、产业链、政策、技术趋势
4. **公司分析** — 商业模式、财务、管理层、投行评级、估值
5. **交叉验证** — 多源印证关键数据，识别信息缺口
6. **综合研判** — 区分"确定性高的判断"和"需要验证的假设"
7. **调研报告输出** — `research/[项目]/reports/YYYY-MM-DD_[主题].md`
8. **知识回写** — 分析中发现的新知识按 `knowledge-index` 规范入库

### 任务管理

## 数据获取双轨制

项目有两个互补的数据获取系统，均由 `stock-fetch` 技能统一调度：

| 系统 | 目录 | 获取内容 | 触发场景 |
|------|------|---------|---------|
| annual_report_crawler | `annual_report_crawler/` | 年报 PDF（A股/港股/美股） | 需要原始年报文件时 |
| pipeline (AKShare) | `pipeline/` | 财务指标 CSV/JSON（80+ 指标） | 需要结构化财务数据时 |

**端到端股票数据获取流程**：当用户要求"获取某只股票的信息"时，调用 `stock-fetch` 技能（只搜集不分析）：
1. `annual_report_crawler` → 下载年报 PDF
2. `pipeline` (AKShare) → 获取财务指标与公司信息
3. `knowledge-index` → 全部结构化入库

## 技能系统

### 用户直接触发

- **stock-fetch** — 统一的数据搜集入口（只搜集，不分析）。触发词：获取、下载、搜集、拉取、查 年报/财报/财务数据。整合 年报PDF → AKShare财务指标 → 知识库入库。当用户要求获取某只股票的信息/年报/财报时，必须首先调用此技能。
- **stock-research** — 数据分析与投资研判（只分析，不搜集）。触发词：分析、评估、研判、估值、对比、投资价值。前置条件：目标公司数据已通过 stock-fetch 入库。基于 knowledge/ 中已有数据进行宏观→行业→公司逐层分析。

### 由上述技能内部调度

- **knowledge-index** — 知识库索引管理：创建条目、评估来源可信度（L1-L7）、归档原始资料、更新 INDEX.md。由 stock-fetch 或 stock-research 在入库/回写时调用。
- **pipeline** — 数据获取管道（技术子技能）：AKShare/Python 爬虫获取公司年报等原始数据，经 staging 中转。由 stock-fetch 统一调度，不直接响应用户请求。
- **task-manager** — 项目级任务追踪：创建调研方向、分解子任务、更新完成状态。跨会话持久化。
- **search-online** — 统一网络搜索入口：使用 brave_web_search 搜索，brave_llm_context 提取高价值长文全文。由 stock-research、knowledge-index 等技能在需要在线搜索时调用。

## 可用的 MCP 工具

- `brave_web_search` — 广泛网络搜索（主要搜索工具，用于探索性搜索、发现多个来源、获取话题概览）
- `brave_llm_context` — 长文本深度提取（用于单个高价值网页的全文提取，返回 LLM 优化的清洁文本，适合 RAG）
- `brave_local_search` — 本地商业搜索
- `brave_rich_search` — 结构化数据查询（股票报价、汇率、天气等，需配合 brave_web_search 的 callback_key 使用）
- `WebFetch` — 抓取并解析网页内容（结果以 .md 存入 research/ 对应项目目录）

### MCP 搜索工具选择规则

> **具体选择逻辑见 `search-online` 技能。以下为工具能力速查：**

| 场景 | 工具 | 说明 |
|------|------|------|
| 所有搜索查询 | `brave_web_search` | 返回搜索结果列表，Agent 自行按 L1-L7 筛选来源，多轮搜索实现交叉验证 |
| 已知 URL 的全文提取 | `brave_llm_context` | 返回清洁正文，适合研报/公告长文提取和归档 |
| 获取实时股票报价/汇率 | `brave_web_search` + `brave_rich_search` | 先搜索获取 callback_key，再用 rich_search 获取结构化数据 |

**核心原则**：
- 所有搜索通过 `brave_web_search` 执行，Agent 自行按 L1-L7 筛选来源
- 需多源交叉验证时，调整搜索词进行多轮搜索
- **提取**（已知具体页面 URL）→ `brave_llm_context`，直接提取页面全文清洁正文

### 双语搜索规则

所有通过 `brave_web_search` 执行的搜索必须遵守以下规则：

1. **每个查询执行两轮搜索**：一轮使用中文关键词，设置 `search_lang=zh`；一轮使用英文关键词，设置 `search_lang=en`
2. **英文关键词策略**：将中文搜索意图翻译为地道的英文行业术语（例如 "白酒行业竞争格局" → "China baijiu industry competitive landscape 2026"）
3. **结果合并**：两轮搜索结果合并后按 L1-L7 筛选，兼顾语言多样性
4. **搜索请求协议扩充**：调用方可通过 `require_english_sources` 参数要求搜索过程必须包含英文来源

## 调研报告格式

报告输出至 `research/[项目]/reports/YYYY-MM-DD_[主题].md`：

```markdown
# [主题] 调研报告

**日期**: YYYY-MM-DD

## 核心摘要
- 要点，每条标注可信度

## 宏观环境
...
> 可信度评估：[等级] — [说明]

## 行业分析
...
> 可信度评估：[等级] — [说明]

## 公司分析
...
> 可信度评估：[等级] — [说明]

## 估值与综合观点
### 确定性较高的判断
### 需要进一步验证的假设
### 当前信息缺口

## 信息来源与可信度汇总
| 来源 | 资质等级 | 用途 | 可信度 |
|------|---------|------|--------|

## 原始资料索引
```

## 信息来源优先级

> 详细白名单与采信规则见 `knowledge/sources.yaml`

1. 官方一手数据（L1）：央行公告、统计年鉴、SEC/港交所文件、审计年报
2. 国际权威机构（L2）：IMF, World Bank, BIS
3. 顶级投行（L3）：Goldman Sachs, Morgan Stanley, JPMorgan, UBS
4. 国内头部券商（L4）：中金、中信、华泰、国泰君安
5. 中小研究机构（L5）：仅作交叉验证参考
6. 财经媒体/数据平台（L6）：Bloomberg, Reuters, 财新, AKShare
7. 自媒体/论坛（L7）：仅作线索，不入知识库
8. **语言多样性**：同等可信度等级的来源，优先选择与已有来源不同语言的来源，以丰富视角
