# -*- coding: utf-8 -*-
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import argparse
from trade_plus.backtest import BacktestEngine
from trade_plus.backtest.strategies import MaMultiBreakoutStrategy
from trade_plus.backtest.utils import TdxDataLoader
from datetime import datetime
import statistics

TDX_VIPDOC_PATH = r'D:\new_tdx\vipdoc'
START_DATE = datetime(2024, 1, 1)
END_DATE = datetime(2025, 12, 31)

def calc_ma(prices, window):
    result = []
    for i in range(window - 1, len(prices)):
        ma = sum(prices[i-window+1:i+1]) / window
        result.append((i, ma))
    return result

def analyze_stock(code, market='sh'):
    loader = TdxDataLoader(vipdoc_path=TDX_VIPDOC_PATH)
    bars = loader.load_daily_bars(code=code, market=market, start_date=START_DATE, end_date=END_DATE)

    if len(bars) < 100:
        print(f'数据不足，仅 {len(bars)} 根K线')
        return

    print(f'股票代码: {code} (市场: {market})')
    print(f'数据范围: {bars[0].datetime.date()} ~ {bars[-1].datetime.date()}, 共 {len(bars)} 根日线')
    print(f'首日收盘: {bars[0].close_price:.2f}, 末日收盘: {bars[-1].close_price:.2f}')
    print('=' * 60)

    vt_symbol = f'{code}.SSE' if market == 'sh' else f'{code}.SZSE'

    engine = (
        BacktestEngine(initial_capital=500_000.0)
        .set_symbols([vt_symbol])
        .set_period(bars[0].datetime, bars[-1].datetime)
        .add_contract(vt_symbol, size=100, long_rate=0.0003, short_rate=0.0003, pricetick=0.01)
        .set_data(vt_symbol, bars)
    )
    engine.use_strategy(MaMultiBreakoutStrategy, setting={'ma20_window': 20, 'ma250_window': 250, 'position_pct': 0.15})
    engine.run()
    trades = engine.get_trades()

    prices = [b.close_price for b in bars]
    ma20 = calc_ma(prices, 20)
    ma60 = calc_ma(prices, 60)
    ma120 = calc_ma(prices, 120)
    ma250 = calc_ma(prices, 250)

    ma20_dict = {idx: ma for idx, ma in ma20}
    ma60_dict = {idx: ma for idx, ma in ma60}
    ma120_dict = {idx: ma for idx, ma in ma120}
    ma250_dict = {idx: ma for idx, ma in ma250}

    n = len(prices)
    above_ma20 = sum(1 for i in range(n) if i in ma20_dict and prices[i] > ma20_dict[i]) / len(ma20_dict) * 100 if ma20_dict else 0
    above_ma60 = sum(1 for i in range(n) if i in ma60_dict and prices[i] > ma60_dict[i]) / len(ma60_dict) * 100 if ma60_dict else 0
    above_ma120 = sum(1 for i in range(n) if i in ma120_dict and prices[i] > ma120_dict[i]) / len(ma120_dict) * 100 if ma120_dict else 0
    above_ma250 = sum(1 for i in range(n) if i in ma250_dict and prices[i] > ma250_dict[i]) / len(ma250_dict) * 100 if ma250_dict else 0

    slope_ma20 = (ma20[-1][1] - ma20[-20][1]) / ma20[-20][1] * 100 if len(ma20) >= 20 else 0
    slope_ma60 = (ma60[-1][1] - ma60[-min(60, len(ma60))][1]) / ma60[-min(60, len(ma60))][1] * 100 if len(ma60) >= 2 else 0
    slope_ma120 = (ma120[-1][1] - ma120[-min(120, len(ma120))][1]) / ma120[-min(120, len(ma120))][1] * 100 if len(ma120) >= 2 else 0
    slope_ma250 = (ma250[-1][1] - ma250[-min(60, len(ma250))][1]) / ma250[-min(60, len(ma250))][1] * 100 if len(ma250) >= 2 else 0

    returns = [(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, len(prices)) if prices[i-1] > 0]
    volatility = statistics.stdev(returns) * 100 if len(returns) >= 2 else 0
    total_return = (prices[-1] - prices[0]) / prices[0] * 100
    price_range = (max(prices) - min(prices)) / min(prices) * 100

    print('\n【趋势特征】')
    print(f'  MA20 斜率(年化):   {slope_ma20:+.1f}%')
    print(f'  MA60 斜率(年化):   {slope_ma60:+.1f}%')
    print(f'  MA120 斜率(年化):  {slope_ma120:+.1f}%')
    print(f'  MA250 斜率(年化):  {slope_ma250:+.1f}%')
    print(f'  股价在 MA20 上方:  {above_ma20:.1f}%')
    print(f'  股价在 MA60 上方:  {above_ma60:.1f}%')
    print(f'  股价在 MA120 上方: {above_ma120:.1f}%')
    print(f'  股价在 MA250 上方: {above_ma250:.1f}%')
    print(f'  区间总收益:        {total_return:+.1f}%')
    print(f'  日波动率:          {volatility:.2f}%')
    print(f'  区间振幅:          {price_range:.1f}%')

    if not trades:
        print('\n【交易结果】 无交易')
        return

    pnls = []
    for i in range(0, len(trades) - 1, 2):
        if i + 1 >= len(trades):
            break
        entry = trades[i]
        exit_trade = trades[i + 1]
        if entry.offset.value in ['open', 'none'] and exit_trade.offset.value == 'close':
            pnl = (exit_trade.price - entry.price) * entry.volume * 100
            pnl -= entry.price * entry.volume * 100 * 0.0003
            pnl -= exit_trade.price * exit_trade.volume * 100 * 0.0003
            pnls.append({'entry': entry.price, 'exit': exit_trade.price, 'pnl': pnl, 'vol': entry.volume, 'entry_date': entry.datetime.date(), 'exit_date': exit_trade.datetime.date()})

    if not pnls:
        print('\n【交易结果】 无有效交易')
        return

    wins = [p for p in pnls if p['pnl'] > 0]
    losses = [p for p in pnls if p['pnl'] < 0]
    win_rate = len(wins) / len(pnls) * 100
    total_pnl = sum(p['pnl'] for p in pnls)
    avg_win = sum(p['pnl'] for p in wins) / len(wins) if wins else 0
    avg_loss = abs(sum(p['pnl'] for p in losses) / len(losses)) if losses else 0
    pl_ratio = avg_win / avg_loss if avg_loss > 0 else float('inf')

    print(f'\n【交易结果】 共 {len(pnls)} 笔交易')
    print(f'  胜率:   {win_rate:.1f}%')
    print(f'  总盈亏: {total_pnl:+.0f} 元')
    if wins:
        print(f'  盈利交易: {len(wins)} 笔, 平均 +{avg_win:.0f} 元')
    if losses:
        print(f'  亏损交易: {len(losses)} 笔, 平均 -{avg_loss:.0f} 元')
    if avg_loss > 0:
        print(f'  盈亏比:   {pl_ratio:.1f}:1')

    print('\n【逐笔明细】')
    print(f'  {"序号":<4} {"入场日期":<12} {"入场价":<8} {"出场日期":<12} {"出场价":<8} {"手数":<6} {"盈亏":<10}')
    print('  ' + '-' * 70)
    for j, p in enumerate(pnls):
        status = '+' if p['pnl'] > 0 else ''
        print(f'  {j+1:<4} {str(p["entry_date"]):<12} {p["entry"]:<8.2f} {str(p["exit_date"]):<12} {p["exit"]:<8.2f} {p["vol"]:<6.0f} {status}{p["pnl"]:.0f} 元')

    print('\n【综合评价】')
    scores = []
    comments = []

    if slope_ma120 >= 20:
        scores.append('优')
        comments.append(f'MA120斜率{slope_ma120:+.1f}%强势')
    elif slope_ma120 >= 10:
        scores.append('良')
        comments.append(f'MA120斜率{slope_ma120:+.1f}%尚可')
    else:
        scores.append('差')
        comments.append(f'MA120斜率{slope_ma120:+.1f}%偏弱')

    if slope_ma250 >= 5:
        scores.append('优')
        comments.append(f'MA250斜率{slope_ma250:+.1f}%上升中')
    elif slope_ma250 >= 2:
        scores.append('良')
        comments.append(f'MA250斜率{slope_ma250:+.1f}%走平')
    else:
        scores.append('差')
        comments.append(f'MA250斜率{slope_ma250:+.1f}%下降')

    if win_rate >= 60:
        scores.append('优')
        comments.append(f'胜率{win_rate:.1f}%优秀')
    elif win_rate >= 50:
        scores.append('良')
        comments.append(f'胜率{win_rate:.1f}%中等')
    else:
        scores.append('差')
        comments.append(f'胜率{win_rate:.1f}%偏低')

    if total_pnl > 20000:
        scores.append('优')
        comments.append(f'盈利{total_pnl:.0f}元')
    elif total_pnl > 0:
        scores.append('良')
        comments.append(f'盈利{total_pnl:.0f}元')
    else:
        scores.append('差')
        comments.append(f'亏损{total_pnl:.0f}元')

    excellent = scores.count('优')
    good = scores.count('良')
    poor = scores.count('差')

    for c in comments:
        print(f'  - {c}')

    print(f'\n  综合评级: {"★★★★★" if excellent >= 4 else "★★★★☆" if excellent >= 3 else "★★★☆☆" if good >= 3 else "★★☆☆☆" if good >= 2 else "★☆☆☆☆"}')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='股票策略回测分析')
    parser.add_argument('code', help='股票代码 (如: 605068)')
    parser.add_argument('-m', '--market', default='sh', choices=['sh', 'sz'], help='市场: sh 或 sz (默认: sh)')
    args = parser.parse_args()

    analyze_stock(args.code, args.market)