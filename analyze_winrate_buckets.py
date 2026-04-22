# -*- coding: utf-8 -*-
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

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
    avg_win = sum(wins) / len(wins) if wins else 0
    avg_loss = abs(sum(losses) / len(losses)) if losses else 0
    profit_loss_ratio = avg_win / avg_loss if avg_loss > 0 else float('inf')
    return {
        "total_trades": len(pnls),
        "win_trades": len(wins),
        "loss_trades": len(losses),
        "win_rate": win_rate,
        "profit_loss_ratio": profit_loss_ratio,
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

    print(f"\n成功分析: {len(results)} 只股票")

    bins = [(0, 10), (10, 20), (20, 30), (30, 40), (40, 50), (50, 60), (60, 70), (70, 80), (80, 90), (90, 100)]

    print("\n" + "=" * 90)
    print("胜率分档统计")
    print("=" * 90)
    print(f"{'胜率区间':<15} {'数量':<8} {'平均波动率':<12} {'平均振幅':<12} {'平均收益':<12} {'平均盈亏比':<12}")
    print("-" * 90)

    bin_results = {}
    for low, high in bins:
        stocks_in_bin = [r for r in results if low <= r["win_rate"] < high]
        if stocks_in_bin:
            avg_vol = sum(r["volatility"] for r in stocks_in_bin) / len(stocks_in_bin)
            avg_range = sum(r["price_range_pct"] for r in stocks_in_bin) / len(stocks_in_bin)
            avg_ret = sum(r["total_return"] for r in stocks_in_bin) / len(stocks_in_bin)
            avg_pl = sum(r["profit_loss_ratio"] for r in stocks_in_bin) / len(stocks_in_bin)
            pl_str = f"{avg_pl:.2f}" if avg_pl != float('inf') else "N/A"
            print(f"{low:>3.0f}-{high:<3.0f}%       {len(stocks_in_bin):<8} {avg_vol:<12.2f} {avg_range:<12.1f} {avg_ret:<12.1f} {pl_str:<12}")
            bin_results[f"{low}-{high}%"] = {
                "count": len(stocks_in_bin),
                "volatility": avg_vol,
                "range": avg_range,
                "return": avg_ret,
                "profit_loss": avg_pl,
            }

    print("\n" + "=" * 90)
    print("结论")
    print("=" * 90)

    best_bins = sorted(bin_results.items(), key=lambda x: x[1]["return"], reverse=True)[:3]
    print("\n收益最高的胜率区间:")
    for label, data in best_bins:
        print(f"  {label}: 平均收益={data['return']:.1f}%, 波动率={data['volatility']:.2f}%, 振幅={data['range']:.1f}%")

    highest_wr_bins = [(k, v) for k, v in bin_results.items() if "90" in k or "80" in k or "70" in k]
    if highest_wr_bins:
        print(f"\n高胜率区间(70%以上)共 {sum(v['count'] for k, v in highest_wr_bins)} 只股票")
        avg_ret_high = sum(v['return'] for k, v in highest_wr_bins) / len(highest_wr_bins)
        avg_vol_high = sum(v['volatility'] for k, v in highest_wr_bins) / len(highest_wr_bins)
        print(f"  平均收益: {avg_ret_high:.1f}%")
        print(f"  平均波动率: {avg_vol_high:.2f}%")

if __name__ == "__main__":
    main()