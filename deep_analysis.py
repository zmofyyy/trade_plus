# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
os.environ['PYTDX Suppress_Warnings'] = '1'

from datetime import datetime
from trade_plus.backtest.utils import TdxDataLoader

TDX_VIPDOC_PATH = r'D:\new_tdx\vipdoc'

TOP_STOCKS = [
    ('603558', 'sh'), ('300483', 'sz'), ('300737', 'sz'),
    ('600686', 'sh'), ('600328', 'sh'), ('000722', 'sz'),
    ('601330', 'sh'), ('601858', 'sh'), ('300279', 'sz'),
    ('600481', 'sh'),
]

def calc_ma(prices, window):
    if len(prices) < window:
        return None
    return sum(prices[-window:]) / window

def ma_direction(prices, window):
    """MA方向：近window日MA值的变化百分比（未年化，更直观）"""
    if len(prices) < window * 2:
        return None
    ma_now = calc_ma(prices, window)
    ma_then = calc_ma(prices[:-window+1], window) if len(prices) >= window * 2 - 1 else None
    if ma_now is None or ma_then is None or ma_then == 0:
        return None
    return (ma_now - ma_then) / ma_then * 100

def volume_ratio(bars, lookback=20):
    vols = [b.volume for b in bars]
    if len(vols) < lookback * 2:
        return None
    recent = sum(vols[-lookback:]) / lookback
    prev = sum(vols[-(lookback*2):-lookback]) / lookback
    return recent / prev if prev > 0 else None

loader = TdxDataLoader(vipdoc_path=TDX_VIPDOC_PATH)

print("=" * 70)
print("Top10 MA20突破股 — 状态深度分析")
print("=" * 70)

for code, market in TOP_STOCKS:
    try:
        bars = loader.load_daily_bars(
            code=code, market=market,
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2026, 4, 22)
        )
        if len(bars) < 250:
            continue

        prices = [b.close_price for b in bars]
        last = prices[-1]

        ma5  = calc_ma(prices, 5)
        ma20 = calc_ma(prices, 20)
        ma60 = calc_ma(prices, 60)
        ma120 = calc_ma(prices, 120)
        ma250 = calc_ma(prices, 250)

        # MA方向：近20/60/120日的MA值变化
        d20  = ma_direction(prices, 20)
        d60  = ma_direction(prices, 60)
        d120 = ma_direction(prices, 120)

        # 位置
        pos250 = (last - ma250) / ma250 * 100
        pos120 = (last - ma120) / ma120 * 100

        # 52周位置
        high52 = max(prices[-252:])
        low52 = min(prices[-252:])
        pos52 = (last - low52) / (high52 - low52) * 100

        # 成交量
        vr = volume_ratio(bars)
        gain5  = (last - prices[-6]) / prices[-6] * 100
        gain20 = (last - prices[-21]) / prices[-21] * 100

        # 均线多头排列
        ma_order = ma5 > ma20 > ma60 > ma120 > ma250
        ma_bearish = ma5 < ma20 < ma60 < ma120 < ma250
        ma_mixed = not ma_order and not ma_bearish

        print(f"\n{'─'*60}")
        print(f"【{code} {market}】收盘价 {last:.2f}")

        # 均线值
        print(f"  均线: MA5={ma5:.2f}  MA20={ma20:.2f}  MA60={ma60:.2f}  MA120={ma120:.2f}  MA250={ma250:.2f}")
        print(f"  均线方向(近20/60/120日变化): MA20{d20:+.1f}%  MA60{d60:+.1f}%  MA120{d120:+.1f}%")
        print(f"  位置: 偏离MA250={pos250:+.1f}%  偏离MA120={pos120:+.1f}%  52周位置={pos52:.0f}%")
        print(f"  动量: 5日{gain5:+.1f}%  20日{gain20:+.1f}%")
        print(f"  量比(近20日/前20日): {vr:.2f}" if vr else "  量比: N/A")

        # 趋势结构
        if ma_order:
            print(f"  ✅ 多头排列: MA5>MA20>MA60>MA120>MA250")
        elif ma_bearish:
            print(f"  ❌ 空头排列: MA5<MA20<MA60<MA120<MA250")
        else:
            print(f"  ⚠️  混合结构", end="")
            issues = []
            if ma5 < ma20: issues.append("MA5<MA20(短期回调)")
            if ma20 < ma60: issues.append("MA20<MA60(中期回调)")
            if ma60 < ma120: issues.append("MA60<MA120(中期偏弱)")
            if issues:
                print(" — " + " | ".join(issues))
            else:
                print()

        # 综合判断
        score = 0
        reasons = []
        if d120 and d120 > 10: score += 3; reasons.append("MA120趋势强")
        elif d120 and d120 < 0: score -= 2; reasons.append("MA120下行")
        if d60 and d60 > 5: score += 2; reasons.append("MA60向上")
        elif d60 and d60 < -10: score -= 1; reasons.append("MA60下行")
        if ma_order: score += 3; reasons.append("多头排列")
        elif ma_mixed: score += 0
        if vr and vr > 1.2: score += 1; reasons.append("量价配合")
        if pos52 and 30 < pos52 < 85: score += 1; reasons.append("52周位置适中")
        if gain5 > 5: score += 1; reasons.append("短期动能充足")
        if gain5 > 12: score -= 1; reasons.append("短期可能过热")

        verdict = "🟢 强" if score >= 7 else "🟡 中" if score >= 4 else "🔴 弱"
        print(f"  综合: {verdict} (分数: {score}/9)  {'|'.join(reasons) if reasons else '无明显优势'}")

    except Exception as e:
        print(f"\n{code} Error: {e}")