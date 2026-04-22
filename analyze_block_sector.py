# -*- coding: utf-8 -*-
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import csv
from pathlib import Path
from datetime import datetime
import statistics

from trade_plus.backtest import BacktestEngine
from trade_plus.backtest.strategies import MaMultiBreakoutStrategy
from trade_plus.backtest.utils import TdxDataLoader

TDX_VIPDOC_PATH = r"D:\new_tdx\vipdoc"
BLOCK_CSV_PATH = r"F:\source\tdx_reader\tdx_reader\block_mapping_result.csv"
START_DATE = datetime(2024, 1, 1)
END_DATE = datetime(2025, 12, 31)
MIN_BARS = 251

def parse_block_csv(csv_path):
    """解析板块映射CSV，返回 {股票代码: (一级行业, 二级行业)}"""
    stock_to_blocks = {}
    block1_stocks = {}
    block2_stocks = {}

    with open(csv_path, encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            if len(row) < 7:
                continue
            level = row[0]
            block1_code = row[1]
            block1_name = row[2]
            child_code = row[3]
            child_name = row[4]
            stocks_str = row[6] if len(row) > 6 else ""

            if not stocks_str:
                continue

            stocks = [s.strip() for s in stocks_str.split(",")]

            for stock_full in stocks:
                if not stock_full or len(stock_full) < 4:
                    continue
                try:
                    market_part, code = stock_full.split(".")
                    if market_part == "SH":
                        code_formatted = f"{code}.SSE"
                    elif market_part == "SZ":
                        code_formatted = f"{code}.SZSE"
                    elif market_part == "BJ":
                        code_formatted = f"{code}.BJSE"
                    else:
                        continue

                    if level == "1":
                        stock_to_blocks[code_formatted] = (block1_name, block1_name)
                        block1_stocks.setdefault(block1_name, []).append(code_formatted)
                    elif level == "2":
                        parent = stock_to_blocks.get(code_formatted, (block1_name, block1_name))
                        stock_to_blocks[code_formatted] = (block1_name, child_name)
                        block2_stocks.setdefault(child_name, []).append(code_formatted)
                except:
                    continue

    return stock_to_blocks, block1_stocks, block2_stocks

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
            pnl -= entry.price * entry.volume * 100 * 0.0003
            pnl -= exit_trade.price * exit_trade.volume * 100 * 0.0003
            pnls.append(pnl)
    if not pnls:
        return None
    wins = [p for p in pnls if p > 0]
    win_rate = len(wins) / len(pnls) * 100 if pnls else 0
    return {"win_rate": win_rate, "total_trades": len(pnls)}

def main():
    print("加载板块映射...")
    stock_to_blocks, block1_stocks, block2_stocks = parse_block_csv(BLOCK_CSV_PATH)
    print(f"板块数据加载完成，共 {len(stock_to_blocks)} 只股票有板块归属")

    codes = get_stock_codes()
    print(f"发现股票总数: {len(codes)}")

    block1_results = {}
    block2_results = {}

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

            if vt_symbol in stock_to_blocks:
                block1_name, block2_name = stock_to_blocks[vt_symbol]
                if block1_name not in block1_results:
                    block1_results[block1_name] = []
                block1_results[block1_name].append(analysis)

                if block2_name not in block2_results:
                    block2_results[block2_name] = []
                block2_results[block2_name].append(analysis)

        except Exception as e:
            continue

    print(f"\n成功分析: {sum(len(v) for v in block1_results.values())} 只股票有板块数据")

    print("\n" + "=" * 80)
    print("一级行业板块胜率统计（按平均胜率排序）")
    print("=" * 80)

    block1_summary = []
    for block1, results in block1_results.items():
        if len(results) >= 5:
            avg_wr = sum(r['win_rate'] for r in results) / len(results)
            avg_trades = sum(r['total_trades'] for r in results) / len(results)
            block1_summary.append({
                "block": block1,
                "count": len(results),
                "avg_win_rate": avg_wr,
                "avg_trades": avg_trades
            })

    block1_summary.sort(key=lambda x: x['avg_win_rate'], reverse=True)

    print(f"\n{'行业板块':<20} {'股票数':<8} {'平均胜率':<12} {'平均交易次数':<12}")
    print("-" * 60)
    for item in block1_summary:
        print(f"{item['block']:<20} {item['count']:<8} {item['avg_win_rate']:<12.1f} {item['avg_trades']:<12.1f}")

    print("\n" + "=" * 80)
    print("二级行业板块胜率统计（TOP 30，按平均胜率排序）")
    print("=" * 80)

    block2_summary = []
    for block2, results in block2_results.items():
        if len(results) >= 5:
            avg_wr = sum(r['win_rate'] for r in results) / len(results)
            avg_trades = sum(r['total_trades'] for r in results) / len(results)
            block2_summary.append({
                "block": block2,
                "count": len(results),
                "avg_win_rate": avg_wr,
                "avg_trades": avg_trades
            })

    block2_summary.sort(key=lambda x: x['avg_win_rate'], reverse=True)

    print(f"\n{'子行业板块':<20} {'股票数':<8} {'平均胜率':<12} {'平均交易次数':<12}")
    print("-" * 60)
    for item in block2_summary[:30]:
        print(f"{item['block']:<20} {item['count']:<8} {item['avg_win_rate']:<12.1f} {item['avg_trades']:<12.1f}")

    print("\n" + "=" * 80)
    print("二级行业板块胜率统计（BOTTOM 20，按平均胜率排序）")
    print("=" * 80)
    print(f"\n{'子行业板块':<20} {'股票数':<8} {'平均胜率':<12} {'平均交易次数':<12}")
    print("-" * 60)
    for item in block2_summary[-20:]:
        print(f"{item['block']:<20} {item['count']:<8} {item['avg_win_rate']:<12.1f} {item['avg_trades']:<12.1f}")

    high_wr_blocks = [b for b in block2_summary if b['avg_win_rate'] >= 60]
    mid_wr_blocks = [b for b in block2_summary if 50 <= b['avg_win_rate'] < 60]
    low_wr_blocks = [b for b in block2_summary if b['avg_win_rate'] < 50]

    print("\n" + "=" * 80)
    print("高胜率板块（>=60%）共 {} 个".format(len(high_wr_blocks)))
    print("=" * 80)
    for item in high_wr_blocks:
        print(f"  {item['block']}: {item['avg_win_rate']:.1f}% ({item['count']}只)")

    print("\n" + "=" * 80)
    print("结论分析")
    print("=" * 80)

if __name__ == "__main__":
    main()