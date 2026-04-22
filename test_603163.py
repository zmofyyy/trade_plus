# -*- coding: utf-8 -*-
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from trade_plus.backtest import BacktestEngine
from trade_plus.backtest.strategies import MaMultiBreakoutStrategy
from trade_plus.backtest.utils import TdxDataLoader
from datetime import datetime
import statistics

TDX_VIPDOC_PATH = r'D:\new_tdx\vipdoc'
START_DATE = datetime(2024, 1, 1)
END_DATE = datetime(2025, 12, 31)

code = '603163'
market = 'sh'
loader = TdxDataLoader(vipdoc_path=TDX_VIPDOC_PATH)
bars = loader.load_daily_bars(code=code, market=market, start_date=START_DATE, end_date=END_DATE)
print(f'Loaded {len(bars)} bars for {code}')
print(f'First: {bars[0].datetime.date()}, close={bars[0].close_price:.2f}')
print(f'Last: {bars[-1].datetime.date()}, close={bars[-1].close_price:.2f}')

vt_symbol = f'{code}.SSE'
engine = (
    BacktestEngine(initial_capital=500_000.0)
    .set_symbols([vt_symbol])
    .set_period(bars[0].datetime, bars[-1].datetime)
    .add_contract(vt_symbol, size=100, long_rate=0.0003, short_rate=0.0003, pricetick=0.01)
    .set_data(vt_symbol, bars)
)
engine.use_strategy(MaMultiBreakoutStrategy, setting={'ma20_window': 20, 'ma250_window': 250, 'position_pct': 0.15})
stats = engine.run()
trades = engine.get_trades()
print(f'\nTrades: {len(trades)}')

prices = [b.close_price for b in bars]

def calc_ma(prices, window):
    result = []
    for i in range(window - 1, len(prices)):
        ma = sum(prices[i-window+1:i+1]) / window
        result.append((i, ma))
    return result

ma20 = calc_ma(prices, 20)
ma60 = calc_ma(prices, 60)
ma120 = calc_ma(prices, 120)
ma250 = calc_ma(prices, 250)

ma20_dict = {idx: ma for idx, ma in ma20}
ma60_dict = {idx: ma for idx, ma in ma60}
ma120_dict = {idx: ma for idx, ma in ma120}
ma250_dict = {idx: ma for idx, ma in ma250}

n = len(prices)
above_ma250 = sum(1 for i in range(n) if i in ma250_dict and prices[i] > ma250_dict[i]) / len(ma250_dict) * 100 if ma250_dict else 0
above_ma120 = sum(1 for i in range(n) if i in ma120_dict and prices[i] > ma120_dict[i]) / len(ma120_dict) * 100 if ma120_dict else 0
above_ma60 = sum(1 for i in range(n) if i in ma60_dict and prices[i] > ma60_dict[i]) / len(ma60_dict) * 100 if ma60_dict else 0
above_ma20 = sum(1 for i in range(n) if i in ma20_dict and prices[i] > ma20_dict[i]) / len(ma20_dict) * 100 if ma20_dict else 0

slope_window = min(60, len(ma250))
slope_250 = (ma250[-1][1] - ma250[-slope_window][1]) / ma250[-slope_window][1] * 100 if slope_window >= 2 else 0
slope_window120 = min(120, len(ma120))
slope_120 = (ma120[-1][1] - ma120[-slope_window120][1]) / ma120[-slope_window120][1] * 100 if slope_window120 >= 2 else 0
slope_window60 = min(60, len(ma60))
slope_60 = (ma60[-1][1] - ma60[-slope_window60][1]) / ma60[-slope_window60][1] * 100 if slope_window60 >= 2 else 0

returns = []
for i in range(1, len(prices)):
    if prices[i-1] > 0:
        returns.append((prices[i] - prices[i-1]) / prices[i-1])
volatility = statistics.stdev(returns) * 100 if len(returns) >= 2 else 0

total_return = (prices[-1] - prices[0]) / prices[0] * 100
price_range = (max(prices) - min(prices)) / min(prices) * 100

print(f'\n趋势特征:')
print(f'  MA20斜率: {(ma20[-1][1] - ma20[-20][1]) / ma20[-20][1] * 100 if len(ma20) >= 20 else 0:.1f}%')
print(f'  MA60斜率: {slope_60:.1f}%')
print(f'  MA120斜率: {slope_120:.1f}%')
print(f'  MA250斜率: {slope_250:.1f}%')
print(f'  股价在MA20上方时间: {above_ma20:.1f}%')
print(f'  股价在MA60上方时间: {above_ma60:.1f}%')
print(f'  股价在MA120上方时间: {above_ma120:.1f}%')
print(f'  股价在MA250上方时间: {above_ma250:.1f}%')
print(f'  总收益: {total_return:.1f}%')
print(f'  波动率: {volatility:.2f}%')
print(f'  振幅: {price_range:.1f}%')

if trades:
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
            pnls.append({'entry': entry.price, 'exit': exit_trade.price, 'pnl': pnl, 'vol': entry.volume})

    if pnls:
        wins = [p for p in pnls if p['pnl'] > 0]
        losses = [p for p in pnls if p['pnl'] < 0]
        win_rate = len(wins) / len(pnls) * 100
        print(f'\n交易结果 (共{len(pnls)}笔):')
        print(f'  胜率: {win_rate:.1f}%')
        for j, p in enumerate(pnls):
            status = '盈利' if p['pnl'] > 0 else '亏损'
            print(f'  第{j+1}笔: 入场={p["entry"]:.2f} 出场={p["exit"]:.2f} 数量={p["vol"]:.0f}手 {status} {p["pnl"]:.0f}元')

        total_pnl = sum(p['pnl'] for p in pnls)
        print(f'  总盈亏: {total_pnl:.0f}元')
        if wins:
            avg_win = sum(p['pnl'] for p in wins) / len(wins)
            print(f'  平均盈利: {avg_win:.0f}元 ({len(wins)}笔)')
        if losses:
            avg_loss = sum(p['pnl'] for p in losses) / len(losses)
            print(f'  平均亏损: {avg_loss:.0f}元 ({len(losses)}笔)')
        if wins and losses:
            pl_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0
            print(f'  盈亏比: {pl_ratio:.1f}:1')