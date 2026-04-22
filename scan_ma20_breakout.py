# -*- coding: utf-8 -*-
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
import argparse

PROJECT_ROOT = r'F:\source\trade_plus'
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

os.environ['PYTDX Suppress_Warnings'] = '1'

from pathlib import Path
from datetime import datetime
from trade_plus.backtest.utils import TdxDataLoader

TDX_VIPDOC_PATH = r'D:\new_tdx\vipdoc'

def get_stock_codes():
    codes = []
    sh_dir = Path(TDX_VIPDOC_PATH) / "sh" / "lday"
    sz_dir = Path(TDX_VIPDOC_PATH) / "sz" / "lday"
    SH_PATTERNS = ('600', '601', '603', '605', '688')
    SZ_PATTERNS = ('000', '001', '002', '003', '300')
    for f in sh_dir.glob("*.day"):
        code = f.stem[2:]
        if code.startswith(SH_PATTERNS):
            codes.append((code, "sh"))
    for f in sz_dir.glob("*.day"):
        code = f.stem[2:]
        if code.startswith(SZ_PATTERNS):
            codes.append((code, "sz"))
    return codes

def is_valid_stock(code, market):
    """检查股票数据文件是否有效（避免 pytdx 报 Unknown security type）"""
    vipdoc_path = Path(TDX_VIPDOC_PATH)
    if market == 'sh':
        file_path = vipdoc_path / "sh" / "lday" / f"sh{code}.day"
    else:
        file_path = vipdoc_path / "sz" / "lday" / f"sz{code}.day"
    if not file_path.exists():
        return False
    if file_path.stat().st_size < 100:
        return False
    return True

def calc_ma(prices, window):
    if len(prices) < window:
        return None
    return sum(prices[-window:]) / window

def scan_breakout(date=None):
    loader = TdxDataLoader(vipdoc_path=TDX_VIPDOC_PATH)
    codes = get_stock_codes()

    if date is None:
        date = datetime(2026, 4, 22)

    results = []

    for code, market in codes:
        try:
            bars = loader.load_daily_bars(
                code=code,
                market=market,
                start_date=datetime(2025, 1, 1),
                end_date=date
            )

            if len(bars) < 250:
                continue

            prices = [b.close_price for b in bars]
            highs = [b.high_price for b in bars]

            ma20 = calc_ma(prices, 20)
            ma250 = calc_ma(prices, 250)

            if ma20 is None or ma250 is None:
                continue

            last_price = prices[-1]
            prev_price = prices[-2] if len(prices) >= 2 else None

            if prev_price is None:
                continue

            # 今日收盘价上穿MA20（前一日在MA20下方或相等，今日在MA20上方）
            cross_up = prev_price <= ma20 and last_price > ma20
            # 股价在MA250上方
            above_ma250 = last_price > ma250

            # 入场条件：收盘价上穿MA20 且 股价在MA250上方
            if cross_up and above_ma250:
                last_date = bars[-1].datetime.date()
                pct_above_ma20 = (last_price - ma20) / ma20 * 100
                pct_above_ma250 = (last_price - ma250) / ma250 * 100

                # 计算近5日涨幅
                if len(prices) >= 6:
                    gain_5d = (last_price - prices[-6]) / prices[-6] * 100
                else:
                    gain_5d = 0

                results.append({
                    'code': code,
                    'market': market,
                    'last_date': last_date,
                    'last_price': last_price,
                    'ma20': ma20,
                    'ma250': ma250,
                    'pct_above_ma20': pct_above_ma20,
                    'pct_above_ma250': pct_above_ma250,
                    'gain_5d': gain_5d,
                })

        except Exception as e:
            continue

    return results

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='扫描MA20突破股票')
    parser.add_argument('--date', help='截止日期 YYYY-MM-DD（默认: 2026-04-22）')
    args = parser.parse_args()

    scan_date = datetime.strptime(args.date, '%Y-%m-%d') if args.date else datetime(2026, 4, 22)

    print(f'扫描日期: {scan_date.date()}')
    print(f'扫描范围: 600/601/603/605/688 开头（沪市）、000/001/002/003/300 开头（深市）')
    print('筛选条件: 收盘价上穿MA20 且 股价在MA250上方')
    print()
    print('正在扫描...')

    results = scan_breakout(scan_date)

    print(f'\n共找到 {len(results)} 只符合条件股票')
    print()

    if results:
        print(f'{"代码":<10} {"市场":<6} {"日期":<12} {"收盘价":<8} {"MA20":<8} {"MA250":<8} {"偏离MA20":<10} {"偏离MA250":<10} {"5日涨幅":<10}')
        print('-' * 95)
        for r in sorted(results, key=lambda x: x['gain_5d'], reverse=True):
            print(f'{r["code"]:<10} {r["market"]:<6} {str(r["last_date"]):<12} {r["last_price"]:<8.2f} {r["ma20"]:<8.2f} {r["ma250"]:<8.2f} {r["pct_above_ma20"]:>+7.2f}%   {r["pct_above_ma250"]:>+7.2f}%   {r["gain_5d"]:>+7.2f}%')
    else:
        print('未找到符合条件的股票')