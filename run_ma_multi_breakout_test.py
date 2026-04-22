# -*- coding: utf-8 -*-
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

"""
MA多周期过滤突破策略回测测试

使用通达信本地数据源进行回测。

规则：
- 多头入场：收盘价上穿20日均线，且 MA20 > MA60, MA20 > MA120, MA20 > MA250
- 退出方式：移动追踪止损，跌破持仓期间最高价×95%时以当天收盘价卖出

用法：
    python run_ma_multi_breakout_test.py 000001 sz
    python run_ma_multi_breakout_test.py 600000 sh
    python run_ma_multi_breakout_test.py 000001 sz 2023-01-01 2025-12-31
"""

import argparse
from datetime import datetime

from trade_plus.backtest import (
    BacktestEngine,
    Interval,
    Exchange,
    RiskControlLayer,
)
from trade_plus.backtest.risk import (
    MaxSingleOrderValueRule,
    MaxDrawdownRule,
)
from trade_plus.backtest.strategies import MaMultiBreakoutStrategy
from trade_plus.backtest.utils import TdxDataLoader


def run_backtest(symbol: str, market: str, start: datetime, end: datetime, position_pct: float = 1.0):
    TDX_VIPDOC_PATH = r"D:\new_tdx\vipdoc"

    print("=" * 60)
    print("MA多周期过滤突破策略 — 通达信本地数据回测")
    print("=" * 60)

    print(f"\n[1] 加载通达信本地数据（复权数据）")
    loader = TdxDataLoader(vipdoc_path=TDX_VIPDOC_PATH)
    bars = loader.load_daily_bars(
        code=symbol,
        market=market,
        start_date=start,
        end_date=end,
    )
    print(f"    标的: {symbol}.{market.upper()}")
    print(f"    数据范围: {start.date()} ~ {end.date()}")
    print(f"    K线数: {len(bars)}")
    print(f"    起始价: {bars[0].close_price:.2f}")
    print(f"    结束价: {bars[-1].close_price:.2f}")

    if len(bars) < 251:
        print(f"    [警告] 数据不足250根K线，策略可能无法正常运行")

    vt_symbol = f"{symbol}.{'SSE' if market == 'sh' else 'SZSE'}"

    print(f"\n[2] 配置回测引擎")
    engine = (
        BacktestEngine(initial_capital=500_000.0)
        .set_symbols([vt_symbol])
        .set_period(start, bars[-1].datetime)
        .add_contract(
            vt_symbol,
            size=100,
            long_rate=0.0003,
            short_rate=0.0003,
            pricetick=0.01,
        )
        .set_data(vt_symbol, bars)
    )
    print(f"    初始资金: 500,000")
    print(f"    合约乘数: 100")
    print(f"    手续费率: 万3")

    print(f"\n[3] 配置风控规则")
    risk_layer = RiskControlLayer()
    risk_layer.add_rule(MaxSingleOrderValueRule(max_pct=0.3))
    risk_layer.add_rule(MaxDrawdownRule(max_drawdown_pct=0.2))
    engine.use_risk_layer(risk_layer)
    print(f"    MaxSingleOrderValueRule: 30%")
    print(f"    MaxDrawdownRule: 20%")

    print(f"\n[4] 加载策略")
    engine.use_strategy(
        MaMultiBreakoutStrategy,
        setting={
            "ma20_window": 20,
            "ma250_window": 250,
            "position_pct": position_pct,
        },
    )
    print(f"    策略: MaMultiBreakoutStrategy")
    print(f"    MA窗口: 20/250日")
    print(f"    入场条件: 突破20日线且股价在250日线上方")
    print(f"    仓位比例: {position_pct * 100:.0f}%")
    print(f"    追踪止损: 5%")

    print(f"\n[5] 运行回测")
    stats = engine.run()
    print(f"    回测完成")

    print(f"\n[6] 统计指标")
    print("-" * 50)
    engine.print_stats()

    print(f"\n[7] 风控统计")
    risk_stats = engine.get_risk_stats()
    print(f"    启用规则数: {risk_stats.get('rule_count')}")
    print(f"    拒绝次数:   {risk_stats.get('rejected_count')}")
    print(f"    警告次数:   {risk_stats.get('warned_count')}")

    print(f"\n[8] 成交记录")
    trades = engine.get_trades()
    print(f"    总成交笔数: {len(trades)}")
    if trades:
        print(f"    {'='*80}")
        print(f"    {'日期':<12} {'方向':<6} {'开/平':<6} {'价格':<10} {'数量':<8} {'合约乘数':<10} {'成交额':<15} {'手续费':<10}")
        print(f"    {'-'*80}")

        total_commission = 0
        for i, trade in enumerate(trades, 1):
            size = 100
            turnover = trade.price * trade.volume * size
            commission = turnover * 0.0003
            total_commission += commission
            direction = "买入" if trade.direction.value == "long" else "卖出"
            offset = "开仓" if trade.offset.value in ["open", "none"] else "平仓"
            print(f"    {str(trade.datetime)[:10]:<12} {direction:<6} {offset:<6} {trade.price:<10.2f} {trade.volume:<8.0f} {size:<10} {turnover:<15,.2f} {commission:<10.2f}")

        print(f"    {'='*80}")
        print(f"    手续费合计: {total_commission:.2f}")

        print(f"\n    [交易明细]")
        i = 0
        while i < len(trades):
            entry = trades[i]
            if entry.offset.value in ["open", "none"]:
                exit_trade = trades[i + 1] if i + 1 < len(trades) else None
                if exit_trade:
                    size = 100
                    entry_turnover = entry.price * entry.volume * size
                    exit_turnover = exit_trade.price * exit_trade.volume * size
                    pnl = (exit_trade.price - entry.price) * entry.volume * size
                    pnl -= entry_turnover * 0.0003
                    pnl -= exit_turnover * 0.0003
                    holding_days = (exit_trade.datetime - entry.datetime).days
                    entry_date = str(entry.datetime)[:10]
                    exit_date = str(exit_trade.datetime)[:10]
                    print(f"    第{(i//2)+1}笔: 买入{entry_date}@{entry.price:.2f} -> 卖出{exit_date}@{exit_trade.price:.2f} | 持仓{holding_days}天 | 盈亏{pnl:.2f}")
                i += 2
            else:
                i += 1

    print(f"\n[9] 绘制图表")
    try:
        engine.plot(output_path="backtest_result.html")
        print(f"    图表已保存: backtest_result.html")
    except Exception as e:
        print(f"    图表生成失败: {e}")
        print(f"    请确保已安装 plotly: pip install plotly")

    print("\n" + "=" * 60)
    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MA多周期过滤突破策略回测")
    parser.add_argument("symbol", help="股票代码，如 000001")
    parser.add_argument("market", help="市场，如 sz 或 sh", choices=["sz", "sh"])
    parser.add_argument("--start", "-s", default="2024-01-01", help="起始日期，如 2024-01-01")
    parser.add_argument("--end", "-e", default="2026-04-20", help="结束日期，如 2026-04-20")
    parser.add_argument("--position-pct", "-p", type=float, default=1.0, help="仓位比例，如 0.15 表示15%%")
    args = parser.parse_args()

    start_date = datetime.strptime(args.start, "%Y-%m-%d")
    end_date = datetime.strptime(args.end, "%Y-%m-%d")

    run_backtest(args.symbol, args.market, start_date, end_date, args.position_pct)
