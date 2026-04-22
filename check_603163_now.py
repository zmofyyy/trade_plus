# -*- coding: utf-8 -*-
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from trade_plus.backtest.utils import TdxDataLoader
from datetime import datetime

TDX_VIPDOC_PATH = r'D:\new_tdx\vipdoc'
loader = TdxDataLoader(vipdoc_path=TDX_VIPDOC_PATH)
bars = loader.load_daily_bars(code='603163', market='sh', start_date=datetime(2024,1,1), end_date=datetime(2026,4,22))

prices = [b.close_price for b in bars]
highs = [b.high_price for b in bars]
lows = [b.low_price for b in bars]
volumes = [b.volume for b in bars]

def calc_ma(prices, window):
    result = []
    for i in range(window - 1, len(prices)):
        ma = sum(prices[i-window+1:i+1]) / window
        result.append((i, ma))
    return result

ma5 = calc_ma(prices, 5)
ma10 = calc_ma(prices, 10)
ma20 = calc_ma(prices, 20)
ma60 = calc_ma(prices, 60)
ma120 = calc_ma(prices, 120)
ma250 = calc_ma(prices, 250)

ma5_d = {idx: ma for idx, ma in ma5}
ma10_d = {idx: ma for idx, ma in ma10}
ma20_d = {idx: ma for idx, ma in ma20}
ma60_d = {idx: ma for idx, ma in ma60}
ma120_d = {idx: ma for idx, ma in ma120}
ma250_d = {idx: ma for idx, ma in ma250}

n = len(prices)
last = n - 1
price = prices[last]
date = bars[last].datetime.date()

print('=' * 55)
print(f'603163 当前状态分析 (数据更新至 {date})')
print('=' * 55)

print(f'\n当前价格: {price:.2f}')

print('\n【均线位置】')
pct_250 = price / ma250_d[last] * 100 - 100
pct_120 = price / ma120_d[last] * 100 - 100
pct_60 = price / ma60_d[last] * 100 - 100
pct_20 = price / ma20_d[last] * 100 - 100
print(f'  MA250 = {ma250_d[last]:.2f}  (价格比MA250高 {pct_250:+.1f}%)')
print(f'  MA120 = {ma120_d[last]:.2f}  (价格比MA120高 {pct_120:+.1f}%)')
print(f'  MA60  = {ma60_d[last]:.2f}  (价格{'高于' if price > ma60_d[last] else '低于'} MA60 {abs(pct_60):.1f}%)')
print(f'  MA20  = {ma20_d[last]:.2f}  (价格{'高于' if price > ma20_d[last] else '低于'} MA20 {abs(pct_20):.1f}%)')
print(f'  MA10  = {ma10_d[last]:.2f}')
print(f'  MA5   = {ma5_d[last]:.2f}')

print('\n【均线排列状态】')
arr_status = []
if ma5_d[last] > ma10_d[last]: arr_status.append('MA5>MA10')
else: arr_status.append('MA5<MA10')
if ma10_d[last] > ma20_d[last]: arr_status.append('MA10>MA20')
else: arr_status.append('MA10<MA20')
if ma20_d[last] > ma60_d[last]: arr_status.append('MA20>MA60')
else: arr_status.append('MA20<MA60')
if ma60_d[last] > ma120_d[last]: arr_status.append('MA60>MA120')
else: arr_status.append('MA60<MA120')
if ma120_d[last] > ma250_d[last]: arr_status.append('MA120>MA250')
else: arr_status.append('MA120<MA250')
print('  ' + ' > '.join(['']))

# Detailed alignment
print(f'\n  MA5={ma5_d[last]:.0f} > MA10={ma10_d[last]:.0f} > MA20={ma20_d[last]:.0f} > MA60={ma60_d[last]:.0f} > MA120={ma120_d[last]:.0f} > MA250={ma250_d[last]:.0f}')

if price > ma250_d[last] and price > ma120_d[last] and price > ma60_d[last] and price > ma20_d[last]:
    print('  状态: 所有均线呈多头排列，长期上升趋势')
elif price > ma250_d[last] and ma20_d[last] > ma60_d[last]:
    print('  状态: 短期回调，但长期仍在上行')
elif price < ma20_d[last]:
    print('  状态: 跌破短期均线，短期偏弱')
else:
    print('  状态: 震荡整理')

print('\n【趋势斜率】')
slope_120 = (ma120[-1][1] - ma120[-120][1]) / ma120[-120][1] * 100 if len(ma120) >= 120 else 0
slope_250 = (ma250[-1][1] - ma250[-60][1]) / ma250[-60][1] * 100 if len(ma250) >= 60 else 0
slope_60 = (ma60[-1][1] - ma60[-60][1]) / ma60[-60][1] * 100 if len(ma60) >= 60 else 0

slope_comment_120 = '强势' if slope_120 > 20 else '偏弱' if slope_120 < 10 else '正常'
slope_comment_250 = '上升中' if slope_250 > 5 else '走平' if slope_250 > 2 else '下降'

print(f'  MA120斜率(年化): {slope_120:+.1f}%  ({slope_comment_120})')
print(f'  MA250斜率(年化): {slope_250:+.1f}%  ({slope_comment_250})')
print(f'  MA60斜率(年化):  {slope_60:+.1f}%')

print('\n【近期表现】')
for p, label in [(5, '近5日'), (10, '近10日'), (20, '近20日'), (60, '近60日')]:
    if n > p:
        chg = (prices[-1] - prices[-p-1]) / prices[-p-1] * 100
        print(f'  {label}: {chg:+.1f}%')

print('\n【成交量】')
avg_v = sum(volumes[-20:]) / 20
vol_r = volumes[-1] / avg_v
print(f'  今日: {volumes[-1]:,.0f}')
print(f'  20日均量: {avg_v:,.0f}')
print(f'  量比: {vol_r:.2f}x')

print('\n【52周位置】')
high_52w = max(highs[-252:]) if len(highs) >= 252 else max(highs)
low_52w = min(lows[-252:]) if len(lows) >= 252 else min(lows)
pos = (price - low_52w) / (high_52w - low_52w) * 100
up_from_low = (price - low_52w) / low_52w * 100
print(f'  52周最高: {high_52w:.2f}')
print(f'  52周最低: {low_52w:.2f}')
print(f'  当前位置: {pos:.1f}% 百分位')
print(f'  从低点上涨: {up_from_low:.1f}%')

print('\n【短期信号】')
days_above_250 = 0
for k in range(last, max(last-20, -1), -1):
    if prices[k] > ma250_d.get(k, 0):
        days_above_250 += 1
    else:
        break
print(f'  连续{days_above_250}日在MA250上方')

if last >= 1:
    cross_up = ma10_d[last] > ma20_d[last] and ma10_d[last-1] <= ma20_d.get(last-1, 0)
    cross_dn = ma10_d[last] < ma20_d[last] and ma10_d[last-1] >= ma20_d.get(last-1, 0)
    if cross_up:
        print('  MA10上穿MA20 - 短期买入信号')
    elif cross_dn:
        print('  MA10下穿MA20 - 短期卖出信号')
    else:
        print('  MA10/MA20无交叉')

print('\n' + '=' * 55)
print('【综合判断】')
print('=' * 55)

signals = []
risks = []

# Trend check
if slope_120 > 20 and slope_250 > 5:
    signals.append('中长期趋势强势(MA120斜率{:.0f}%, MA250斜率{:.0f}%)'.format(slope_120, slope_250))

# Position check
if pos < 70:
    signals.append('当前位置适中({:.0f}%), 未接近高点'.format(pos))
elif pos > 90:
    risks.append('接近52周高点, 可能有回调压力')

# MA check
if price > ma250_d[last] and price > ma120_d[last]:
    signals.append('价格位于MA250和MA120上方, 上升趋势未变')
elif price < ma120_d[last]:
    risks.append('价格跌破MA120, 可能进入中期调整')

if price > ma60_d[last] and price < ma20_d[last]:
    risks.append('价格跌破MA20但仍在MA60上方, 短期偏弱')

# Volume check
if vol_r < 0.5:
    risks.append('成交量萎缩至均量的{:.0f}%, 上涨动力不足'.format(vol_r*100))
elif vol_r > 1.5:
    signals.append('成交量放大(量比{:.1f}x), 趋势可能延续'.format(vol_r))

# MA crossover
if last >= 1:
    if ma10_d[last] > ma20_d[last] and ma10_d[last-1] <= ma20_d.get(last-1, 0):
        signals.append('MA10金叉MA20, 短期买入信号')
    elif ma10_d[last] < ma20_d[last] and ma10_d[last-1] >= ma20_d.get(last-1, 0):
        risks.append('MA10死叉MA20, 短期卖出信号')

# Recent performance
recent_5d = (prices[-1] - prices[-6]) / prices[-6] * 100 if n > 5 else 0
if recent_5d < -5:
    risks.append('短期回调较大(近5日{:.1f}%)'.format(recent_5d))

print()
for s in signals:
    print(f'  + {s}')
for r in risks:
    print(f'  ! {r}')

print()
print('【结论】')
if len(signals) >= 3 and len(risks) <= 1:
    print('  适合买入 - 趋势强势，信号积极，注意回调风险')
elif len(signals) >= 2 and len(risks) <= 2:
    print('  谨慎买入 - 趋势良好，但需注意短期波动')
elif len(risks) >= 3:
    print('  不建议买入 - 风险因素较多，建议观望')
else:
    print('  中性观望 - 多空因素均衡，等待更明确信号')