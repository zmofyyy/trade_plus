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
                    elif level == "2":
                        stock_to_blocks[code_formatted] = (block1_name, child_name)
                except:
                    continue
    return stock_to_blocks

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

    above_ma250_count = 0
    above_ma120_count = 0
    above_ma60_count = 0
    above_ma20_count = 0

    ma250_dict = {idx: ma for idx, ma in ma250}
    ma120_dict = {idx: ma for idx, ma in ma120}
    ma60_dict = {idx: ma for idx, ma in ma60}
    ma20_dict = {idx: ma for idx, ma in ma20}

    for i in range(n):
        if i in ma250_dict and prices[i] > ma250_dict[i]:
            above_ma250_count += 1
        if i in ma60_dict and prices[i] > ma60_dict[i]:
            above_ma60_count += 1
        if i in ma120_dict and prices[i] > ma120_dict[i]:
            above_ma120_count += 1
        if i in ma20_dict and prices[i] > ma20_dict[i]:
            above_ma20_count += 1

    above_ma250_pct = above_ma250_count / len(ma250_dict) * 100 if ma250_dict else 0
    above_ma120_pct = above_ma120_count / len(ma120_dict) * 100 if ma120_dict else 0
    above_ma60_pct = above_ma60_count / len(ma60_dict) * 100 if ma60_dict else 0
    above_ma20_pct = above_ma20_count / len(ma20_dict) * 100 if ma20_dict else 0

    slope_window = min(60, len(ma250))
    slope_250 = (ma250[-1][1] - ma250[-slope_window][1]) / ma250[-slope_window][1] * 100 if slope_window >= 2 else 0
    slope_window120 = min(120, len(ma120))
    slope_120 = (ma120[-1][1] - ma120[-slope_window120][1]) / ma120[-slope_window120][1] * 100 if slope_window120 >= 2 else 0
    slope_window60 = min(60, len(ma60))
    slope_60 = (ma60[-1][1] - ma60[-slope_window60][1]) / ma60[-slope_window60][1] * 100 if slope_window60 >= 2 else 0
    slope_window20 = min(20, len(ma20))
    slope_20 = (ma20[-1][1] - ma20[-slope_window20][1]) / ma20[-slope_window20][1] * 100 if slope_window20 >= 2 else 0

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
    stock_to_blocks = parse_block_csv(BLOCK_CSV_PATH)
    print(f"板块数据加载完成，共 {len(stock_to_blocks)} 只股票有板块归属")

    codes = get_stock_codes()
    print(f"发现股票总数: {len(codes)}")

    block1_data = {}

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
            trade_analysis = analyze_trades(trades)
            if not trade_analysis:
                continue
            trend_chars = analyze_trend_chars(bars)
            if not trend_chars:
                continue

            if vt_symbol in stock_to_blocks:
                block1_name, block2_name = stock_to_blocks[vt_symbol]
                if block1_name not in block1_data:
                    block1_data[block1_name] = []
                block1_data[block1_name].append({
                    **trade_analysis,
                    **trend_chars,
                    "vt_symbol": vt_symbol
                })
        except Exception as e:
            continue

    print(f"\n成功分析: {sum(len(v) for v in block1_data.values())} 只股票有板块数据")

    block1_summary = []
    for block1, stocks_data in block1_data.items():
        if len(stocks_data) >= 5:
            avg_wr = sum(r['win_rate'] for r in stocks_data) / len(stocks_data)
            avg_ret = sum(r['total_return'] for r in stocks_data) / len(stocks_data)
            avg_vol = sum(r['volatility'] for r in stocks_data) / len(stocks_data)
            avg_range = sum(r['price_range'] for r in stocks_data) / len(stocks_data)
            avg_ma120_slope = sum(r['ma_slope_120'] for r in stocks_data) / len(stocks_data)
            avg_ma250_slope = sum(r['ma_slope_250'] for r in stocks_data) / len(stocks_data)
            avg_above_ma250 = sum(r['above_ma250_pct'] for r in stocks_data) / len(stocks_data)
            avg_above_ma120 = sum(r['above_ma120_pct'] for r in stocks_data) / len(stocks_data)

            block1_summary.append({
                "block": block1,
                "count": len(stocks_data),
                "avg_win_rate": avg_wr,
                "avg_return": avg_ret,
                "avg_volatility": avg_vol,
                "avg_price_range": avg_range,
                "avg_ma120_slope": avg_ma120_slope,
                "avg_ma250_slope": avg_ma250_slope,
                "avg_above_ma250_pct": avg_above_ma250,
                "avg_above_ma120_pct": avg_above_ma120,
            })

    block1_summary.sort(key=lambda x: x['avg_win_rate'], reverse=True)

    print("\n" + "=" * 100)
    print("各一级行业板块的趋势特征分析")
    print("=" * 100)
    print(f"\n{'行业':<12} {'胜率':<8} {'MA120斜率':<10} {'MA250斜率':<10} {'MA250上方':<10} {'MA120上方':<10} {'总收益':<10} {'振幅':<10}")
    print("-" * 100)
    for item in block1_summary:
        print(f"{item['block']:<12} {item['avg_win_rate']:<8.1f} {item['avg_ma120_slope']:<10.1f} {item['avg_ma250_slope']:<10.1f} {item['avg_above_ma250_pct']:<10.1f} {item['avg_above_ma120_pct']:<10.1f} {item['avg_return']:<10.1f} {item['avg_price_range']:<10.1f}")

    print("\n" + "=" * 100)
    print("按 MA120 斜率排序（高斜率 -> 低斜率）")
    print("=" * 100)
    block1_by_slope = sorted(block1_summary, key=lambda x: x['avg_ma120_slope'], reverse=True)
    print(f"\n{'行业':<12} {'胜率':<8} {'MA120斜率':<10} {'MA250斜率':<10} {'MA250上方':<10} {'总收益':<10}")
    print("-" * 70)
    for item in block1_by_slope:
        print(f"{item['block']:<12} {item['avg_win_rate']:<8.1f} {item['avg_ma120_slope']:<10.1f} {item['avg_ma250_slope']:<10.1f} {item['avg_above_ma250_pct']:<10.1f} {item['avg_return']:<10.1f}")

    print("\n" + "=" * 100)
    print("按总收益排序（高 -> 低）")
    print("=" * 100)
    block1_by_return = sorted(block1_summary, key=lambda x: x['avg_return'], reverse=True)
    print(f"\n{'行业':<12} {'胜率':<8} {'MA120斜率':<10} {'MA250斜率':<10} {'总收益':<10} {'振幅':<10}")
    print("-" * 70)
    for item in block1_by_return:
        print(f"{item['block']:<12} {item['avg_win_rate']:<8.1f} {item['avg_ma120_slope']:<10.1f} {item['avg_ma250_slope']:<10.1f} {item['avg_return']:<10.1f} {item['avg_price_range']:<10.1f}")

    high_wr_blocks = [b for b in block1_summary if b['avg_win_rate'] >= 50]
    low_wr_blocks = [b for b in block1_summary if b['avg_win_rate'] < 45]

    print("\n" + "=" * 100)
    print("高胜率板块（>=50%）特征均值")
    print("=" * 100)
    if high_wr_blocks:
        n = len(high_wr_blocks)
        print(f"  MA120斜率均值: {sum(b['avg_ma120_slope'] for b in high_wr_blocks)/n:.1f}%")
        print(f"  MA250斜率均值: {sum(b['avg_ma250_slope'] for b in high_wr_blocks)/n:.1f}%")
        print(f"  MA250上方时间均值: {sum(b['avg_above_ma250_pct'] for b in high_wr_blocks)/n:.1f}%")
        print(f"  总收益均值: {sum(b['avg_return'] for b in high_wr_blocks)/n:.1f}%")

    print("\n" + "=" * 100)
    print("低胜率板块（<45%）特征均值")
    print("=" * 100)
    if low_wr_blocks:
        n = len(low_wr_blocks)
        print(f"  MA120斜率均值: {sum(b['avg_ma120_slope'] for b in low_wr_blocks)/n:.1f}%")
        print(f"  MA250斜率均值: {sum(b['avg_ma250_slope'] for b in low_wr_blocks)/n:.1f}%")
        print(f"  MA250上方时间均值: {sum(b['avg_above_ma250_pct'] for b in low_wr_blocks)/n:.1f}%")
        print(f"  总收益均值: {sum(b['avg_return'] for b in low_wr_blocks)/n:.1f}%")

    print("\n" + "=" * 100)
    print("结论分析")
    print("=" * 100)

if __name__ == "__main__":
    main()