"""
trade_plus 回测框架使用示例

演示如何：
1. 创建回测引擎
2. 注入历史K线数据
3. 配置合约参数
4. 加载策略
5. 运行回测并查看结果
"""

from datetime import datetime, date

from trade_plus.backtest import (
    BacktestEngine,
    BarData,
    Interval,
    Exchange,
    RiskControlLayer,
    Direction,
)
from trade_plus.backtest.risk import MaxPositionPerSymbolRule, MaxDrawdownRule
from trade_plus.backtest.strategies import DualMovingAverageStrategy


def generate_sample_data(
    symbol: str, exchange: Exchange, days: int = 100, base_price: float = 100.0
) -> list[BarData]:
    """生成模拟K线数据用于演示"""
    import random
    bars = []
    current_price = base_price
    current_date = datetime(2024, 1, 1)

    for i in range(days):
        change = random.gauss(0, 1)
        open_price = current_price
        high_price = open_price * (1 + abs(change) * 0.5)
        low_price = open_price * (1 - abs(change) * 0.5)
        close_price = open_price * (1 + change * 0.01)
        volume = random.uniform(1000, 10000)

        bar = BarData(
            symbol=symbol,
            exchange=exchange,
            datetime=current_date,
            interval=Interval.DAILY,
            open_price=open_price,
            high_price=high_price,
            low_price=low_price,
            close_price=close_price,
            volume=volume,
            gateway_name="SAMPLE",
        )
        bars.append(bar)

        current_price = close_price
        current_date = datetime(
            year=current_date.year,
            month=current_date.month,
            day=current_date.day + 1,
        )
        if current_date.weekday() >= 5:
            current_date = datetime(
                year=current_date.year,
                month=current_date.month,
                day=current_date.day + (7 - current_date.weekday()),
            )

    return bars


def main():
    print("=" * 60)
    print("trade_plus 回测框架演示")
    print("=" * 60)

    SYMBOL = "000001"
    EXCHANGE = Exchange.SZSE

    print(f"\n[1] 生成模拟数据: {SYMBOL}.{EXCHANGE.value}")
    bars = generate_sample_data(SYMBOL, EXCHANGE, days=200, base_price=100.0)
    print(f"    生成 {len(bars)} 根日K线")
    print(f"    数据区间: {bars[0].datetime.date()} ~ {bars[-1].datetime.date()}")

    print("\n[2] 配置回测引擎")
    engine = (
        BacktestEngine(initial_capital=1_000_000.0)
        .set_symbols([f"{SYMBOL}.{EXCHANGE.value}"])
        .set_period(datetime(2024, 1, 1), datetime(2024, 12, 31))
        .add_contract(
            f"{SYMBOL}.{EXCHANGE.value}",
            size=100,
            long_rate=0.0003,
            short_rate=0.0003,
            pricetick=0.01,
        )
        .set_data(f"{SYMBOL}.{EXCHANGE.value}", bars)
    )

    print("\n[3] 配置风控规则")
    risk_layer = RiskControlLayer.default()
    risk_layer.add_rule(MaxPositionPerSymbolRule(max_pct=0.3))
    risk_layer.add_rule(MaxDrawdownRule(max_drawdown_pct=0.15))
    engine.use_risk_layer(risk_layer)

    print("\n[4] 加载策略")
    engine.use_strategy(
        DualMovingAverageStrategy,
        setting={
            "fast_window": 5,
            "slow_window": 20,
            "price_add": 0.001,
        },
    )
    print("    策略: DualMovingAverageStrategy")
    print("    参数: fast_window=5, slow_window=20")

    print("\n[5] 运行回测")
    stats = engine.run()
    print("    回测完成")

    print("\n[6] 统计指标")
    engine.print_stats(stats)

    print("\n[7] 风控统计")
    risk_stats = engine.get_risk_stats()
    print(f"    启用: {risk_stats.get('enabled')}")
    print(f"    规则数: {risk_stats.get('rule_count')}")
    print(f"    拒绝次数: {risk_stats.get('rejected_count')}")
    print(f"    警告次数: {risk_stats.get('warned_count')}")

    print("\n[8] 绘图（如已安装plotly）")
    try:
        engine.plot()
        print("    图表已显示")
    except Exception as e:
        print(f"    绘图跳过: {e}")


if __name__ == "__main__":
    main()
