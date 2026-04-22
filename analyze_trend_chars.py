# -*- coding: utf-8 -*-
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from pathlib import Path
from datetime import datetime
import statistics

from trade_plus.backtest import BacktestEngine
from trade_plus.backtest.strategies import MaMultiBreakoutStrategy
from trade_plus.backtest.utils import TdxDataLoader

TDX_VIPDOC_PATH = r"D:\new_tdx\vipdoc"
START_DATE = datetime(2024, 1, 1)
END_DATE = datetime(2025, 12, 31)
MIN_BARS = 251

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

def calc_ma(prices, window):
    result = []
    for i in range(window - 1, len(prices)):
        ma = sum(prices[i - window + 1:i + 1]) / window
        result.append((i, ma))
    return result

def calc_volatility(prices):
    if len(prices) < 2:
        return 0
    returns = []
    for i in range(1, len(prices)):
        if prices[i - 1] > 0:
            returns.append((prices[i] - prices[i - 1]) / prices[i - 1])
    if len(returns) < 2:
        return 0
    return statistics.stdev(returns) * 100

def analyze_trend_chars(bars):
    prices = [b.close_price for b in bars]
    n = len(prices)
    if n < 250:
        return None

    ma20 = calc_ma(prices, 20)
    ma60 = calc_ma(prices, 60)
    ma120 = calc_ma(prices, 120)
    ma250 = calc_ma(prices, 250)

    above_ma20_count = 0
    above_ma60_count = 0
    above_ma120_count = 0
    above_ma250_count = 0
    trend排列_count = 0

    valid_start = max(len(ma20), len(ma60), len(ma120), len(ma250))
    if valid_start > n:
        return None

    ma20_dict = {idx: ma for idx, ma in ma20}
    ma60_dict = {idx: ma for idx, ma in ma60}
    ma120_dict = {idx: ma for idx, ma in ma120}
    ma250_dict = {idx: ma for idx, ma in ma250}

    for i in range(n):
        if i in ma250_dict:
            if prices[i] > ma250_dict[i]:
                above_ma250_count += 1
        if i in ma60_dict:
            if prices[i] > ma60_dict[i]:
                above_ma60_count += 1
        if i in ma120_dict:
            if prices[i] > ma120_dict[i]:
                above_ma120_count += 1
        if i in ma20_dict:
            if prices[i] > ma20_dict[i]:
                above_ma20_count += 1

        if all(k in ma250_dict and ma250_dict[k] > 0 for k in [i, i - 1, i - 2]) and \
           all(k in ma120_dict for k in [i, i - 1]):
            m20 = ma20_dict.get(i, 0)
            m60 = ma60_dict.get(i, 0)
            m120 = ma120_dict.get(i, 0)
            m250 = ma250_dict.get(i, 0)
            if m20 > m60 > m120 > m250:
                trend排列_count += 1

    above_ma250_pct = above_ma250_count / len(ma250_dict) * 100 if ma250_dict else 0
    above_ma120_pct = above_ma120_count / len(ma120_dict) * 100 if ma120_dict else 0
    above_ma60_pct = above_ma60_count / len(ma60_dict) * 100 if ma60_dict else 0
    above_ma20_pct = above_ma20_count / len(ma20_dict) * 100 if ma20_dict else 0

    slope_window = min(60, len(ma250))
    if slope_window >= 2:
        slope_250 = (ma250[-1][1] - ma250[-slope_window][1]) / ma250[-slope_window][1] * 100
    else:
        slope_250 = 0

    slope_window20 = min(20, len(ma20))
    if slope_window20 >= 2:
        slope_20 = (ma20[-1][1] - ma20[-slope_window20][1]) / ma20[-slope_window20][1] * 100
    else:
        slope_20 = 0

    slope_window60 = min(60, len(ma60))
    if slope_window60 >= 2:
        slope_60 = (ma60[-1][1] - ma60[-slope_window60][1]) / ma60[-slope_window60][1] * 100
    else:
        slope_60 = 0

    slope_window120 = min(120, len(ma120))
    if slope_window120 >= 2:
        slope_120 = (ma120[-1][1] - ma120[-slope_window120][1]) / ma120[-slope_window120][1] * 100
    else:
        slope_120 = 0

    trend_pct = trend排列_count / len(ma250_dict) * 100 if ma250_dict else 0

    start_price = prices[0]
    end_price = prices[-1]
    total_return = (end_price - start_price) / start_price * 100 if start_price > 0 else 0

    volatility = calc_volatility(prices)

    price_range = (max(prices) - min(prices)) / min(prices) * 100 if min(prices) > 0 else 0

    return {
        "above_ma20_pct": above_ma20_pct,
        "above_ma60_pct": above_ma60_pct,
        "above_ma120_pct": above_ma120_pct,
        "above_ma250_pct": above_ma250_pct,
        "ma_slope_20": slope_20,
        "ma_slope_60": slope_60,
        "ma_slope_120": slope_120,
        "ma_slope_250": slope_250,
        "trend_pct": trend_pct,
        "total_return": total_return,
        "volatility": volatility,
        "price_range": price_range,
    }

def analyze_trades(trades):
    if not trades:
        return None
    pnls = []
    for i in range(0, len(trades) - 1, 2):
        if i + 1 >= len(trades):
            break
        entry = trades[i]
        exit_trade = trades[i + 1]
        if entry.offset.value in ["open", "none"] and exit_trade.offset.value == "close":
            pnl = (exit_trade.price - entry.price) * entry.volume * 100
            size = 100
            pnl -= entry.price * entry.volume * size * 0.0003
            pnl -= exit_trade.price * exit_trade.volume * size * 0.0003
            pnls.append(pnl)
    if not pnls:
        return None
    wins = [p for p in pnls if p > 0]
    win_rate = len(wins) / len(pnls) * 100 if pnls else 0
    return {"win_rate": win_rate, "total_trades": len(pnls)}

def main():
    codes = get_stock_codes()
    print(f"发现股票总数: {len(codes)}")

    results = []

    for i, (code, market) in enumerate(codes):
        if (i + 1) % 500 == 0:
            print(f"进度: {i + 1}/{len(codes)}")

        try:
            loader = TdxDataLoader(vipdoc_path=TDX_VIPDOC_PATH)
            bars = loader.load_daily_bars(code=code, market=market, start_date=START_DATE, end_date=END_DATE)
            if len(bars) < MIN_BARS:
                continue
            vt_symbol = f"{code}.{'SSE' if market == 'sh' else 'SZSE'}"
            engine = (
                BacktestEngine(initial_capital=500_000.0)
                .set_symbols([vt_symbol])
                .set_period(bars[0].datetime, bars[-1].datetime)
                .add_contract(vt_symbol, size=100, long_rate=0.0003, short_rate=0.0003, pricetick=0.01)
                .set_data(vt_symbol, bars)
            )
            engine.use_strategy(
                MaMultiBreakoutStrategy,
                setting={"ma20_window": 20, "ma250_window": 250, "position_pct": 0.15}
            )
            engine.run()
            trades = engine.get_trades()
            if not trades:
                continue
            analysis = analyze_trades(trades)
            if not analysis:
                continue
            trend_chars = analyze_trend_chars(bars)
            if not trend_chars:
                continue
            results.append({**analysis, **trend_chars, "code": code, "market": market})
        except Exception as e:
            continue

    print(f"\n成功分析: {len(results)} 只股票")

    low_wr = [r for r in results if r["win_rate"] < 40]
    mid_wr = [r for r in results if 40 <= r["win_rate"] < 60]
    high_wr = [r for r in results if r["win_rate"] >= 60]

    def print_group(name, stocks):
        if not stocks:
            return
        n = len(stocks)
        print(f"\n{name} (共{n}只, 平均胜率{sum(r['win_rate'] for r in stocks)/n:.1f}%):")
        print(f"  股价在MA20上方时间: {sum(r['above_ma20_pct'] for r in stocks)/n:.1f}%")
        print(f"  股价在MA60上方时间: {sum(r['above_ma60_pct'] for r in stocks)/n:.1f}%")
        print(f"  股价在MA120上方时间: {sum(r['above_ma120_pct'] for r in stocks)/n:.1f}%")
        print(f"  股价在MA250上方时间: {sum(r['above_ma250_pct'] for r in stocks)/n:.1f}%")
        print(f"  MA20斜率(年化): {sum(r['ma_slope_20'] for r in stocks)/n:.1f}%")
        print(f"  MA60斜率(年化): {sum(r['ma_slope_60'] for r in stocks)/n:.1f}%")
        print(f"  MA120斜率(年化): {sum(r['ma_slope_120'] for r in stocks)/n:.1f}%")
        print(f"  MA250斜率(年化): {sum(r['ma_slope_250'] for r in stocks)/n:.1f}%")
        print(f"  多头排列时间占比: {sum(r['trend_pct'] for r in stocks)/n:.1f}%")
        print(f"  平均总收益: {sum(r['total_return'] for r in stocks)/n:.1f}%")
        print(f"  平均波动率: {sum(r['volatility'] for r in stocks)/n:.2f}%")
        print(f"  平均振幅: {sum(r['price_range'] for r in stocks)/n:.1f}%")

    print_group("低胜率(<40%)", low_wr)
    print_group("中胜率(40-60%)", mid_wr)
    print_group("高胜率(>=60%)", high_wr)

    print("\n" + "=" * 80)
    print("结论分析")
    print("=" * 80)

if __name__ == "__main__":
    main()