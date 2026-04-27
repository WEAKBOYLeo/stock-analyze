# Pipeline — 数据获取管道

通过 Python 脚本/爬虫从公开数据源获取公司年报、公告等原始信息，经由临时中转区（staging/）整理后，将结构化数据放入 `knowledge/` 对应位置。

## 目录结构

```
pipeline/
├── README.md             # 本文件 — 架构说明
├── .gitignore            # 忽略 tasks/、staging/、logs/ 内容（保留 .gitkeep）
├── examples/             # 可复用的 API/爬虫 示例脚本（每个配一个关键字指导文件）
│   ├── template.py       #   通用爬虫模板 — 复制到 tasks/ 后按需调整
│   ├── akshare_financial.py          #   AKShare: 三大财报 (资产负债表/利润表/现金流量表)
│   ├── akshare_financial_guide.json  #     关键字配置: 股票代码, 财报类型
│   ├── akshare_reports.py            #   AKShare: 业绩报表/预告/快报 + 公告搜索
│   ├── akshare_reports_guide.json    #     关键字配置: 日期, 报表类型, 公告关键词
│   ├── akshare_company.py            #   AKShare: 公司信息/估值/杜邦/成长性对比
│   └── akshare_company_guide.json    #     关键字配置: 股票代码, 启用的信息类型
├── lib/                  # 共享工具库
│   ├── logger.py         #   任务级日志：创建带时间戳的 log 文件 + 控制台输出
│   ├── fetcher.py        #   HTTP 请求封装：限速、重试、User-Agent 管理
│   └── filing_db.py      #   本地获取记录索引：去重、查询已下载文件
├── tasks/                # 活跃任务脚本（gitignored，按需从 examples/ 复制脚本+guide）
├── staging/              # 原始下载文件暂存区（gitignored，整理后移入 knowledge/）
└── logs/                 # 任务执行日志（gitignored）
```

## 工作流

```
examples/
    │
    ├─ 复制脚本 + 指导文件 → tasks/     # 配对复制：.py + _guide.json
    │
    ├─ 修改 guide.json 中的关键字       # 调整股票代码、日期、关键词等
    │
    ├─ 运行 → 输出到 staging/            # CSV/JSON 数据文件
    │
    └─ 组织 → knowledge/                 # 结构化后移入知识库对应位置
                    │
                    ├─ raw/       # 原始数据存档（CSV/PDF 等）
                    ├─ entries/   # 提取的知识条目
                    └─ 更新 INDEX.md + SUMMARY.md
```

## AKShare 示例

项目内置了基于 [AKShare](https://akshare.akfamily.xyz/) 的三个示例，覆盖公司调研的核心数据需求：

| 示例 | 功能 | 数据来源 |
|------|------|---------|
| `akshare_financial.py` | 资产负债表 + 利润表 + 现金流量表 + 财务关键指标 | 东方财富 / 新浪 |
| `akshare_reports.py` | 全市场业绩报表/预告/快报 + 按公司搜索公告 | 东方财富 / 巨潮资讯 |
| `akshare_company.py` | 公司基本信息 + 估值/杜邦/成长性同行对比 | 东方财富 / 雪球 / 巨潮 |

每个 `.py` 脚本配有一个 `_guide.json` 关键字指导文件：
- 存储所有可调整参数（股票代码、日期、启用的功能等）
- 包含 API 函数参考和使用说明
- 复制到 `tasks/` 后只需修改 JSON，无需改动 Python 脚本
    │
    └─ 组织 → knowledge/           # 结构化后移入知识库对应位置
                    │
                    ├─ raw/       # 原始资料存档（年报 PDF 等）
                    ├─ entries/   # 提取的知识条目
                    └─ 更新 INDEX.md + SUMMARY.md
```

## 与 knowledge/ 和 research/ 的关系

| 目录 | 定位 | 关系 |
|------|------|------|
| `pipeline/` | **数据获取层** — 从外部源抓取原始信息 | 为 knowledge/ 供给原材料 |
| `knowledge/` | **知识存储层** — 原子化、结构化、可溯源的知识条目 | 消费 pipeline 产出，服务于 research/ |
| `research/` | **分析应用层** — 按任务场景组织知识进行分析 | 消费 knowledge/，产出报告 |

## 示例模板说明

`examples/template.py` 展示了一个标准爬虫脚本的结构：

1. **CONFIG 区**：集中管理搜索目标、参数、输出路径
2. **搜索函数**：调用 API / 爬取网页，返回结果列表
3. **下载函数**：下载文件到 staging/，记录到 filing_db
4. **主流程**：串联搜索 → 过滤 → 下载 → 汇总

实际使用时，复制 `template.py` 到 `tasks/` 目录，根据目标数据源调整搜索逻辑和参数。任务完成后，`tasks/` 中的脚本可作为记录保留。

## 新增数据源

当需要支持新的数据源时：

1. 在 `examples/` 中创建针对该数据源的示例脚本（参考 `template.py`）
2. 脚本可复用时复制到 `tasks/` 调整参数即可
3. 确保包含 User-Agent、限速、错误处理
