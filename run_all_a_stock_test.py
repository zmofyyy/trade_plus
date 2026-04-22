# -*- coding: utf-8 -*-
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import os
from datetime import datetime
from pathlib import Path

from trade_plus.backtest import BacktestEngine, Exchange
from trade_plus.backtest.strategies import MaMultiBreakoutStrategy
from trade_plus.backtest.utils import TdxDataLoader

TDX_VIPDOC_PATH = r"D:\new_tdx\vipdoc"
START_DATE = datetime(2024, 1, 1)
END_DATE = datetime(2025, 12, 31)
MIN_BARS = 251

def get_stock_codes():
    """获取所有A股股票代码（排除指数、基金等）"""
    codes = []
    sh_dir = Path(TDX_VIPDOC_PATH) / "sh" / "lday"
    sz_dir = Path(TDX_VIPDOC_PATH) / "sz" / "lday"

    # 上海A股：600xxx, 601xxx, 603xxx, 605xxx, 688xxx
    SH_PATTERNS = ('600', '601', '603', '605', '688')

    # 深圳A股：000xxx, 001xxx, 002xxx, 003xxx, 300xxx
    SZ_PATTERNS = ('000', '001', '002', '003', '300')

    for f in sh_dir.glob("*.day"):
        code = f.stem[2:]  # 去掉 "sh" 前缀
        if code.startswith(SH_PATTERNS):
            codes.append((code, "sh"))

    for f in sz_dir.glob("*.day"):
        code = f.stem[2:]  # 去掉 "sz" 前缀
        if code.startswith(SZ_PATTERNS):
            codes.append((code, "sz"))

    return codes

def run_backtest(code: str, market: str):
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
            setting={"ma20_window": 20, "ma250_window": 250, "volume": 50}
        )

        stats = engine.run()
        trades = engine.get_trades()

        return {
            "code": code,
            "market": market,
            "vt_symbol": vt_symbol,
            "bars_count": len(bars),
            "trades": trades,
        }
    except Exception as e:
        return None

def analyze_trades(trades):
    """分析交易记录，计算胜率和盈亏比"""
    if not trades:
        return None

    entries = []
    for t in trades:
        if t.offset.value in ["open", "none"]:
            entries.append(t)

    if len(entries) == 0:
        return None

    pnls = []
    for entry in entries:
        idx = trades.index(entry)
        if idx + 1 < len(trades):
            exit_trade = trades[idx + 1]
            if exit_trade.offset.value == "close":
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
    print("A股全市场回测 - MA均线突破策略")
    print("=" * 70)
    print(f"数据目录: {TDX_VIPDOC_PATH}")
    print(f"回测区间: {START_DATE.date()} ~ {END_DATE.date()}")
    print(f"最小K线数: {MIN_BARS}")
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
            if analysis:
                results.append({
                    **analysis,
                    "code": code,
                    "market": market,
                    "vt_symbol": result["vt_symbol"],
                    "bars_count": result["bars_count"],
                    "trades": result["trades"],
                })

    print(f"\n完成! 成功回测: {len(results)} 只股票")
    print()

    if results:
        print("=" * 70)
        print("汇总统计")
        print("=" * 70)

        total_trades = sum(r["total_trades"] for r in results)
        total_wins = sum(r["win_trades"] for r in results)
        total_losses = sum(r["loss_trades"] for r in results)

        all_pnls = []
        for r in results:
            trades = r.get("trades", [])
            i = 0
            while i < len(trades):
                t = trades[i]
                if t.offset.value in ["open", "none"]:
                    if i + 1 < len(trades):
                        exit_trade = trades[i + 1]
                        if exit_trade.offset.value == "close":
                            pnl = (exit_trade.price - t.price) * t.volume * 100
                            size = 100
                            pnl -= t.price * t.volume * size * 0.0003
                            pnl -= exit_trade.price * exit_trade.volume * size * 0.0003
                            all_pnls.append(pnl)
                    i += 2
                else:
                    i += 1

        wins = [p for p in all_pnls if p > 0]
        losses = [p for p in all_pnls if p <= 0]

        overall_win_rate = len(wins) / len(all_pnls) * 100 if all_pnls else 0
        avg_win = sum(wins) / len(wins) if wins else 0
        avg_loss = abs(sum(losses) / len(losses)) if losses else 0
        overall_profit_loss = avg_win / avg_loss if avg_loss > 0 else float('inf')

        print(f"回测股票数:     {len(results)}")
        print(f"总交易次数:     {total_trades}")
        print(f"盈利次数:       {total_wins}")
        print(f"亏损次数:       {total_losses}")
        print(f"总体胜率:       {overall_win_rate:.2f}%")
        print(f"平均盈利:       {avg_win:.2f}")
        print(f"平均亏损:       {avg_loss:.2f}")
        print(f"盈亏比:         {overall_profit_loss:.2f}")
        print(f"总盈亏:         {sum(all_pnls):.2f}")
        print()

        print("=" * 70)
        print("Top 10 盈利股票")
        print("=" * 70)
        sorted_by_pnl = sorted(results, key=lambda x: x["total_pnl"], reverse=True)
        print(f"{'代码':<10} {'市场':<6} {'交易次数':<8} {'胜率':<8} {'盈亏比':<10} {'总盈亏':<15}")
        print("-" * 70)
        for r in sorted_by_pnl[:10]:
            print(f"{r['code']:<10} {r['market']:<6} {r['total_trades']:<8} {r['win_rate']:.1f}%    {r['profit_loss_ratio']:<10.2f} {r['total_pnl']:<15.2f}")
        print()

        print("=" * 70)
        print("Top 10 亏损股票")
        print("=" * 70)
        sorted_by_loss = sorted(results, key=lambda x: x["total_pnl"])[:10]
        print(f"{'代码':<10} {'市场':<6} {'交易次数':<8} {'胜率':<8} {'盈亏比':<10} {'总盈亏':<15}")
        print("-" * 70)
        for r in sorted_by_loss:
            print(f"{r['code']:<10} {r['market']:<6} {r['total_trades']:<8} {r['win_rate']:.1f}%    {r['profit_loss_ratio']:<10.2f} {r['total_pnl']:<15.2f}")
        print()

        print("=" * 70)
        print("胜率最高的前10只股票")
        print("=" * 70)
        sorted_by_winrate = sorted(results, key=lambda x: (x["win_rate"], x["total_trades"]), reverse=True)
        print(f"{'代码':<10} {'市场':<6} {'交易次数':<8} {'胜率':<8} {'盈亏比':<10} {'总盈亏':<15}")
        print("-" * 70)
        for r in sorted_by_winrate[:10]:
            print(f"{r['code']:<10} {r['market']:<6} {r['total_trades']:<8} {r['win_rate']:.1f}%    {r['profit_loss_ratio']:<10.2f} {r['total_pnl']:<15.2f}")

if __name__ == "__main__":
    main()