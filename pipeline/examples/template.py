#!/usr/bin/env python3
"""
通用年报/公告 搜索下载模板。

使用方法：
    1. 复制本文件到 pipeline/tasks/[任务名].py
    2. 修改 CONFIG 区的搜索目标和参数
    3. 实现 search_announcements() 函数，适配目标数据源的 API
    4. 运行：python pipeline/tasks/[任务名].py

输出：
    - 原始文件 → pipeline/staging/[数据源]/[代码]_[日期].[扩展名]
    - 元数据   → pipeline/staging/[数据源]/[代码]_[日期].json
    - 执行日志 → pipeline/logs/[任务名]_[时间戳].log

每新增一个数据源，按此模板模式编写对应的搜索逻辑。
"""

import sys
import os

# 确保能 import lib/ 模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from lib.logger import TaskLogger
from lib.fetcher import Fetcher
from lib.filing_db import FilingDB

# ═══════════════════════════════════════════════════════════════════════
# CONFIG — 按任务调整以下参数
# ═══════════════════════════════════════════════════════════════════════

TASK_NAME = "my_search"           # 任务名，用于日志文件名
DATA_SOURCE = "my_source"         # 数据源标识（如 sec_edgar, hkex, cninfo）

# 搜索目标
COMPANIES = [
    {"code": "000001", "name": "Example Inc."},
]

# 搜索参数
FILING_TYPE = "annual"            # 文件类型：annual / interim / quarterly
FROM_DATE = "2024-01-01"
TO_DATE   = "2025-12-31"

# 请求配置
USER_AGENT = "StockResearch/1.0 (your-email@example.com)"
MAX_DOWNLOADS = 5                 # 单次运行下载上限

# 输出路径
STAGING_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "staging", DATA_SOURCE
)

# ═══════════════════════════════════════════════════════════════════════
# 搜索函数 — 根据目标数据源实现
# ═══════════════════════════════════════════════════════════════════════

def search_announcements(fetcher: Fetcher, company: dict, log: TaskLogger) -> list[dict]:
    """
    搜索公司公告/年报。

    Args:
        fetcher: Fetcher 实例（已配置好 User-Agent 和限速）
        company: COMPANIES 中的一条 {"code": ..., "name": ...}
        log: 日志实例

    Returns:
        公告列表，每条为一个 dict：
            {
                "source": DATA_SOURCE,
                "code": 公司代码,
                "name": 公司名,
                "title": 公告标题,
                "filing_date": "YYYY-MM-DD",
                "doc_url": 下载链接,
            }

    实现要点：
        - 使用 fetcher.get_json() / fetcher.post_json() / fetcher.get_text()
        - 处理 API 特有的分页、筛选参数
        - 异常时 log.error() 并返回空列表，不中断整体流程
        - 注意 API 的限速要求，适当 sleep
    """
    # TODO: 实现目标数据源的搜索逻辑
    #
    # 示例（SEC EDGAR 风格）:
    #   url = "https://api.example.com/search"
    #   params = {"company": company["code"], "type": FILING_TYPE, ...}
    #   data = fetcher.get_json(url, **params)
    #   results = []
    #   for item in data.get("results", []):
    #       results.append({...})
    #   return results

    log.warn("search_announcements() not implemented — this is a template")
    return []


# ═══════════════════════════════════════════════════════════════════════
# 下载函数 — 通常不需要修改
# ═══════════════════════════════════════════════════════════════════════

def download_filing(fetcher: Fetcher, item: dict, log: TaskLogger, db: FilingDB) -> str | None:
    """
    下载单个公告文件到 staging/，返回本地路径或 None。
    自动去重：已下载过的文件跳过。
    """
    import json

    code = item.get("code", "unknown")
    date = item.get("filing_date", "unknown")
    url = item.get("doc_url", "")

    if not url:
        log.warn(f"No download URL for {code} on {date}")
        return None

    # 去重检查
    if db.exists(DATA_SOURCE, code, item.get("title", "")[:50], date):
        log.info(f"Already downloaded: {code} {date}")
        return None

    # 生成文件名
    safe_title = item.get("title", "")[:40].replace("/", "_").replace(" ", "_")
    ext = os.path.splitext(url.split("?")[0])[1] or ".pdf"
    filename = f"{code}_{date}_{safe_title}{ext}"
    dest = os.path.join(STAGING_DIR, filename)

    try:
        fetcher.download(url, dest)

        # 存入本地索引
        record = {
            "source": DATA_SOURCE,
            "ticker": code,
            "company_name": item.get("name", ""),
            "filing_type": item.get("title", ""),
            "filing_date": date,
            "doc_url": url,
            "local_path": dest,
            "status": "downloaded",
        }
        db.add(record)

        # 保存 JSON 元数据
        meta_path = os.path.join(STAGING_DIR, f"{code}_{date}.json")
        with open(meta_path, "w") as f:
            json.dump(record, f, indent=2, ensure_ascii=False)

        return dest

    except Exception as e:
        log.error(f"Download failed: {url} → {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════════════════════

def main():
    log = TaskLogger(TASK_NAME)
    log.section(f"Pipeline: {TASK_NAME}")

    os.makedirs(STAGING_DIR, exist_ok=True)

    fetcher = Fetcher(user_agent=USER_AGENT, log=log)
    db = FilingDB()

    total = 0
    for company in COMPANIES:
        if total >= MAX_DOWNLOADS:
            log.warn(f"Reached MAX_DOWNLOADS ({MAX_DOWNLOADS}), stopping")
            break

        code = company["code"]
        name = company["name"]
        log.section(f"Processing {code} — {name}")

        items = search_announcements(fetcher, company, log)

        for item in items:
            if total >= MAX_DOWNLOADS:
                break
            path = download_filing(fetcher, item, log, db)
            if path:
                total += 1

    fetcher.close()

    log.section("Summary")
    log.summary({
        "Task": TASK_NAME,
        "Companies": len(COMPANIES),
        "Downloaded": total,
        "Staging": STAGING_DIR,
        "Log file": log.log_path,
    })


if __name__ == "__main__":
    main()
