"""
Debug test for the backtest engine.
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
from trade_plus.backtest.strategies import MaBreakoutStrategy


def generate_bars():
    bars = []
    p = 100.0
    d = datetime(2023, 1, 1)
    random.seed(42)
    for i in range(500):
        r = random.gauss(0.0003, 0.012)
        o = p
        h = p * (1 + abs(r) * random.uniform(0.3, 0.8))
        l = p * (1 - abs(r) * random.uniform(0.3, 0.8))
        c = p * (1 + r)
        bars.append(BarData(
            symbol="TEST",
            exchange=Exchange.SZSE,
            datetime=d,
            interval=Interval.DAILY,
            open_price=round(o, 2),
            high_price=round(h, 2),
            low_price=round(l, 2),
            close_price=round(c, 2),
            volume=round(random.uniform(5000, 50000), 2),
            gateway_name="SIM",
        ))
        p = c
        d += timedelta(days=1)
        if d.weekday() >= 5:
            d += timedelta(days=7 - d.weekday())
    return bars


def main():
    bars = generate_bars()
    print(f"Generated {len(bars)} bars")
    print(f"First bar: {bars[0].datetime}  close={bars[0].close_price}")
    print(f"Last bar: {bars[-1].datetime}  close={bars[-1].close_price}")

    # Check dts count
    dts = set(bar.datetime for bar in bars)
    print(f"Unique datetimes: {len(dts)}")

    engine = (
        BacktestEngine(initial_capital=500_000.0)
        .set_symbols(["TEST.SZSE"])
        .set_period(datetime(2023, 1, 1), bars[-1].datetime)
        .add_contract("TEST.SZSE", size=100, long_rate=0.0003, short_rate=0.0003, pricetick=0.01)
        .set_data("TEST.SZSE", bars)
        .use_strategy(MaBreakoutStrategy, {"ma_window": 20, "price_add": 0.001})
    )

    stats = engine.run()
    trades = engine.get_trades()

    print(f"\nResult:")
    print(f"  total_days: {stats.get('total_days')}")
    print(f"  trades: {len(trades)}")
    print(f"  total_pnl: {stats.get('total_pnl')}")
    print(f"  end_balance: {stats.get('end_balance')}")

    if not trades:
        print("\nNo trades! Checking logs:")
        logs = engine.get_logs()
        for log in logs[:20]:
            print(f"  {log}")


if __name__ == "__main__":
    main()
