#!/usr/bin/env python3
"""
AKShare 公司基本面信息获取 — 公司概况、行业分类、估值对比、股东信息。

数据源：东方财富网 + 雪球 + 巨潮资讯网（通过 AKShare）
依赖：pip install akshare pandas

用法：
    cp pipeline/examples/akshare_company.py pipeline/tasks/
    cp pipeline/examples/akshare_company_guide.json pipeline/tasks/
    # 修改 guide.json 中的股票代码和启用选项
    python pipeline/tasks/akshare_company.py

输出：
    - CSV/JSON → pipeline/staging/akshare/company/
    - 日志 → pipeline/logs/akshare_company_{timestamp}.log
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


GUIDE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "akshare_company_guide.json")

def load_guide():
    if os.path.exists(GUIDE_FILE):
        with open(GUIDE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

guide = load_guide()

TASK_NAME = guide.get("task_name", "akshare_company")
STOCK_CODES = guide.get("stock_codes", ["600519", "000858"])

# 启用的信息类型
ENABLE_INFO = guide.get("enable_company_info", True)
ENABLE_PROFILE = guide.get("enable_company_profile", False)
ENABLE_VALUATION = guide.get("enable_valuation_comparison", False)
ENABLE_DUPONT = guide.get("enable_dupont_comparison", False)
ENABLE_GROWTH = guide.get("enable_growth_comparison", False)
ENABLE_INDICATOR = guide.get("enable_financial_indicator", False)

STAGING_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "staging", "akshare", "company"
)


def fetch_company_info(symbol: str, log: TaskLogger, db: FilingDB) -> str | None:
    """获取个股基本信息（东方财富）。"""
    tag = f"info_{symbol}"
    if db.exists("akshare_company", symbol, tag, "latest"):
        log.info(f"  [{symbol}] 公司信息 — 已获取")
        return None

    try:
        df = ak.stock_individual_info_em(symbol=symbol)
        if df is None or df.empty:
            log.warn(f"  [{symbol}] 公司信息返回空")
            return None

        # 此函数返回单列，转为 dict 保存
        dest = os.path.join(STAGING_DIR, f"{symbol}_info.json")
        os.makedirs(STAGING_DIR, exist_ok=True)

        info_dict = {}
        for _, row in df.iterrows():
            info_dict[str(row.iloc[0])] = str(row.iloc[1]) if len(row) > 1 else ""

        with open(dest, "w", encoding="utf-8") as f:
            json.dump(info_dict, f, indent=2, ensure_ascii=False)

        db.add({
            "source": "akshare_company",
            "ticker": symbol,
            "filing_type": "公司基本信息",
            "filing_date": "latest",
            "data_keys": list(info_dict.keys()),
            "local_path": dest,
            "status": "fetched",
        })

        log.info(f"  [{symbol}] 公司信息 → {dest}")
        # 打印关键信息
        for key in ["股票简称", "总市值", "行业", "上市时间", "总股本"]:
            if key in info_dict:
                log.info(f"    {key}: {info_dict[key]}")

        return dest

    except Exception as e:
        log.error(f"  [{symbol}] 公司信息失败: {e}")
        return None


def fetch_company_profile(symbol: str, log: TaskLogger, db: FilingDB) -> str | None:
    """获取公司概况（巨潮资讯网 — 更详细）。"""
    tag = f"profile_{symbol}"
    if db.exists("akshare_company", symbol, tag, "latest"):
        log.info(f"  [{symbol}] 公司概况 — 已获取")
        return None

    try:
        df = ak.stock_company_profile_cninfo(symbol=symbol)
        if df is None or df.empty:
            log.warn(f"  [{symbol}] 公司概况返回空")
            return None

        dest = os.path.join(STAGING_DIR, f"{symbol}_profile.csv")
        os.makedirs(STAGING_DIR, exist_ok=True)
        df.to_csv(dest, index=False, encoding="utf-8-sig")

        db.add({
            "source": "akshare_company",
            "ticker": symbol,
            "filing_type": "公司概况_巨潮",
            "filing_date": "latest",
            "row_count": len(df),
            "columns": list(df.columns),
            "local_path": dest,
            "status": "fetched",
        })

        log.info(f"  [{symbol}] 公司概况 → {dest}")
        return dest

    except Exception as e:
        log.error(f"  [{symbol}] 公司概况失败: {e}")
        return None


def fetch_valuation_comparison(symbol: str, log: TaskLogger, db: FilingDB) -> str | None:
    """获取个股估值比较数据（与同行业对比）。"""
    tag = f"valuation_{symbol}"
    if db.exists("akshare_company", symbol, tag, "latest"):
        log.info(f"  [{symbol}] 估值比较 — 已获取")
        return None

    try:
        df = ak.stock_zh_valuation_comparison_em(symbol=symbol)
        if df is None or df.empty:
            log.warn(f"  [{symbol}] 估值比较返回空")
            return None

        dest = os.path.join(STAGING_DIR, f"{symbol}_valuation.csv")
        os.makedirs(STAGING_DIR, exist_ok=True)
        df.to_csv(dest, index=False, encoding="utf-8-sig")

        db.add({
            "source": "akshare_company",
            "ticker": symbol,
            "filing_type": "估值比较",
            "filing_date": "latest",
            "row_count": len(df),
            "local_path": dest,
            "status": "fetched",
        })

        log.info(f"  [{symbol}] 估值比较 → {dest} ({len(df)} 条同行)")
        return dest

    except Exception as e:
        log.error(f"  [{symbol}] 估值比较失败: {e}")
        return None


def fetch_dupont_comparison(symbol: str, log: TaskLogger, db: FilingDB) -> str | None:
    """杜邦分析比较。"""
    tag = f"dupont_{symbol}"
    if db.exists("akshare_company", symbol, tag, "latest"):
        log.info(f"  [{symbol}] 杜邦分析 — 已获取")
        return None

    try:
        df = ak.stock_zh_dupont_comparison_em(symbol=symbol)
        if df is None or df.empty:
            log.warn(f"  [{symbol}] 杜邦分析返回空")
            return None

        dest = os.path.join(STAGING_DIR, f"{symbol}_dupont.csv")
        os.makedirs(STAGING_DIR, exist_ok=True)
        df.to_csv(dest, index=False, encoding="utf-8-sig")

        db.add({
            "source": "akshare_company",
            "ticker": symbol,
            "filing_type": "杜邦分析",
            "filing_date": "latest",
            "local_path": dest,
            "status": "fetched",
        })

        log.info(f"  [{symbol}] 杜邦分析 → {dest} (ROE 拆解)")
        return dest

    except Exception as e:
        log.error(f"  [{symbol}] 杜邦分析失败: {e}")
        return None


def fetch_growth_comparison(symbol: str, log: TaskLogger, db: FilingDB) -> str | None:
    """成长性比较。"""
    tag = f"growth_{symbol}"
    if db.exists("akshare_company", symbol, tag, "latest"):
        log.info(f"  [{symbol}] 成长性比较 — 已获取")
        return None

    try:
        df = ak.stock_zh_growth_comparison_em(symbol=symbol)
        if df is None or df.empty:
            log.warn(f"  [{symbol}] 成长性比较返回空")
            return None

        dest = os.path.join(STAGING_DIR, f"{symbol}_growth.csv")
        os.makedirs(STAGING_DIR, exist_ok=True)
        df.to_csv(dest, index=False, encoding="utf-8-sig")

        db.add({
            "source": "akshare_company",
            "ticker": symbol,
            "filing_type": "成长性比较",
            "filing_date": "latest",
            "local_path": dest,
            "status": "fetched",
        })

        log.info(f"  [{symbol}] 成长性比较 → {dest} ({len(df)} 条同行)")
        return dest

    except Exception as e:
        log.error(f"  [{symbol}] 成长性比较失败: {e}")
        return None


def fetch_financial_indicator(symbol: str, log: TaskLogger, db: FilingDB) -> str | None:
    """获取新浪财务关键指标。"""
    tag = f"indicator_{symbol}"
    if db.exists("akshare_company", symbol, tag, "latest"):
        log.info(f"  [{symbol}] 财务指标 — 已获取")
        return None

    try:
        df = ak.stock_financial_analysis_indicator(symbol=symbol)
        if df is None or df.empty:
            log.warn(f"  [{symbol}] 财务指标返回空")
            return None

        dest = os.path.join(STAGING_DIR, f"{symbol}_indicator.csv")
        os.makedirs(STAGING_DIR, exist_ok=True)
        df.to_csv(dest, index=False, encoding="utf-8-sig")

        db.add({
            "source": "akshare_company",
            "ticker": symbol,
            "filing_type": "财务关键指标",
            "filing_date": "latest",
            "row_count": len(df),
            "local_path": dest,
            "status": "fetched",
        })

        log.info(f"  [{symbol}] 财务指标 → {dest} ({len(df)} 行)")
        return dest

    except Exception as e:
        log.error(f"  [{symbol}] 财务指标失败: {e}")
        return None


def main():
    log = TaskLogger(TASK_NAME)
    log.section("AKShare 公司基本面信息获取")

    db = FilingDB()
    os.makedirs(STAGING_DIR, exist_ok=True)

    enabled = []
    if ENABLE_INFO: enabled.append("公司基本信息")
    if ENABLE_PROFILE: enabled.append("公司概况(巨潮)")
    if ENABLE_VALUATION: enabled.append("估值比较")
    if ENABLE_DUPONT: enabled.append("杜邦分析")
    if ENABLE_GROWTH: enabled.append("成长性比较")
    if ENABLE_INDICATOR: enabled.append("财务关键指标")

    log.info(f"股票代码: {STOCK_CODES}")
    log.info(f"启用: {', '.join(enabled) if enabled else '(无)'}")
    log.info(f"输出目录: {STAGING_DIR}")
    log.info("")

    total = 0
    for code in STOCK_CODES:
        log.section(f"处理 {code}")

        if ENABLE_INFO:
            p = fetch_company_info(code, log, db)
            if p: total += 1

        if ENABLE_PROFILE:
            p = fetch_company_profile(code, log, db)
            if p: total += 1

        if ENABLE_VALUATION:
            p = fetch_valuation_comparison(code, log, db)
            if p: total += 1

        if ENABLE_DUPONT:
            p = fetch_dupont_comparison(code, log, db)
            if p: total += 1

        if ENABLE_GROWTH:
            p = fetch_growth_comparison(code, log, db)
            if p: total += 1

        if ENABLE_INDICATOR:
            p = fetch_financial_indicator(code, log, db)
            if p: total += 1

    log.section("Summary")
    log.summary({
        "Task": TASK_NAME,
        "Stocks processed": len(STOCK_CODES),
        "Files fetched": total,
        "Output directory": STAGING_DIR,
        "Guide file": GUIDE_FILE,
        "Log file": log.log_path,
    })

    log.info("提示: 修改 pipeline/tasks/akshare_company_guide.json 调整股票代码和启用的信息类型")


if __name__ == "__main__":
    main()
