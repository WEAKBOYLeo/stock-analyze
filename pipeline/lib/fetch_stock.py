#!/usr/bin/env python3
"""
股票数据一键获取 — 整合 annual_report_crawler + AKShare pipeline。

用法:
    python pipeline/lib/fetch_stock.py <股票代码> [年份范围] [--skip-pdf] [--skip-financial]

示例:
    python pipeline/lib/fetch_stock.py 600169                        # 默认近5年
    python pipeline/lib/fetch_stock.py 600519 2020-2025               # 指定年份范围
    python pipeline/lib/fetch_stock.py 000001 --skip-pdf              # 跳过PDF下载
    python pipeline/lib/fetch_stock.py 300750 2018,2019,2020,2021,2022  # 不连续年份

输出:
    - 年报 PDF → knowledge/company/raw/
    - 财务摘要 CSV → pipeline/staging/akshare/financial/
    - 公司信息 JSON/CSV → pipeline/staging/akshare/company/
    - 执行日志 → pipeline/logs/
"""

import sys
import os
import json
import subprocess
import shutil
from pathlib import Path
from datetime import datetime

# 项目根目录
ROOT = Path(__file__).resolve().parent.parent.parent
CRAWLER_DIR = ROOT / "annual_report_crawler"
CRAWLER_V1 = CRAWLER_DIR / "v1"
PIPELINE_DIR = ROOT / "pipeline"
STAGING_FIN = PIPELINE_DIR / "staging" / "akshare" / "financial"
STAGING_CO = PIPELINE_DIR / "staging" / "akshare" / "company"
KNOWLEDGE_RAW = ROOT / "knowledge" / "company" / "raw"
TASKS_DIR = PIPELINE_DIR / "tasks"

sys.path.insert(0, str(PIPELINE_DIR))


def parse_years(year_str: str) -> list:
    """解析年份字符串: '2020-2025', '2020,2021,2022', '2020'"""
    years = []
    if '-' in year_str:
        start, end = year_str.split('-')
        years = list(range(int(start), int(end) + 1))
    elif ',' in year_str:
        years = [int(y.strip()) for y in year_str.split(',')]
    else:
        years = [int(year_str)]
    return years


def identify_market(code: str) -> str:
    """识别股票市场"""
    if code.isdigit():
        if len(code) == 6:
            if code.startswith(('600', '601', '603', '605', '000', '001', '002')):
                return 'A股主板'
            elif code.startswith('688'):
                return 'A股科创板'
            elif code.startswith('300'):
                return 'A股创业板'
            return 'A股'
        elif len(code) == 5:
            return '港股'
    elif code.isalpha() and 1 <= len(code) <= 5:
        return '美股'
    return '未知'


def run_cmd(cmd: list, cwd=None, env=None) -> tuple:
    """运行命令，返回 (returncode, stdout, stderr)"""
    result = subprocess.run(cmd, cwd=cwd or ROOT, capture_output=True, text=True, env=env or os.environ)
    return result.returncode, result.stdout, result.stderr


def step1_download_pdfs(code: str, years: list, market: str) -> list:
    """Step 1: 通过 annual_report_crawler 下载年报 PDF"""
    print(f"\n{'='*60}")
    print(f"Step 1/3: 下载年报 PDF — {code} ({market})")
    print(f"{'='*60}")

    year_str = f"{min(years)}-{max(years)}"
    download_dir = CRAWLER_DIR / "annual_reports"
    download_dir.mkdir(exist_ok=True)

    # A股主板优先用 Requests 模式；科创板/创业板/港股用 WebDriver 模式
    if market in ('A股主板', 'A股'):
        script = CRAWLER_V1 / "annual_report_downloader_rq.py"
    else:
        script = CRAWLER_V1 / "annual_report_downloader_bd.py"

    if not script.exists():
        print(f"  ✗ 下载脚本不存在: {script}")
        return []

    print(f"  模式: {'Requests (Hanae)' if 'rq' in script.name else 'WebDriver (Shio)'}")
    print(f"  年份: {year_str}")

    ret, stdout, stderr = run_cmd(
        ["python", str(script), "-s", code, "-y", year_str, "-d", str(download_dir)],
        cwd=str(CRAWLER_V1)
    )

    print(stdout)
    if stderr:
        print(f"  [stderr]: {stderr[:500]}")

    # 查找下载的 PDF
    pdfs = []
    for pattern in [f"{code}_*", f"*_{code}_*"]:
        for f in download_dir.glob(pattern):
            if f.suffix.lower() in ('.pdf', '.html'):
                pdfs.append(f)

    if pdfs:
        print(f"  ✓ 下载了 {len(pdfs)} 个文件:")
        for p in pdfs:
            print(f"    - {p.name}")
    else:
        print(f"  ⚠ 未找到下载的 PDF 文件（可能是首次运行或下载失败）")
        # 列出目录中所有文件帮助诊断
        all_files = list(download_dir.iterdir())
        if all_files:
            print(f"  目录内容 ({len(all_files)} 个文件):")
            for f in all_files:
                print(f"    - {f.name}")

    return pdfs


def step2_fetch_financial(code: str) -> dict:
    """Step 2: 通过 AKShare pipeline 获取财务数据 + 公司信息"""
    print(f"\n{'='*60}")
    print(f"Step 2/3: 获取财务数据与公司信息 — {code}")
    print(f"{'='*60}")

    results = {}

    # 确保 tasks 目录存在
    TASKS_DIR.mkdir(exist_ok=True)

    # --- 财务摘要 ---
    print("\n  [2a] 获取财务摘要 (stock_financial_abstract)...")
    try:
        import akshare as ak
        import pandas as pd

        print(f"    AKShare 版本: {ak.__version__}")

        df = ak.stock_financial_abstract(symbol=code)
        if df is not None and not df.empty:
            STAGING_FIN.mkdir(parents=True, exist_ok=True)
            dest = STAGING_FIN / f"{code}_financial_abstract.csv"
            df.to_csv(dest, index=False, encoding="utf-8-sig")
            results['financial_csv'] = str(dest)

            # 提取关键年报数据
            annual_cols = [c for c in df.columns if str(c).endswith('1231')]
            annual_dates = sorted(annual_cols, reverse=True)

            print(f"    ✓ 指标数: {len(df)} | 年报数: {len(annual_dates)}")
            if annual_dates:
                latest = annual_dates[0]
                key_metrics = ['归母净利润', '营业总收入', '净资产收益率(ROE)', '毛利率', '资产负债率']
                print(f"    最新年报 ({latest[:4]}):")
                for metric in key_metrics:
                    row = df[df.iloc[:, 1] == metric]
                    if not row.empty:
                        val = row.iloc[0][latest]
                        try:
                            v = float(val)
                            if metric == '营业总收入' or metric == '归母净利润':
                                print(f"      {metric}: {v/1e8:.2f}亿")
                            elif metric in ('净资产收益率(ROE)', '毛利率', '资产负债率'):
                                print(f"      {metric}: {v:.2f}%")
                            else:
                                print(f"      {metric}: {v}")
                        except (ValueError, TypeError):
                            print(f"      {metric}: {val}")
        else:
            print(f"    ⚠ 财务摘要返回空（可能代码错误或已退市）")
    except ImportError:
        print(f"    ✗ 请安装 AKShare: pip install akshare pandas")
    except Exception as e:
        print(f"    ✗ 财务摘要获取失败: {e}")

    # --- 公司基本信息 ---
    print("\n  [2b] 获取公司基本信息...")
    try:
        import akshare as ak
        info = ak.stock_individual_info_em(symbol=code)
        if info is not None and not info.empty:
            STAGING_CO.mkdir(parents=True, exist_ok=True)
            dest = STAGING_CO / f"{code}_info.json"
            info_dict = {}
            for _, row in info.iterrows():
                info_dict[str(row.iloc[0])] = str(row.iloc[1]) if len(row) > 1 else ""
            with open(dest, "w", encoding="utf-8") as f:
                json.dump(info_dict, f, indent=2, ensure_ascii=False)
            results['company_info'] = str(dest)
            for key in ["股票简称", "总市值", "行业", "上市时间", "总股本"]:
                if key in info_dict:
                    print(f"    {key}: {info_dict[key]}")
        else:
            print(f"    ⚠ 公司信息返回空")
    except Exception as e:
        print(f"    ⚠ 公司信息获取失败: {e}")

    # --- 估值对比 ---
    print("\n  [2c] 获取估值同行对比...")
    try:
        import akshare as ak
        val = ak.stock_zh_valuation_comparison_em(symbol=code)
        if val is not None and not val.empty:
            dest = STAGING_CO / f"{code}_valuation.csv"
            val.to_csv(dest, index=False, encoding="utf-8-sig")
            results['valuation'] = str(dest)
            print(f"    ✓ 估值对比: {len(val)} 个同行")
    except Exception as e:
        print(f"    ⚠ 估值对比获取失败: {e}")

    # --- 成长性对比 ---
    print("\n  [2d] 获取成长性同行对比...")
    try:
        import akshare as ak
        growth = ak.stock_zh_growth_comparison_em(symbol=code)
        if growth is not None and not growth.empty:
            dest = STAGING_CO / f"{code}_growth.csv"
            growth.to_csv(dest, index=False, encoding="utf-8-sig")
            results['growth'] = str(dest)
            print(f"    ✓ 成长性对比: {len(growth)} 个同行")
    except Exception as e:
        print(f"    ⚠ 成长性对比获取失败: {e}")

    return results


def step3_move_to_knowledge(code: str, pdfs: list, company_name: str = None) -> dict:
    """Step 3: 将数据移入 knowledge/ 知识库目录"""
    print(f"\n{'='*60}")
    print(f"Step 3/3: 移入知识库 — {code}")
    print(f"{'='*60}")

    KNOWLEDGE_RAW.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    name = company_name or code
    moved = {}

    # 移动 PDF
    for pdf in pdfs:
        if not pdf.exists():
            continue
        # 尝试从文件名提取年份
        year = ""
        for part in pdf.stem.split('_'):
            if part.isdigit() and len(part) == 4 and 2000 <= int(part) <= 2100:
                year = part
                break

        dest_name = f"{today}_巨潮资讯_{name}_{year}年报.pdf" if year else f"{today}_巨潮资讯_{name}_{pdf.name}"
        dest = KNOWLEDGE_RAW / dest_name
        if not dest.exists():
            shutil.copy2(pdf, dest)
            print(f"  ✓ PDF: {pdf.name} → {dest_name}")
        else:
            print(f"  - PDF: {dest_name} (已存在，跳过)")
        moved[str(pdf)] = str(dest)

    # 移动财务 CSV
    fin_csv = STAGING_FIN / f"{code}_financial_abstract.csv"
    if fin_csv.exists():
        dest_name = f"{today}_东方财富_{name}财务摘要.csv"
        dest = KNOWLEDGE_RAW / dest_name
        shutil.copy2(fin_csv, dest)
        print(f"  ✓ 财务摘要: {fin_csv.name} → {dest_name}")
        moved[str(fin_csv)] = str(dest)

    # 移动公司信息
    info_json = STAGING_CO / f"{code}_info.json"
    if info_json.exists():
        dest_name = f"{today}_东方财富_{name}公司信息.json"
        dest = KNOWLEDGE_RAW / dest_name
        shutil.copy2(info_json, dest)
        print(f"  ✓ 公司信息: {info_json.name} → {dest_name}")
        moved[str(info_json)] = str(dest)

    return moved


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    code = sys.argv[1]
    market = identify_market(code)

    # 默认年份：近5年（不含当前年）
    current_year = datetime.now().year
    default_years = list(range(current_year - 5, current_year))
    years = default_years

    skip_pdf = '--skip-pdf' in sys.argv
    skip_financial = '--skip-financial' in sys.argv

    for arg in sys.argv[2:]:
        if arg.startswith('--'):
            continue
        # 尝试解析为年份
        try:
            years = parse_years(arg)
            break
        except (ValueError, IndexError):
            continue

    print(f"{'='*60}")
    print(f"股票数据一键获取")
    print(f"{'='*60}")
    print(f"  股票代码: {code}")
    print(f"  市场: {market}")
    print(f"  年份: {min(years)}-{max(years)} ({len(years)} 年)")
    print(f"  项目根目录: {ROOT}")

    # Step 1: 下载年报 PDF
    pdfs = []
    if not skip_pdf:
        pdfs = step1_download_pdfs(code, years, market)

    # Step 2: 获取财务数据
    if not skip_financial:
        step2_fetch_financial(code)

    # Step 3: 移入 knowledge/
    moved = step3_move_to_knowledge(code, pdfs)

    # 汇总
    print(f"\n{'='*60}")
    print(f"获取完成 — {code} ({market})")
    print(f"{'='*60}")
    print(f"  PDF: {len([v for k, v in moved.items() if k.endswith('.pdf')])} 个")
    print(f"  数据文件: {len(moved)} 个 → {KNOWLEDGE_RAW}")
    print(f"\n下一步（需 Claude 执行）:")
    print(f"  1. 读取 CSV 提取关键数据 → 创建 knowledge/company/entries/ 条目")
    print(f"  2. 更新 knowledge/company/INDEX.md")
    print(f"  3. 更新 knowledge/company/raw/INDEX.md")
    print(f"  4. 更新 knowledge/company/SUMMARY.md")
    print(f"\n详细流程见: .claude/skills/stock-fetch.md")


if __name__ == "__main__":
    main()
