---
name: stock-fetch
description: 统一的数据搜集入口。当用户要求获取股票信息、下载年报、搜集财报、查找公司数据时触发。只负责搜集原始数据（年报PDF + 财务指标），不做分析。整合 annual_report_crawler（年报PDF）→ pipeline（AKShare财务指标+公司信息）→ knowledge（结构化入库）三步流程。
---

# 统一数据搜集技能

## 核心定位

**本技能是项目所有数据搜集工作的唯一入口。只搜集，不分析。**

- 负责：下载年报 PDF、获取财务指标 CSV、抓取公司信息、数据入库
- 不负责：财务趋势分析、行业对比、估值研判、投资建议
- 分析工作由 `stock-research` 技能在数据入库后另行执行

## 触发条件（放宽匹配）

用户提出以下**任何类型**的请求时，**必须首先**调用本技能：

- "获取/下载/搜集/拉取 XX 的年报/财报/财务数据"
- "查一下 XX 的财报/年报/财务"
- "帮我对 XX 近 X 年的财报进行调研" — **注意："调研"在此语境下指搜集数据，不是分析**
- "看看 XX 的财务情况" — **仅搜集数据，不做分析**
- "下载 XX 的年报 PDF"
- "把 XX 的数据入库"
- 任何涉及获取特定公司原始数据的请求

**关键词匹配**：获取、下载、搜集、拉取、查、年报、财报、财务数据、年报PDF、信息

**边界判断**：
- 用户说"获取/搜集/下载" + 公司/股票 → 本技能
- 用户说"分析/评估/研判/估值" + 公司/股票 → `stock-research`
- 用户说"调研" — 若提及"年报/财报/数据"等具体文件，按本技能处理（搜集）；若提及"投资价值/估值/前景"，按 `stock-research` 处理

## 前置步骤：数据就绪检查（防重复搜集）

**在开始搜集之前，必须先校验知识库中已有数据：**

1. **查 `knowledge/company/entries/entries.json`** — 确认目标公司是否已有知识条目，查看条目的 `topic`、`date`、`raw_materials` 字段
2. **查 `knowledge/company/raw/index.json`** — 确认原始资料（年报PDF、财务CSV）的年份/指标覆盖范围
3. **查对应行业/宏观层级的 entries.json** — 如涉及行业或宏观数据
4. **对比需求与已有数据**：
   - **全部存在** → 跳过搜集，告知用户"数据已就绪，可直接分析"
   - **部分存在** → 只搜集缺失的年份/指标，已存在的跳过不重复下载
   - **不存在** → 完整执行三步工作流

**校验结果须向用户报告**（格式参考 knowledge-index 技能中的校验结果报告格式）。

## 三步工作流

```
Step 1: annual_report_crawler    下载年报 PDF → knowledge/company/raw/
Step 2: pipeline/AKShare         获取财务指标 + 公司信息 → pipeline/staging/
Step 3: knowledge-index          结构化入库 → entries/ + INDEX.md
```

---

## Step 1 — 年报 PDF 下载

### 1.1 识别股票代码与市场

| 代码特征 | 市场 | 下载方式 |
|---------|------|---------|
| 6位数字，6/688/300 开头 | A股 | CLI Requests 模式（优先）|
| 5位数字 | 港股 | CLI WebDriver 模式 |
| 1-5位字母 | 美股 | CLI Requests 模式（SEC EDGAR）|

A股优先使用 Requests "Hanae" 模式（速度快）。若遇到加密文件（科创板/创业板常见），改用 WebDriver "Shio" 模式。

### 1.2 执行下载

**方式 A — CLI（推荐，无需启动 Web 服务器）**：

```bash
# A股主板（Requests 模式）
cd /home/lrt-asus/project/stock/annual_report_crawler/v1 && \
python annual_report_downloader_rq.py -s <股票代码> -y <年份范围> -d ../annual_reports

# 科创板/创业板/港股（WebDriver 模式，遇到加密问题时使用）
cd /home/lrt-asus/project/stock/annual_report_crawler/v1 && \
python annual_report_downloader_bd.py -s <股票代码> -y <年份范围> -d ../annual_reports
```

**方式 B — Web 界面**（需要交互操作时使用）：

```bash
cd /home/lrt-asus/project/stock/annual_report_crawler && \
python web_app_hysilens.py
# 访问 http://localhost:31425，在界面中选择模式和输入代码
```

**年份范围**：若用户指定了年份则按用户要求；若未指定，默认下载近5年。

### 1.3 移入知识库

下载完成后，将 PDF 移入 `knowledge/company/raw/{代码}-{公司名}/`（按公司分子目录）：

```bash
# 创建公司子目录
mkdir -p knowledge/company/raw/<股票代码>-<公司名>

# 格式: 代码-公司名-年份年报.pdf
cp annual_report_crawler/annual_reports/<原始文件名>.pdf \
   knowledge/company/raw/<股票代码>-<公司名>/<股票代码>-<公司名>-<年份>年报.pdf
```

**文件命名规范**：
- PDF年报: `{代码}-{公司名}-{年份}年报.pdf`（如 `600169-太原重工-2025年报.pdf`）
- CSV数据: `{代码}-{公司名}-{描述}.csv`（如 `600169-太原重工-2005-2026Q1财务摘要.csv`）
- 公司子目录: `{代码}-{公司名}/`（如 `600169-太原重工/`）

### 1.4 更新 JSON 索引

在 `knowledge/company/raw/index.json` 中添加文件记录（程序化检索主索引）：

```json
{
  "code": "600169",
  "name": "太原重工",
  "directory": "600169-太原重工",
  "files": [
    {
      "filename": "600169-太原重工-2025年报.pdf",
      "type": "pdf",
      "year": 2025,
      "category": "annual_report"
    }
  ]
}
```

同时更新 `knowledge/company/raw/INDEX.md`（人类可读补充索引）。

---

## Step 2 — 财务数据与公司信息获取

### 2.1 使用 stock_financial_abstract（主力函数）

AKShare 的 `stock_financial_abstract` 覆盖 80+ 指标 × 全报告期，单次调用即可替代资产负债表+利润表+现金流量表+财务指标。

```bash
cd /home/lrt-asus/project/stock && python3 -c "
import akshare as ak
import pandas as pd

# 获取财务摘要（80+指标 × 全报告期）
df = ak.stock_financial_abstract(symbol='<股票代码>')
df.to_csv('pipeline/staging/akshare/financial/<股票代码>_financial_abstract.csv', index=False, encoding='utf-8-sig')
print(f'获取完成: {len(df)} 行, {len(df.columns)} 列')
"
```

### 2.2 获取公司信息与同行对比（可选）

```bash
cd /home/lrt-asus/project/stock && python3 -c "
import akshare as ak
import json

# 公司基本信息
info = ak.stock_individual_info_em(symbol='<股票代码>')
with open('pipeline/staging/akshare/company/<股票代码>_info.json', 'w') as f:
    json.dump(info.to_dict(), f, ensure_ascii=False, indent=2)
"
```

### 2.3 输出文件

- `pipeline/staging/akshare/financial/{code}_financial_abstract.csv` — 80+ 财务指标 × 全报告期
- `pipeline/staging/akshare/company/{code}_info.json` — 公司基本信息

### 2.4 错误处理

| 症状 | 处理 |
|------|------|
| AKShare 返回 NoneType | `pip install akshare --upgrade` 后重试 |
| 某函数返回空 | 用 `stock_financial_abstract` 替代（已验证可用） |
| 网络/代理错误 | 检查网络，增加 retry_delay 到 5-10s |
| 股票代码无数据 | 确认代码正确，可能已退市或代码格式不对 |

---

## Step 3 — 结构化入库

遵循 `knowledge-index` 技能规范，执行以下操作：

### 3.1 原始资料归档

```bash
# 创建公司子目录
mkdir -p knowledge/company/raw/{代码}-{公司名}

# 财务数据 CSV 移入公司子目录
cp pipeline/staging/akshare/financial/{code}_financial_abstract.csv \
   knowledge/company/raw/{代码}-{公司名}/{代码}-{公司名}-财务摘要.csv
```

更新 `knowledge/company/raw/index.json`（程序化主索引）和 `INDEX.md`（人类可读补充）。

### 3.2 创建知识条目

在 `knowledge/company/entries/` 创建条目文件，命名格式：`{代码}-{公司名}-{主题}.md`

例如：`entries/600169-太原重工-15年财务数据.md`

条目内容**限于数据记录**，不包含分析判断：

```markdown
# {公司名}({代码}) 财务数据

**日期**: YYYY-MM-DD | **股票代码**: {代码} | **行业**: {行业}

## 数据来源
- 财务摘要: raw/{代码}-{公司名}/{代码}-{公司名}-财务摘要.csv
- 原始年报: raw/{代码}-{公司名}/ (YYYY-YYYY年，共N份PDF)

## 年度财务数据表

### 营收与利润
| 年份 | 营收(亿) | 营收增速 | 归母净利(亿) | 毛利率 | 净利率 | ROE |
|------|---------|---------|-------------|--------|--------|-----|

### 资产负债
| 年份 | 资产负债率 | 净资产(亿) | 总资产(亿) |
|------|----------|-----------|----------|

### 现金流
| 年份 | 经营现金流(亿) | 投资现金流(亿) | 筹资现金流(亿) |
|------|--------------|--------------|--------------|

## 公司基本信息
- 全称/简称/代码/行业/上市日期/总股本/总市值

## 原始资料
- [年报 PDF](raw/...)
- [财务摘要 CSV](raw/...)
```

### 3.3 更新 INDEX.md 和 index.json

在 `knowledge/company/INDEX.md` 中添加一行：

```
| YYYY-MM-DD | {公司名} | {代码} | {行业} | 财务数据 | 中→中高 | entries/{代码}-{公司名}-{主题}.md | raw/{代码}-{公司名}/ | 财务数据, {行业标签} |
```

在 `knowledge/company/raw/index.json` 中更新公司文件列表。

---

## 完成后输出

任务完成后向用户报告：

1. **年报 PDF**：下载了哪些年份，存放在哪里（若下载失败说明原因）
2. **财务数据**：获取了哪些指标，数据覆盖的时间范围
3. **入库状态**：创建了哪些条目，更新了哪些索引
4. **数据覆盖年份**：明确列出已有数据的年份范围

**明确告知用户**：数据搜集完成。如需进一步分析（财务趋势、行业对比、估值研判），可使用 `stock-research` 技能。

---

## 与 stock-research 技能的关系

```
用户请求
  ├─ "搜集/获取/下载 数据" → stock-fetch（本技能）→ 数据入库 → 完成
  │                                                          │
  │                                         用户可继续要求 → stock-research 分析
  │
  └─ "分析/评估/研判 投资价值" → stock-research（读取 knowledge/ 已有数据进行分析）
```

本技能是 `stock-research` 的前置步骤。用户先通过本技能搜集数据，再（可选）通过 `stock-research` 进行分析。
