---
name: pipeline
description: 数据获取管道（技术子技能）— 由 stock-fetch 统一调度，不直接响应用户请求。提供 AKShare/Python 爬虫获取年报、公告、SEC filings 等原始数据的能力。
---

# 数据获取管道技能

## 核心概念

`pipeline/` 是项目的**数据获取层**，与 `knowledge/`（知识存储层）和 `research/`（分析应用层）形成三层架构：

```
pipeline/     →  获取原始数据（年报PDF、公告等）
knowledge/    →  存储结构化、可溯源的知识条目
research/     →  按任务场景组织知识进行分析
```

管道的工作流：**复制脚本+guide → 修改 guide.json 关键字 → 运行脚本 → staging 暂存 → 整理入库**

## 目录结构

```
pipeline/
├── README.md             # 架构说明
├── .gitignore            # 忽略 tasks/、staging/、logs/ 内容
├── examples/             # 可复用的 API/爬虫 示例脚本（每个配一个关键字指导文件）
│   ├── template.py                  # 通用模板
│   ├── akshare_financial.py         # AKShare: 三大财报
│   ├── akshare_financial_guide.json #   关键字配置
│   ├── akshare_reports.py           # AKShare: 业绩报表/公告
│   ├── akshare_reports_guide.json   #   关键字配置
│   ├── akshare_company.py           # AKShare: 公司信息/估值对比
│   └── akshare_company_guide.json   #   关键字配置
├── lib/                  # 共享工具库
│   ├── logger.py         # 任务级日志（文件 + 控制台）
│   ├── fetcher.py        # HTTP 请求封装（限速、重试、UA 管理）
│   └── filing_db.py      # 本地获取记录索引（去重、查询）
├── tasks/                # 活跃任务脚本（gitignored）
├── staging/              # 原始下载文件暂存区（gitignored）
└── logs/                 # 任务执行日志（gitignored）
```

## 使用流程

### 0. 选择示例

根据调研需要选择对应的示例脚本：

| 调研需求 | 使用示例 |
|---------|---------|
| 获取公司三大财报（资产负债表/利润表/现金流） | `akshare_financial` |
| 获取全市场业绩报表/预告/快报 + 搜索公司公告 | `akshare_reports` |
| 获取公司基本信息/估值/杜邦/成长性同行对比 | `akshare_company` |
| 自定义数据源 / 爬虫 | `template` |

### 1. 创建任务脚本

每个示例脚本配有一个 `_guide.json` 关键字指导文件。**两者必须配对复制**：

```bash
# 复制脚本 + 关键字配置
cp pipeline/examples/akshare_financial.py pipeline/tasks/
cp pipeline/examples/akshare_financial_guide.json pipeline/tasks/
```

### 2. 调整关键字

只修改 `_guide.json` 文件即可，无需改动 Python 脚本：
- `stock_codes` — 目标股票代码列表
- `enabled_sheets` — 启用的报表类型
- `report_dates` — 搜索日期
- 各 `enable_xxx` 开关 — 按需启用功能

`_guide.json` 中包含了所有可调参数的说明、API 函数参考、常用关键词速查。

### 3. 运行脚本

```bash
cd /home/lrt-asus/project/stock
pip install akshare pandas  # 首次使用需安装
python pipeline/tasks/akshare_financial.py
```

脚本会：
- 通过 AKShare 从东方财富/巨潮/新浪等公开数据源获取数据
- 将 CSV/JSON 数据保存到 `pipeline/staging/akshare/[类型]/`
- 在 `filing_index.json` 中记录已获取数据（跨任务去重）
- 在 `pipeline/logs/` 中生成带时间戳的执行日志

### 4. 整理入库

搜索成功完成后，**必须立即将数据从 staging 移入 knowledge 知识库**，不得让数据长期停留在 staging 中。

> 入库规范详见 `knowledge-index` 技能。以下为标准流程：

**Step 1: 原始资料归档**
```bash
mkdir -p knowledge/company/raw/{code}-{公司名}
cp pipeline/staging/akshare/financial/{code}_financial_abstract.csv \
   knowledge/company/raw/{code}-{公司名}/{code}-{公司名}-财务摘要.csv
```
然后更新 `knowledge/company/raw/index.json` 和 `INDEX.md`。

**Step 2: 创建知识条目**
在 `knowledge/company/entries/` 创建条目文件，命名：`{代码}-{公司名}-{主题}.md`：
- 近10年营收/利润/毛利率趋势表
- 资产负债结构分析
- 现金流变化
- 关键判断（确定性高 vs 待验证）
- 与同行业横向对比（如已获取全市场数据）
- 信息缺口清单

**Step 3: 更新索引**
在 `knowledge/company/INDEX.md` 中添加条目行，标注可信度和原始资料引用。

**Step 4: 更新索引**
验证 entries.json 和 INDEX.md 已正确更新。

**Step 5: 清理 staging**（可选）
入库验证完成后可清理 staging 临时文件。

### 5. 任务收尾

- 任务脚本保留在 `tasks/` 中作为执行记录
- 检查 `pipeline/logs/` 确认无遗漏错误
- 将新发现的数据源模式整理回 `examples/` 供复用

---

## AKShare API 兼容性

AKShare 不同版本间 API 行为可能不同。以下为已验证的函数状态：

### ✅ 已验证可用（v1.18.57）

| 函数 | 用途 | 注意事项 |
|------|------|---------|
| `stock_financial_abstract(symbol)` | 公司财务摘要（80+指标×全报告期） | **推荐主力函数**，单次调用覆盖三大报表+指标 |
| `stock_yjbb_em(date)` | 全市场业绩报表 | 按日期获取，适合行业横向对比 |
| `stock_yjyg_em(date)` | 全市场业绩预告 | 预增/预减/扭亏等预告类型 |
| `stock_individual_info_em(symbol)` | 公司基本信息 | 需要稳定网络，代理环境下可能失败 |

### ❌ 已知失效（v1.18.57）

| 函数 | 错误现象 | 解决方案 |
|------|---------|---------|
| `stock_balance_sheet_by_report_em` | 返回 NoneType | 升级 akshare 或使用 `financial_abstract` 替代 |
| `stock_profit_sheet_by_report_em` | 返回 NoneType | 同上 |
| `stock_cash_flow_sheet_by_report_em` | 返回 NoneType | 同上 |
| `stock_financial_analysis_indicator` | 返回空 DataFrame | 该功能已在 `financial_abstract` 中覆盖 |

### 故障排查

| 症状 | 可能原因 | 解决步骤 |
|------|---------|---------|
| 所有函数返回 NoneType | AKShare 版本过旧/过新 | ① `pip install akshare --upgrade` ② 换用 `stock_financial_abstract` |
| 代理/网络错误 | push2.eastmoney.com 被代理阻断 | ① 检查 HTTPS_PROXY 环境变量 ② 切换网络 ③ 增加 retry_delay |
| 某只股票返回空 | ST/退市/代码格式不对 | ① 确认代码为6位数字 ② 尝试其他 AKShare 函数 ③ 手动查东方财富网页 |
| 速率限制 (429) | 请求太频繁 | 增加 retry_delay 到 5-10 秒 |

## 新增数据源

当遇到新数据源需要支持时：

1. 参考 `examples/template.py` 的模式
2. 在 `examples/` 下创建 `.py` 脚本 + `_guide.json` 关键字配置（配对）
3. `.py` 负责数据获取逻辑，`_guide.json` 存储所有可调参数和 API 参考
4. 确保包含：User-Agent 设置、错误处理、日志记录、去重检查

### 主要数据源参考

| 数据源 | 市场 | 覆盖内容 | 获取方式 |
|--------|------|---------|-------------|
| AKShare (东方财富/巨潮) | A股 | 财报、业绩、公告、公司信息、估值 | `pip install akshare` Python API |
| SEC EDGAR | 美股 | 10-K/20-F 年报、10-Q 季报 | REST API（免费，需 UA） |
| HKEX 披露易 | 港股 | 年报、中报、公告 | HTTP POST + JSON |
| 巨潮资讯网 | A股 | 年报、半年报、季报 | HTTP POST（form-encoded）/ AKShare 封装 |
| 上交所 | A股（沪市） | 年报、公告 | 网页搜索 + 下载 |
| 深交所 | A股（深市） | 年报、公告 | 网页搜索 + 下载 |

## 日志与追踪

每次任务执行都会在 `pipeline/logs/` 生成日志文件，格式：`[任务名]_[YYYYMMDD-HHMMSS].log`

日志级别：
- **DEBUG**：请求详情、响应状态码（仅写入文件）
- **INFO**：关键步骤、下载成功（文件 + 控制台）
- **WARN**：限速等待、非致命错误
- **ERROR**：下载失败、API 报错

`filing_index.json` 跨任务记录所有已获取文件，防止重复下载。

## 与 annual_report_crawler 的协作

年报 PDF 获取由 `annual_report_crawler/` 负责（独立的巨潮资讯/SEC 下载工具），本技能通过 AKShare 获取结构化财务指标。两者互补：

| 需求 | 使用工具 |
|------|---------|
| 年报 PDF 原文 | `annual_report_crawler` CLI |
| 财务指标（营收/利润/ROE/负债率等） | 本技能（AKShare `stock_financial_abstract`） |
| 公司基本信息/估值对比 | 本技能（AKShare company 系列） |

端到端流程见 `stock-fetch` 技能。

## 与 stock-research 技能的协作

本技能是 `stock-research` 的数据获取环节：

1. `stock-research` 调研过程中发现需要获取某公司年报时，触发本技能
2. 本技能通过管道获取原始数据，放入 staging
3. 原始数据整理后按 `knowledge-index` 规范入库
4. `stock-research` 继续使用入库的知识进行调研

## 安全与合规

- 仅从公开数据源获取信息（SEC EDGAR、HKEX、巨潮资讯网等官方披露平台）
- 遵守各数据源的 robots.txt 和 API 使用条款
- 控制请求频率，不对目标服务器造成负担
- User-Agent 中提供联系方式（SEC 要求）
- 不爬取付费/登录后的内容
- 获取的年报 PDF 仅用于研究用途，不对外分发
