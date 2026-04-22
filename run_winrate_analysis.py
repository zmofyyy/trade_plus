# -*- coding: utf-8 -*-
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import os
from datetime import datetime
from pathlib import Path
import statistics

from trade_plus.backtest import BacktestEngine, Exchange
from trade_plus.backtest.strategies import MaMultiBreakoutStrategy
from trade_plus.backtest.utils import TdxDataLoader

TDX_VIPDOC_PATH = r"D:\new_tdx\vipdoc"
START_DATE = datetime(2024, 1, 1)
END_DATE = datetime(2025, 12, 31)
MIN_BARS = 251
WIN_RATE_THRESHOLD = 50.0

def get_stock_codes():
    """获取所有A股股票代码（排除指数、基金等）"""
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
    """计算收益率波动率"""
    if len(prices) < 2:
        return 0
    returns = []
    for i in range(1, len(prices)):
        if prices[i-1] > 0:
            returns.append((prices[i] - prices[i-1]) / prices[i-1])
    if len(returns) < 2:
        return 0
    return statistics.stdev(returns) * 100

def calc_max_drawdown(prices):
    """计算最大回撤"""
    if not prices:
        return 0
    peak = prices[0]
    max_dd = 0
    for p in prices:
        if p > peak:
            peak = p
        dd = (peak - p) / peak * 100 if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd
    return max_dd

def analyze_stock(code, market, bars):
    """分析单只股票的特点"""
    prices = [b.close_price for b in bars]
    highs = [b.high_price for b in bars]
    lows = [b.low_price for b in bars]

    start_price = prices[0]
    end_price = prices[-1]
    total_return = (end_price - start_price) / start_price * 100 if start_price > 0 else 0

    volatility = calc_volatility(prices)
    max_dd = calc_max_drawdown(prices)

    avg_volume = statistics.mean([b.volume for b in bars]) if bars else 0

    price_range_pct = (max(highs) - min(lows)) / min(lows) * 100 if min(lows) > 0 else 0

    return {
        "code": code,
        "market": market,
        "start_price": start_price,
        "end_price": end_price,
        "total_return": total_return,
        "volatility": volatility,
        "max_drawdown": max_dd,
        "avg_volume": avg_volume,
        "price_range_pct": price_range_pct,
    }

def run_backtest(code, market):
    """对单只股票运行回测"""
    try:
        loader = TdxDataLoader(vipdoc_path=TDX_VIPDOC_PATH)
        bars = loader.load_daily_bars(
            code=code,
            market=market,
            start_date=START_DATE,
            end_date=END_DATE,
        )

        if len(bars) < MIN_BARS:
            return None

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

        stats = engine.run()
        trades = engine.get_trades()

        return {
            "code": code,
            "market": market,
            "vt_symbol": vt_symbol,
            "bars_count": len(bars),
            "trades": trades,
            "bars": bars,
        }
    except Exception as e:
        return None

def analyze_trades(trades):
    """分析交易记录，计算胜率和盈亏比"""
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
            entry_turnover = entry.price * entry.volume * size
            exit_turnover = exit_trade.price * exit_trade.volume * size
            pnl -= entry_turnover * 0.0003
            pnl -= exit_turnover * 0.0003
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
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "profit_loss_ratio": profit_loss_ratio,
        "total_pnl": sum(pnls),
    }

def main():
    print("=" * 70)
    print("A股全市场回测 - 筛选胜率>50%%的股票")
    print("=" * 70)
    print(f"数据目录: {TDX_VIPDOC_PATH}")
    print(f"回测区间: {START_DATE.date()} ~ {END_DATE.date()}")
    print(f"最小K线数: {MIN_BARS}")
    print(f"胜率阈值: >{WIN_RATE_THRESHOLD}%")
    print()

    codes = get_stock_codes()
    print(f"发现股票总数: {len(codes)}")
    print()

    results = []
    progress_interval = 500

    for i, (code, market) in enumerate(codes):
        if (i + 1) % progress_interval == 0:
            print(f"进度: {i + 1}/{len(codes)} ({100*(i+1)/len(codes):.1f}%)")

        result = run_backtest(code, market)
        if result and result["trades"]:
            analysis = analyze_trades(result["trades"])
            if analysis and analysis["total_trades"] >= 3:
                stock_chars = analyze_stock(code, market, result["bars"])
                results.append({
                    **analysis,
                    **stock_chars,
                    "trades": result["trades"],
                })

    print(f"\n完成! 成功回测: {len(results)} 只股票")
    print()

    if results:
        high_win_rate = [r for r in results if r["win_rate"] > WIN_RATE_THRESHOLD]
        print(f"=" * 70)
        print(f"胜率 > {WIN_RATE_THRESHOLD}% 的股票: {len(high_win_rate)} 只")
        print(f"=" * 70)

        if high_win_rate:
            print()
            print("-" * 70)
            print("汇总统计")
            print("-" * 70)

            total_trades = sum(r["total_trades"] for r in high_win_rate)
            total_wins = sum(r["win_trades"] for r in high_win_rate)
            total_losses = sum(r["loss_trades"] for r in high_win_rate)

            avg_return = statistics.mean([r["total_return"] for r in high_win_rate])
            avg_volatility = statistics.mean([r["volatility"] for r in high_win_rate])
            avg_max_dd = statistics.mean([r["max_drawdown"] for r in high_win_rate])
            avg_price_range = statistics.mean([r["price_range_pct"] for r in high_win_rate])

            print(f"股票数量:         {len(high_win_rate)}")
            print(f"平均胜率:         {sum(r['win_rate'] for r in high_win_rate) / len(high_win_rate):.1f}%")
            print(f"平均盈亏比:       {sum(r['profit_loss_ratio'] for r in high_win_rate) / len(high_win_rate):.2f}")
            print(f"平均总收益率:     {avg_return:.1f}%")
            print(f"平均波动率:       {avg_volatility:.2f}%")
            print(f"平均最大回撤:     {avg_max_dd:.1f}%")
            print(f"平均价格振幅:     {avg_price_range:.1f}%")
            print()

            print("-" * 70)
            print(f"Top 20 高胜率股票")
            print("-" * 70)
            sorted_by_winrate = sorted(high_win_rate, key=lambda x: (x["win_rate"], x["total_trades"]), reverse=True)
            print(f"{'代码':<10} {'市场':<6} {'交易':<6} {'胜率':<8} {'盈亏比':<10} {'总收益':<12} {'波动率':<10} {'振幅':<10}")
            print("-" * 80)
            for r in sorted_by_winrate[:20]:
                print(f"{r['code']:<10} {r['market']:<6} {r['total_trades']:<6} {r['win_rate']:.1f}%    {r['profit_loss_ratio']:<10.2f} {r['total_return']:<12.1f} {r['volatility']:<10.2f} {r['price_range_pct']:<10.1f}")
            print()

            print("-" * 70)
            print("股票特点分析")
            print("-" * 70)

            high_return_stocks = sorted(high_win_rate, key=lambda x: x["total_return"], reverse=True)[:10]
            high_vol_stocks = sorted(high_win_rate, key=lambda x: x["volatility"], reverse=True)[:10]
            high_range_stocks = sorted(high_win_rate, key=lambda x: x["price_range_pct"], reverse=True)[:10]

            print("收益最高的10只股票特点:")
            for r in high_return_stocks[:5]:
                print(f"  {r['code']}: 收益率={r['total_return']:.1f}%, 波动率={r['volatility']:.2f}%, 振幅={r['price_range_pct']:.1f}%, 胜率={r['win_rate']:.1f}%")

            print()
            print("高波动股票 (波动率>3%):")
            high_vol_filtered = [r for r in high_win_rate if r["volatility"] > 3.0]
            print(f"  数量: {len(high_vol_filtered)}")
            if high_vol_filtered:
                avg_wr_high_vol = sum(r['win_rate'] for r in high_vol_filtered) / len(high_vol_filtered)
                print(f"  平均胜率: {avg_wr_high_vol:.1f}%")

            low_vol_filtered = [r for r in high_win_rate if r["volatility"] < 2.0]
            print(f"低波动股票 (波动率<2%):")
            print(f"  数量: {len(low_vol_filtered)}")
            if low_vol_filtered:
                avg_wr_low_vol = sum(r['win_rate'] for r in low_vol_filtered) / len(low_vol_filtered)
                print(f"  平均胜率: {avg_wr_low_vol:.1f}%")

            print()
            print("-" * 70)
            print("按波动率分组统计")
            print("-" * 70)

            vol_bins = [(0, 1.5), (1.5, 2.0), (2.0, 2.5), (2.5, 3.0), (3.0, 100)]
            for low, high in vol_bins:
                stocks_in_bin = [r for r in high_win_rate if low <= r["volatility"] < high]
                if stocks_in_bin:
                    avg_wr = sum(r["win_rate"] for r in stocks_in_bin) / len(stocks_in_bin)
                    avg_pl = sum(r["profit_loss_ratio"] for r in stocks_in_bin) / len(stocks_in_bin)
                    avg_ret = sum(r["total_return"] for r in stocks_in_bin) / len(stocks_in_bin)
                    print(f"波动率 {low:.1f}-{high:.1f}%: {len(stocks_in_bin)}只, 平均胜率={avg_wr:.1f}%, 平均盈亏比={avg_pl:.2f}, 平均收益={avg_ret:.1f}%")

if __name__ == "__main__":
    main()