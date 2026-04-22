# -*- coding: utf-8 -*-
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from pathlib import Path
from datetime import datetime
import statistics

from trade_plus.backtest import BacktestEngine, Exchange
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

def calc_volatility(prices):
    if len(prices) < 2:
        return 0
    returns = []
    for i in range(1, len(prices)):
        if prices[i-1] > 0:
            returns.append((prices[i] - prices[i-1]) / prices[i-1])
    if len(returns) < 2:
        return 0
    return statistics.stdev(returns) * 100

def analyze_stock(bars):
    prices = [b.close_price for b in bars]
    highs = [b.high_price for b in bars]
    lows = [b.low_price for b in bars]
    start_price = prices[0]
    end_price = prices[-1]
    total_return = (end_price - start_price) / start_price * 100 if start_price > 0 else 0
    volatility = calc_volatility(prices)
    price_range_pct = (max(highs) - min(lows)) / min(lows) * 100 if min(lows) > 0 else 0
    return {
        "total_return": total_return,
        "volatility": volatility,
        "price_range_pct": price_range_pct,
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
    losses = [p for p in pnls if p <= 0]
    win_rate = len(wins) / len(pnls) * 100 if pnls else 0
    return {
        "total_trades": len(pnls),
        "win_rate": win_rate,
        "total_pnl": sum(pnls),
    }

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
            if not analysis or analysis["total_trades"] < 3:
                continue
            stock_chars = analyze_stock(bars)
            results.append({**analysis, **stock_chars, "code": code, "market": market})
        except Exception as e:
            continue

    low_win_rate = [r for r in results if r["win_rate"] < 50]
    high_win_rate = [r for r in results if r["win_rate"] >= 50]

    print(f"\n胜率<50%的股票: {len(low_win_rate)} 只")
    print(f"胜率>=50%的股票: {len(high_win_rate)} 只")

    if low_win_rate:
        print(f"\n=== 胜率<50%股票特征 ===")
        avg_wr = sum(r['win_rate'] for r in low_win_rate) / len(low_win_rate)
        avg_vol = sum(r['volatility'] for r in low_win_rate) / len(low_win_rate)
        avg_ret = sum(r['total_return'] for r in low_win_rate) / len(low_win_rate)
        avg_range = sum(r['price_range_pct'] for r in low_win_rate) / len(low_win_rate)
        print(f"平均胜率: {avg_wr:.1f}%")
        print(f"平均波动率: {avg_vol:.2f}%")
        print(f"平均总收益: {avg_ret:.1f}%")
        print(f"平均价格振幅: {avg_range:.1f}%")

    if high_win_rate:
        print(f"\n=== 胜率>=50%股票特征 ===")
        avg_wr_h = sum(r['win_rate'] for r in high_win_rate) / len(high_win_rate)
        avg_vol_h = sum(r['volatility'] for r in high_win_rate) / len(high_win_rate)
        avg_ret_h = sum(r['total_return'] for r in high_win_rate) / len(high_win_rate)
        avg_range_h = sum(r['price_range_pct'] for r in high_win_rate) / len(high_win_rate)
        print(f"平均胜率: {avg_wr_h:.1f}%")
        print(f"平均波动率: {avg_vol_h:.2f}%")
        print(f"平均总收益: {avg_ret_h:.1f}%")
        print(f"平均价格振幅: {avg_range_h:.1f}%")

    print(f"\n=== 对比总结 ===")
    print(f"{'指标':<20} {'胜率<50%':<15} {'胜率>=50%':<15}")
    print("-" * 50)
    print(f"{'股票数量':<20} {len(low_win_rate):<15} {len(high_win_rate):<15}")
    print(f"{'平均波动率':<20} {avg_vol:.2f}%{'':<10} {avg_vol_h:.2f}%")
    print(f"{'平均总收益':<20} {avg_ret:.1f}%{'':<10} {avg_ret_h:.1f}%")
    print(f"{'平均价格振幅':<20} {avg_range:.1f}%{'':<10} {avg_range_h:.1f}%")

if __name__ == "__main__":
    main()