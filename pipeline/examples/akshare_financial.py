#!/usr/bin/env python3
"""
AKShare 公司财务数据获取 — 使用 stock_financial_abstract 一次性获取全量财务指标。

数据源：东方财富网（通过 AKShare）
依赖：pip install akshare pandas

AKShare v1.18+ 兼容说明：
    - stock_balance_sheet_by_report_em / stock_profit_sheet_by_report_em /
      stock_cash_flow_sheet_by_report_em 在 v1.18.57 存在 bug（返回 NoneType）
    - 替代方案: stock_financial_abstract(symbol) — 单次调用返回 80+ 指标 × 全部报告期
    - 备选: stock_financial_report_sina(symbol) — 新浪来源三大报表（部分版本可用）
    - 全市场扫描: stock_yjbb_em(date) — 按日期获取全市场业绩报表

用法：
    cp pipeline/examples/akshare_financial.py pipeline/tasks/
    cp pipeline/examples/akshare_financial_guide.json pipeline/tasks/
    # 修改 guide.json 中的 stock_codes
    python pipeline/tasks/akshare_financial.py

输出：
    - 全量 CSV → pipeline/staging/akshare/financial/{code}_financial_abstract.csv
    - 年份汇总 CSV → pipeline/staging/akshare/financial/{code}_annual_summary.csv
    - 日志 → pipeline/logs/akshare_financial_{timestamp}.log
"""

import sys
import os
import json
import time

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
                          "akshare_financial_guide.json")

def load_guide():
    if os.path.exists(GUIDE_FILE):
        with open(GUIDE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

guide = load_guide()

TASK_NAME = guide.get("task_name", "akshare_financial")
STOCK_CODES = guide.get("stock_codes", ["000001", "600519"])

# 启用的获取模式
FETCH_FINANCIAL_ABSTRACT = guide.get("fetch_financial_abstract", True)
FETCH_YJBB = guide.get("fetch_yjbb_market", False)
YJBB_DATES = guide.get("yjbb_dates", ["20241231"])

# 重试配置
MAX_RETRIES = guide.get("max_retries", 3)
RETRY_DELAY = guide.get("retry_delay", 3)

STAGING_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "staging", "akshare", "financial"
)
# ═══════════════════════════════════════════════════════════════════════


def _retry_call(func, log, retries=MAX_RETRIES, delay=RETRY_DELAY, **kwargs):
    """带重试的 API 调用。"""
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            result = func(**kwargs)
            if result is not None and hasattr(result, 'shape') and result.shape[0] > 0:
                return result
            if result is not None and isinstance(result, dict) and len(result) > 0:
                return result
            log.warn(f"  第{attempt}次调用返回空，{'重试...' if attempt < retries else ''}")
            last_err = ValueError("返回空数据")
        except Exception as e:
            last_err = e
            log.warn(f"  第{attempt}次调用失败: {e.__class__.__name__}: {str(e)[:60]}")
            if attempt < retries:
                time.sleep(delay * attempt)
    raise last_err or RuntimeError("所有重试均返回空数据")


def fetch_financial_abstract(symbol: str, log: TaskLogger, db: FilingDB) -> dict | None:
    """
    获取公司全量财务摘要（stock_financial_abstract）。
    返回 80+ 财务指标 × 全部报告期（季度），覆盖近10年+。
    这是 AKShare v1.18+ 最可靠的财务数据接口。
    """
    if db.exists("akshare_financial", symbol, "financial_abstract", "latest"):
        log.info(f"  [{symbol}] 财务摘要 — 已获取，跳过")
        return None

    try:
        log.info(f"  [{symbol}] 获取财务摘要 (stock_financial_abstract)...")
        df = _retry_call(ak.stock_financial_abstract, log, symbol=symbol)

        # 保存全量数据
        full_dest = os.path.join(STAGING_DIR, f"{symbol}_financial_abstract.csv")
        os.makedirs(STAGING_DIR, exist_ok=True)
        df.to_csv(full_dest, index=False, encoding="utf-8-sig")

        # 提取年报数据（每年1231列）
        annual_cols = [c for c in df.columns if str(c).endswith('1231')]
        annual_dates = sorted(annual_cols, reverse=True)

        db.add({
            "source": "akshare_financial",
            "ticker": symbol,
            "filing_type": "财务摘要_全量",
            "filing_date": "latest",
            "date_range": f"{annual_dates[-1][:4]}-{annual_dates[0][:4]}" if annual_dates else "N/A",
            "row_count": len(df),
            "annual_reports": len(annual_dates),
            "columns": list(df.columns)[:3],
            "local_path": full_dest,
            "status": "fetched",
        })

        log.info(f"  [{symbol}] 财务摘要 → {full_dest}")
        log.info(f"    指标数: {len(df)} | 季度数: {len(df.columns)-2} | 年报数: {len(annual_dates)}")

        # 打印关键指标最新年报值
        key_indicators = ['归母净利润', '营业总收入', '净资产收益率(ROE)', '毛利率', '资产负债率']
        latest_annual = annual_dates[0] if annual_dates else None
        if latest_annual:
            log.info(f"    最新年报({latest_annual[:4]})关键数据:")
            for ind in key_indicators:
                row = df[df.iloc[:,1] == ind]
                if not row.empty:
                    val = row.iloc[0][latest_annual]
                    try:
                        v = float(val)
                        if ind == '营业总收入':
                            log.info(f"      {ind}: {v/1e8:.2f}亿")
                        elif ind in ['归母净利润']:
                            log.info(f"      {ind}: {v/1e8:.2f}亿")
                        else:
                            log.info(f"      {ind}: {v:.2f}%")
                    except:
                        log.info(f"      {ind}: {val}")

        return {"full_dest": full_dest, "df": df, "annual_dates": annual_dates}

    except Exception as e:
        log.error(f"  [{symbol}] 财务摘要获取失败: {e}")
        log.info(f"  [{symbol}] 建议: 升级 akshare → pip install akshare --upgrade")
        log.info(f"  [{symbol}] 备选: 尝试 stock_financial_report_sina(symbol='{symbol}')")
        return None


def fetch_yjbb_market(date: str, log: TaskLogger, db: FilingDB) -> str | None:
    """获取全市场业绩报表（用于横向对比）。"""
    tag = f"yjbb_{date}"
    if db.exists("akshare_yjbb", "ALL", tag, date):
        log.info(f"  全市场业绩报表 {date} — 已获取")
        return None

    try:
        log.info(f"  获取全市场业绩报表 {date} ...")
        df = _retry_call(ak.stock_yjbb_em, log, date=date)

        dest = os.path.join(STAGING_DIR, f"yjbb_all_{date}.csv")
        os.makedirs(STAGING_DIR, exist_ok=True)
        df.to_csv(dest, index=False, encoding="utf-8-sig")

        db.add({
            "source": "akshare_yjbb",
            "ticker": "ALL",
            "filing_type": f"全市场业绩报表_{date}",
            "filing_date": date,
            "row_count": len(df),
            "local_path": dest,
            "status": "fetched",
        })

        log.info(f"  全市场业绩报表 {date} → {dest} ({len(df)} 家)")
        return dest

    except Exception as e:
        log.error(f"  全市场业绩报表 {date} 失败: {e}")
        return None


def main():
    log = TaskLogger(TASK_NAME)
    log.section("AKShare 公司财务数据获取")
    log.info(f"AKShare 版本: {ak.__version__}")
    log.info(f"股票代码: {STOCK_CODES}")
    log.info(f"获取模式: 财务摘要={FETCH_FINANCIAL_ABSTRACT} 全市场业绩={FETCH_YJBB}")
    log.info("")

    db = FilingDB()
    os.makedirs(STAGING_DIR, exist_ok=True)

    total = 0

    # 主要模式：获取每只股票的财务摘要
    if FETCH_FINANCIAL_ABSTRACT:
        for code in STOCK_CODES:
            log.section(f"处理 {code}")
            result = fetch_financial_abstract(code, log, db)
            if result:
                total += 1

    # 可选：获取全市场业绩报表（用于行业对比）
    if FETCH_YJBB:
        for date in YJBB_DATES:
            path = fetch_yjbb_market(date, log, db)
            if path:
                total += 1

    log.section("Summary")
    log.summary({
        "Task": TASK_NAME,
        "AKShare version": ak.__version__,
        "Stocks processed": len(STOCK_CODES),
        "Files fetched": total,
        "Output directory": STAGING_DIR,
        "Guide file": GUIDE_FILE,
        "Log file": log.log_path,
    })

    log.info("下一步: 数据入库 → knowledge/company/raw/ + entries/ + 更新 INDEX.md & SUMMARY.md")
    log.info("提示: 修改 pipeline/tasks/akshare_financial_guide.json 调整股票代码")


if __name__ == "__main__":
    main()
