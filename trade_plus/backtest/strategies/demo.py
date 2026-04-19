from collections import defaultdict

from ..data import BarData, TradeData, Direction
from ..strategy.template import Strategy


class DualMovingAverageStrategy(Strategy):
    """
    双均线策略示例。

    - 多头：短期均线上穿长期均线
    - 空头：短期均线下穿长期均线
    """

    strategy_name = "DualMovingAverage"

    fast_window: int = 5
    slow_window: int = 20
    price_add: float = 0.001

    def __init__(
        self,
        execution_engine,
        strategy_name: str,
        vt_symbols: list[str],
        setting: dict,
    ):
        super().__init__(execution_engine, strategy_name, vt_symbols, setting)
        self._prices: dict[str, list[float]] = defaultdict(list)
        self._holding_days: dict[str, int] = defaultdict(int)

    def on_init(self) -> None:
        self.write_log("双均线策略初始化")

    def on_trade(self, trade: TradeData) -> None:
        if trade.direction == Direction.SHORT:
            self._holding_days.pop(trade.vt_symbol, None)

    def on_bars(self, bars: dict[str, BarData]) -> None:
        for vt_symbol, bar in bars.items():
            if bar.close_price <= 0:
                continue

            self._prices[vt_symbol].append(bar.close_price)

            if len(self._prices[vt_symbol]) < self.slow_window:
                continue

            prices = self._prices[vt_symbol][-self.slow_window:]

            fast_ma = sum(prices[-self.fast_window:]) / self.fast_window
            slow_ma = sum(prices[-self.slow_window:]) / self.slow_window

            pos = self.get_pos(vt_symbol)

            if fast_ma > slow_ma and pos <= 0:
                target_volume = 1.0
                if pos < 0:
                    self.cover(vt_symbol, bar.close_price * (1 + self.price_add), abs(pos))
                self.buy(vt_symbol, bar.close_price * (1 + self.price_add), target_volume)
                self.set_target(vt_symbol, target_volume)

            elif fast_ma < slow_ma and pos >= 0:
                if pos > 0:
                    self.sell(vt_symbol, bar.close_price * (1 - self.price_add), pos)
                self.set_target(vt_symbol, 0)


class MeanReversionStrategy(Strategy):
    """
    均值回归策略示例。

    - 价格偏离均值超过阈值时反向交易
    - 回归时平仓
    """

    strategy_name = "MeanReversion"

    window: int = 20
    entry_threshold: float = 2.0
    exit_threshold: float = 0.5
    price_add: float = 0.001

    def __init__(
        self,
        execution_engine,
        strategy_name: str,
        vt_symbols: list[str],
        setting: dict,
    ):
        super().__init__(execution_engine, strategy_name, vt_symbols, setting)
        self._prices: dict[str, list[float]] = defaultdict(list)

    def on_init(self) -> None:
        self.write_log("均值回归策略初始化")

    def on_bars(self, bars: dict[str, BarData]) -> None:
        for vt_symbol, bar in bars.items():
            if bar.close_price <= 0:
                continue

            self._prices[vt_symbol].append(bar.close_price)

            if len(self._prices[vt_symbol]) < self.window:
                continue

            prices = self._prices[vt_symbol][-self.window:]
            mean = sum(prices) / len(prices)
            std = (sum((p - mean) ** 2 for p in prices) / len(prices)) ** 0.5

            pos = self.get_pos(vt_symbol)
            z_score = (bar.close_price - mean) / std if std > 0 else 0

            if z_score < -self.entry_threshold and pos <= 0:
                target = 1.0
                if pos < 0:
                    self.cover(vt_symbol, bar.close_price * (1 + self.price_add), abs(pos))
                self.buy(vt_symbol, bar.close_price * (1 + self.price_add), target)
                self.set_target(vt_symbol, target)

            elif z_score > -self.exit_threshold and pos > 0:
                self.sell(vt_symbol, bar.close_price * (1 - self.price_add), pos)
                self.set_target(vt_symbol, 0)

            elif z_score > self.entry_threshold and pos >= 0:
                target = -1.0
                if pos > 0:
                    self.sell(vt_symbol, bar.close_price * (1 - self.price_add), pos)
                self.short(vt_symbol, bar.close_price * (1 - self.price_add), abs(target))
                self.set_target(vt_symbol, target)

            elif z_score < self.exit_threshold and pos < 0:
                self.cover(vt_symbol, bar.close_price * (1 + self.price_add), abs(pos))
                self.set_target(vt_symbol, 0)
