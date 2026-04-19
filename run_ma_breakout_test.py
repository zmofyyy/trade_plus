"""
20日均线突破策略回测测试

生成模拟K线数据，运行回测，输出结果。
"""

import random
from datetime import datetime, timedelta

from trade_plus.backtest import (
    BacktestEngine,
    BarData,
    Interval,
    Exchange,
    RiskControlLayer,
)
from trade_plus.backtest.risk import (
    MaxPositionPerSymbolRule,
    MaxSingleOrderValueRule,
    MaxDrawdownRule,
)
from trade_plus.backtest.strategies import MaBreakoutStrategy
from trade_plus.backtest.visual import plot_full_report


def generate_ohlcv_bars(
    symbol: str,
    exchange: Exchange,
    start_date: datetime,
    num_bars: int,
    base_price: float = 100.0,
    trend: float = 0.0002,
    volatility: float = 0.015,
) -> list[BarData]:
    """
    生成带趋势的OHLCV模拟K线。

    Args:
        symbol: 合约代码
        exchange: 交易所
        start_date: 起始日期
        num_bars: K线数量
        base_price: 起始价格
        trend: 每根K线的趋势偏移（正数=上涨趋势）
        volatility: 波动率

    Returns:
        BarData列表
    """
    bars = []
    current_price = base_price
    current_date = start_date

    random.seed(42)

    for i in range(num_bars):
        daily_return = random.gauss(trend, volatility)

        open_price = current_price
        high_price = open_price * (1 + abs(daily_return) * random.uniform(0.3, 0.8))
        low_price = open_price * (1 - abs(daily_return) * random.uniform(0.3, 0.8))
        close_price = open_price * (1 + daily_return)

        high_price = max(open_price, close_price, high_price)
        low_price = min(open_price, close_price, low_price)

        volume = random.uniform(5000, 50000)

        bar = BarData(
            symbol=symbol,
            exchange=exchange,
            datetime=current_date,
            interval=Interval.DAILY,
            open_price=round(open_price, 2),
            high_price=round(high_price, 2),
            low_price=round(low_price, 2),
            close_price=round(close_price, 2),
            volume=round(volume, 2),
            gateway_name="SIMULATION",
        )
        bars.append(bar)

        current_price = close_price
        current_date += timedelta(days=1)

        if current_date.weekday() == 6:
            current_date += timedelta(days=1)
        elif current_date.weekday() == 5:
            current_date += timedelta(days=2)

    return bars


def run_backtest():
    SYMBOL = "000001"
    EXCHANGE = Exchange.SZSE
    START = datetime(2023, 1, 1)
    NUM_BARS = 500

    print("=" * 60)
    print("20日均线突破策略 — 回测测试")
    print("=" * 60)

    print(f"\n[1] 生成模拟数据")
    bars = generate_ohlcv_bars(
        symbol=SYMBOL,
        exchange=EXCHANGE,
        start_date=START,
        num_bars=NUM_BARS,
        base_price=100.0,
        trend=0.0003,
        volatility=0.012,
    )
    print(f"    标的: {SYMBOL}.{EXCHANGE.value}")
    print(f"    K线数: {len(bars)}")
    print(f"    起始价: {bars[0].close_price:.2f}")
    print(f"    结束价: {bars[-1].close_price:.2f}")

    print(f"\n[2] 配置回测引擎")
    engine = (
        BacktestEngine(initial_capital=500_000.0)
        .set_symbols([f"{SYMBOL}.{EXCHANGE.value}"])
        .set_period(START, bars[-1].datetime)
        .add_contract(
            f"{SYMBOL}.{EXCHANGE.value}",
            size=100,
            long_rate=0.0003,
            short_rate=0.0003,
            pricetick=0.01,
        )
        .set_data(f"{SYMBOL}.{EXCHANGE.value}", bars)
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
        MaBreakoutStrategy,
        setting={
            "ma_window": 20,
            "price_add": 0.001,
        },
    )
    print(f"    策略: MaBreakoutStrategy")
    print(f"    均线窗口: 20日")
    print(f"    滑点: 0.1%")

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
        print(f"    首笔成交: {trades[0].datetime}  价格:{trades[0].price:.2f}")
        print(f"    末笔成交: {trades[-1].datetime}  价格:{trades[-1].price:.2f}")

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
    run_backtest()
