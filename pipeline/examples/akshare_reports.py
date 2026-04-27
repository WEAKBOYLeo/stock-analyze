#!/usr/bin/env python3
"""
AKShare 业绩报表/预告/快报 + 信息披露公告获取。

数据源：东方财富网 + 巨潮资讯网（通过 AKShare）
依赖：pip install akshare pandas

用法：
    # 1. 复制到任务区
    cp pipeline/examples/akshare_reports.py pipeline/tasks/
    cp pipeline/examples/akshare_reports_guide.json pipeline/tasks/

    # 2. 按需修改 akshare_reports_guide.json 中的关键字

    # 3. 运行
    python pipeline/tasks/akshare_reports.py

输出：
    - CSV 数据 → pipeline/staging/akshare/reports/
    - 日志 → pipeline/logs/akshare_reports_{timestamp}.log

AKShare 函数参考：
    stock_yjbb_em(date)                — 业绩报表（按报告期，全市场）
    stock_yjyg_em(date)                — 业绩预告
    stock_yjkb_em(date)                — 业绩快报
    stock_info_disclosure_cninfo(...)   — 巨潮资讯信息披露公告（按公司+关键词搜索）
"""

import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from lib.logger import TaskLogger
from lib.filing_db import FilingDB

try:
    import akshare as ak
    import pandas as pd
except ImportError:
    print("请先安装 AKShare: pip install akshare pandas")
    sys.exit(1)


# ═══════════════════════════════════════════════════════════════════════
# 加载关键字配置
# ═══════════════════════════════════════════════════════════════════════

GUIDE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "akshare_reports_guide.json")

def load_guide():
    if os.path.exists(GUIDE_FILE):
        with open(GUIDE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

guide = load_guide()

TASK_NAME = guide.get("task_name", "akshare_reports")

# 全市场业绩数据日期
REPORT_DATES = guide.get("report_dates", ["20231231", "20240930"])

# 启用的报表类型
ENABLED_TYPES = guide.get("enabled_types", ["yjbb", "yjyg"])

# 按公司搜索公告
ENABLE_DISCLOSURE = guide.get("enable_disclosure_search", False)
DISCLOSURE_STOCKS = guide.get("disclosure_stocks", [
    {"symbol": "600519", "market": "sh", "keyword": "年报", "name": "贵州茅台"},
])

STAGING_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "staging", "akshare", "reports"
)
# ═══════════════════════════════════════════════════════════════════════


def fetch_yjbb(date: str, log: TaskLogger, db: FilingDB) -> str | None:
    """获取全市场业绩报表（东方财富）。"""
    tag = f"yjbb_{date}"
    if db.exists("akshare_reports", "ALL", tag, date):
        log.info(f"  业绩报表 {date} — 已获取，跳过")
        return None

    try:
        log.info(f"  获取全市场业绩报表 {date} ...")
        df = ak.stock_yjbb_em(date=date)

        if df is None or df.empty:
            log.warn(f"  业绩报表 {date} 返回空")
            return None

        filename = f"yjbb_{date}.csv"
        dest = os.path.join(STAGING_DIR, filename)
        os.makedirs(STAGING_DIR, exist_ok=True)
        df.to_csv(dest, index=False, encoding="utf-8-sig")

        db.add({
            "source": "akshare_reports",
            "ticker": "ALL",
            "filing_type": f"业绩报表_{date}",
            "filing_date": date,
            "row_count": len(df),
            "columns": list(df.columns),
            "local_path": dest,
            "status": "fetched",
        })

        log.info(f"  业绩报表 {date} → {dest} ({len(df)} 家)")
        log.info(f"    核心列: {[c for c in df.columns if 'EPS' in c.upper() or 'PROFIT' in c.upper() or 'INCOME' in c.upper()][:5]}")
        return dest

    except Exception as e:
        log.error(f"  业绩报表 {date} 失败: {e}")
        return None


def fetch_yjyg(date: str, log: TaskLogger, db: FilingDB) -> str | None:
    """获取全市场业绩预告（东方财富）。"""
    tag = f"yjyg_{date}"
    if db.exists("akshare_reports", "ALL", tag, date):
        log.info(f"  业绩预告 {date} — 已获取")
        return None

    try:
        log.info(f"  获取全市场业绩预告 {date} ...")
        df = ak.stock_yjyg_em(date=date)

        if df is None or df.empty:
            log.warn(f"  业绩预告 {date} 返回空")
            return None

        filename = f"yjyg_{date}.csv"
        dest = os.path.join(STAGING_DIR, filename)
        os.makedirs(STAGING_DIR, exist_ok=True)
        df.to_csv(dest, index=False, encoding="utf-8-sig")

        db.add({
            "source": "akshare_reports",
            "ticker": "ALL",
            "filing_type": f"业绩预告_{date}",
            "filing_date": date,
            "row_count": len(df),
            "columns": list(df.columns),
            "local_path": dest,
            "status": "fetched",
        })

        log.info(f"  业绩预告 {date} → {dest} ({len(df)} 家)")
        return dest

    except Exception as e:
        log.error(f"  业绩预告 {date} 失败: {e}")
        return None


def fetch_yjkb(date: str, log: TaskLogger, db: FilingDB) -> str | None:
    """获取全市场业绩快报（东方财富）。"""
    tag = f"yjkb_{date}"
    if db.exists("akshare_reports", "ALL", tag, date):
        log.info(f"  业绩快报 {date} — 已获取")
        return None

    try:
        log.info(f"  获取全市场业绩快报 {date} ...")
        df = ak.stock_yjkb_em(date=date)

        if df is None or df.empty:
            log.warn(f"  业绩快报 {date} 返回空")
            return None

        filename = f"yjkb_{date}.csv"
        dest = os.path.join(STAGING_DIR, filename)
        os.makedirs(STAGING_DIR, exist_ok=True)
        df.to_csv(dest, index=False, encoding="utf-8-sig")

        db.add({
            "source": "akshare_reports",
            "ticker": "ALL",
            "filing_type": f"业绩快报_{date}",
            "filing_date": date,
            "row_count": len(df),
            "columns": list(df.columns),
            "local_path": dest,
            "status": "fetched",
        })

        log.info(f"  业绩快报 {date} → {dest} ({len(df)} 家)")
        return dest

    except Exception as e:
        log.error(f"  业绩快报 {date} 失败: {e}")
        return None


def fetch_disclosure(stock: dict, log: TaskLogger, db: FilingDB) -> str | None:
    """按公司搜索巨潮资讯信息披露公告。"""
    symbol = stock["symbol"]
    keyword = stock["keyword"]

    tag = f"disclosure_{symbol}_{keyword}"
    if db.exists("akshare_disclosure", symbol, tag, "latest"):
        log.info(f"  [{symbol}] 公告搜索 '{keyword}' — 已获取")
        return None

    try:
        log.info(f"  [{symbol}] 搜索公告: 关键词='{keyword}' ...")
        df = ak.stock_info_disclosure_cninfo(
            symbol=symbol,
            market=stock["market"],
            keyword=keyword,
            start_date=stock.get("start_date", "2024-01-01"),
            end_date=stock.get("end_date", "2025-12-31"),
        )

        if df is None or df.empty:
            log.warn(f"  [{symbol}] '{keyword}' 无公告结果")
            return None

        filename = f"{symbol}_disclosure_{keyword}.csv"
        dest = os.path.join(STAGING_DIR, filename)
        os.makedirs(STAGING_DIR, exist_ok=True)
        df.to_csv(dest, index=False, encoding="utf-8-sig")

        db.add({
            "source": "akshare_disclosure",
            "ticker": symbol,
            "filing_type": f"公告_{keyword}",
            "filing_date": "latest",
            "row_count": len(df),
            "columns": list(df.columns),
            "local_path": dest,
            "status": "fetched",
        })

        log.info(f"  [{symbol}] 公告 '{keyword}' → {dest} ({len(df)} 条)")
        return dest

    except Exception as e:
        log.error(f"  [{symbol}] 公告搜索失败: {e}")
        return None


def main():
    log = TaskLogger(TASK_NAME)
    log.section("AKShare 业绩报表 / 公告获取")

    db = FilingDB()
    os.makedirs(STAGING_DIR, exist_ok=True)

    log.info(f"报表日期: {REPORT_DATES}")
    log.info(f"启用类型: {ENABLED_TYPES}")
    log.info(f"公告搜索: {'是' if ENABLE_DISCLOSURE else '否'}")
    log.info("")

    total = 0

    # 全市场业绩数据
    for date in REPORT_DATES:
        for rtype in ENABLED_TYPES:
            if rtype == "yjbb":
                p = fetch_yjbb(date, log, db)
            elif rtype == "yjyg":
                p = fetch_yjyg(date, log, db)
            elif rtype == "yjkb":
                p = fetch_yjkb(date, log, db)
            else:
                log.warn(f"未知报表类型: {rtype}")
                continue
            if p:
                total += 1

    # 按公司搜索公告
    if ENABLE_DISCLOSURE:
        for stock in DISCLOSURE_STOCKS:
            log.section(f"公告搜索 {stock.get('name', '')} ({stock['symbol']})")
            p = fetch_disclosure(stock, log, db)
            if p:
                total += 1

    log.section("Summary")
    log.summary({
        "Task": TASK_NAME,
        "Files fetched": total,
        "Output directory": STAGING_DIR,
        "Guide file": GUIDE_FILE,
        "Log file": log.log_path,
    })

    log.info("提示: 修改 pipeline/tasks/akshare_reports_guide.json 调整日期、启用的报表类型、公告搜索条件")


if __name__ == "__main__":
    main()
