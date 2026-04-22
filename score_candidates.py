# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
os.environ['PYTDX Suppress_Warnings'] = '1'

from pathlib import Path
from datetime import datetime
from trade_plus.backtest.utils import TdxDataLoader

TDX_VIPDOC_PATH = r'D:\new_tdx\vipdoc'

def calc_ma(prices, window):
    if len(prices) < window:
        return None
    return sum(prices[-window:]) / window

def calc_ma_slope(prices, window):
    if len(prices) < window:
        return None
    recent = prices[-window:]
    if len(recent) < 2:
        return None
    first = recent[0]
    last = recent[-1]
    if first == 0:
        return None
    return (last - first) / first * 100

# Top candidates based on 5-day gain ranking, with balanced entry quality
candidates = [
    ('000722', 'sz'), ('603496', 'sh'), ('002470', 'sz'), ('300030', 'sz'),
    ('601330', 'sh'), ('300901', 'sz'), ('001212', 'sz'), ('600686', 'sh'),
    ('300483', 'sz'), ('600638', 'sh'), ('603558', 'sh'), ('000531', 'sz'),
    ('601858', 'sh'), ('000159', 'sz'), ('002955', 'sz'), ('300737', 'sz'),
    ('300981', 'sz'), ('600328', 'sh'), ('600481', 'sh'), ('300279', 'sz'),
]

loader = TdxDataLoader(vipdoc_path=TDX_VIPDOC_PATH)

results = []
for code, market in candidates:
    try:
        bars = loader.load_daily_bars(
            code=code, market=market,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2026, 4, 22)
        )
        if len(bars) < 250:
            continue

        prices = [b.close_price for b in bars]

        ma20 = calc_ma(prices, 20)
        ma120 = calc_ma(prices, 120)
        ma250 = calc_ma(prices, 250)
        if None in (ma20, ma120, ma250):
            continue

        last_price = prices[-1]
        prev_price = prices[-2]

        cross_up = prev_price <= ma20 and last_price > ma20
        above_ma250 = last_price > ma250

        ma20_dev = (last_price - ma20) / ma20 * 100
        ma250_dev = (last_price - ma250) / ma250 * 100
        gain5 = (last_price - prices[-6]) / prices[-6] * 100 if len(prices) >= 6 else 0

        # MA120 slope as trend strength proxy (annualized from 120-day)
        ma120_slope = (calc_ma_slope(prices, 120) or 0) * (250 / 120)

        if not (cross_up and above_ma250):
            continue

        # Scoring
        ma20_score = 100 if ma20_dev < 2 else 90 if ma20_dev < 4 else 75 if ma20_dev < 6 else 60 if ma20_dev < 10 else 40
        ma250_score = 100 if 10 <= ma250_dev <= 50 else 70 if 5 <= ma250_dev < 10 else 75 if 50 < ma250_dev <= 80 else 50
        gain_score = 100 if 0 <= gain5 <= 8 else 85 if -2 <= gain5 < 0 else 80 if 8 < gain5 <= 12 else 60
        # MA120 slope score: annualized, higher is better
        slope_score = 100 if ma120_slope >= 30 else 90 if ma120_slope >= 20 else 80 if ma120_slope >= 10 else 70 if ma120_slope >= 5 else 50

        total = ma20_score * 0.30 + ma250_score * 0.25 + gain_score * 0.20 + slope_score * 0.25

        results.append({
            'code': code, 'market': market,
            'price': last_price, 'ma20': ma20, 'ma250': ma250,
            'ma20_dev': ma20_dev, 'ma250_dev': ma250_dev,
            'gain5': gain5, 'ma120_slope': ma120_slope,
            'ma20_score': ma20_score, 'ma250_score': ma250_score,
            'gain_score': gain_score, 'slope_score': slope_score,
            'total': round(total, 1),
        })
    except:
        continue

results.sort(key=lambda x: x['total'], reverse=True)

print(f"{'排名':<4} {'代码':<8} {'市场':<4} {'收盘价':<7} {'MA20偏%':<9} {'MA250偏%':<10} {'5日涨%':<9} {'MA120斜%':<9} {'综合分':<6}")
print('-' * 80)
for i, r in enumerate(results[:15], 1):
    print(f"{i:<4} {r['code']:<8} {r['market']:<4} {r['price']:<7.2f} {r['ma20_dev']:>+6.2f}%   {r['ma250_dev']:>+7.2f}%   {r['gain5']:>+6.2f}%   {r['ma120_slope']:>+6.1f}%   {r['total']}")