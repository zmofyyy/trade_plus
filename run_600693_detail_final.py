# -*- coding: utf-8 -*-
"""
600693 回测详细分析
正确计算资金曲线 = 剩余资金 + 持仓变现
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from trade_plus.backtest import BacktestEngine, Exchange, RiskControlLayer
from trade_plus.backtest.risk import MaxSingleOrderValueRule, MaxDrawdownRule
from trade_plus.backtest.strategies import MaMultiBreakoutStrategy
from trade_plus.backtest.utils import TdxDataLoader
from datetime import datetime

TDX_VIPDOC_PATH = r"D:\new_tdx\vipdoc"

def run_backtest_detail(symbol, market, start_date, end_date):
    print("=" * 70)
    print(f"MA多周期过滤突破策略 — {symbol}.{market.upper()} 详细回测")
    print("=" * 70)

    loader = TdxDataLoader(vipdoc_path=TDX_VIPDOC_PATH)
    bars = loader.load_daily_bars(symbol, market, start_date, end_date)

    vt_symbol = f"{symbol}.{Exchange.SZSE.value if market == 'sz' else Exchange.SSE.value}"

    engine = (
        BacktestEngine(initial_capital=500_000.0)
        .set_symbols([vt_symbol])
        .set_period(start_date, bars[-1].datetime)
        .add_contract(vt_symbol, size=100, long_rate=0.0003, short_rate=0.0003, pricetick=0.01)
        .set_data(vt_symbol, bars)
    )
    risk_layer = RiskControlLayer()
    risk_layer.add_rule(MaxSingleOrderValueRule(max_pct=0.3))
    risk_layer.add_rule(MaxDrawdownRule(max_drawdown_pct=0.2))
    engine.use_risk_layer(risk_layer)
    engine.use_strategy(MaMultiBreakoutStrategy, setting={
        "ma20_window": 20,
        "ma250_window": 250,
        "volume": 50,
    })

    stats = engine.run()
    trades = engine.get_trades()

    print(f"\n数据范围: {start_date.date()} ~ {end_date.date()}")
    print(f"K线数量: {len(bars)}")
    print(f"初始资金: 500,000.00")

    # 处理交易对
    trades_list = list(trades)
    trades_list.sort(key=lambda x: x.datetime)

    # 匹配买卖交易
    trade_pairs = []
    entry = None
    for t in trades_list:
        if t.offset.value in ["open", "none"]:
            entry = t
        else:
            if entry:
                trade_pairs.append((entry, t))
                entry = None

    print("\n" + "=" * 70)
    print("【逐笔交易详情】")
    print("=" * 70)

    total_pnl = 0.0
    for idx, (entry, exit) in enumerate(trade_pairs, 1):
        size = 100
        entry_turnover = entry.price * entry.volume * size
        exit_turnover = exit.price * exit.volume * size

        pnl = (exit.price - entry.price) * entry.volume * size
        pnl -= entry_turnover * 0.0003
        pnl -= exit_turnover * 0.0003

        holding_days = (exit.datetime - entry.datetime).days
        total_pnl += pnl

        direction = "买入" if entry.direction.value == "long" else "卖出"
        exit_direction = "卖出" if exit.direction.value == "short" else "买入"
        print(f"\n  第{idx}笔:")
        print(f"    入场: {entry.datetime.date()} {direction} @ {entry.price:.2f} 数量={entry.volume}")
        print(f"    出场: {exit.datetime.date()} {exit_direction} @ {exit.price:.2f} 数量={exit.volume}")
        print(f"    持仓天数: {holding_days}天")
        print(f"    买入成交额: {entry_turnover:,.2f}")
        print(f"    卖出成交额: {exit_turnover:,.2f}")
        print(f"    手续费合计: {entry_turnover * 0.0003 + exit_turnover * 0.0003:.2f}")
        print(f"    净盈亏: {pnl:,.2f} ({'盈利' if pnl > 0 else '亏损'})")

    print(f"\n  已匹配交易对: {len(trade_pairs)} 笔")
    print(f"  累计净盈亏: {total_pnl:,.2f}")

    # 手动计算资金曲线
    print("\n" + "=" * 70)
    print("【资金权益曲线 — 逐日计算】")
    print("=" * 70)

    # 构建日期到收盘价的映射
    bar_map = {}
    for bar in bars:
        d = bar.datetime if isinstance(bar.datetime, datetime) else datetime.combine(bar.datetime, datetime.min.time())
        bar_map[d.date()] = bar.close_price

    all_dates = sorted(bar_map.keys())

    cash = 500000.0
    pos = 0.0
    size = 100
    commission_rate = 0.0003

    trade_idx = 0
    daily_records = []

    for d in all_dates:
        close = bar_map.get(d, 0.0)

        # 处理当日的交易
        while trade_idx < len(trades_list) and trades_list[trade_idx].datetime.date() == d:
            trade = trades_list[trade_idx]
            turnover = trade.price * trade.volume * size
            commission = turnover * commission_rate

            if trade.direction.value == "long":
                cash -= (turnover + commission)
                pos += trade.volume
            else:
                cash += (turnover - commission)
                pos -= trade.volume

            trade_idx += 1

        # 计算市值 (持仓变现)
        market_value = pos * close * size if pos > 0 else 0.0

        # 总资产 = 现金 + 持仓变现
        total_assets = cash + market_value

        daily_records.append({
            'date': d,
            'cash': cash,
            'close': close,
            'pos': pos,
            'market_value': market_value,
            'total_assets': total_assets,
        })

    # 打印权益曲线
    print(f"\n{'日期':<12} {'现金余额':>15} {'收盘价':>10} {'持仓':>8} {'变现市值':>15} {'总资产':>15}")
    print("-" * 70)

    # 只打印有交易或持仓变化的日期
    prev_pos = None
    for rec in daily_records:
        # 打印所有日子
        print(f"{str(rec['date']):<12} {rec['cash']:>15,.2f} {rec['close']:>10.2f} {rec['pos']:>8.0f} {rec['market_value']:>15,.2f} {rec['total_assets']:>15,.2f}")

    # 统计
    print("\n" + "=" * 70)
    print("【统计摘要】")
    print("=" * 70)

    final_record = daily_records[-1] if daily_records else None
    final_assets = final_record['total_assets'] if final_record else 500000.0
    final_cash = final_record['cash'] if final_record else 500000.0
    final_pos = final_record['pos'] if final_record else 0.0

    high_water = 500000.0
    max_drawdown = 0.0
    max_drawdown_pct = 0.0
    max_drawdown_date = None

    for rec in daily_records:
        if rec['total_assets'] > high_water:
            high_water = rec['total_assets']
        dd = high_water - rec['total_assets']
        if dd > max_drawdown:
            max_drawdown = dd
            max_drawdown_pct = (dd / high_water) * 100
            max_drawdown_date = rec['date']

    print(f"初始资金:     500,000.00")
    print(f"最终现金:     {final_cash:,.2f}")
    print(f"最终持仓:     {final_pos:.0f} 手")
    print(f"最终总资产:   {final_assets:,.2f}")
    print(f"总盈亏:       {final_assets - 500000:,.2f}")
    print(f"总收益率:     {(final_assets - 500000) / 500000 * 100:.2f}%")
    print(f"最大回撤:     {max_drawdown:,.2f}")
    print(f"百分比回撤:   {max_drawdown_pct:.2f}%")
    print(f"最大回撤日期: {max_drawdown_date}")

    return engine, stats

if __name__ == "__main__":
    start = datetime(2024, 1, 1)
    end = datetime(2026, 4, 20)

    run_backtest_detail("600693", "sh", start, end)