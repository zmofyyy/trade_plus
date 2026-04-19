"""
20日均线突破策略

规则：
- 多头入场：收盘价上穿20日均线
- 空头入场：收盘价下穿20日均线
- 平仓：反向信号出现时平仓

这是一个纯多头策略，仅做多，不做空。
"""

from collections import defaultdict
from typing import TYPE_CHECKING

from ..data import BarData, TradeData, Direction
from ..strategy.template import Strategy


class MaBreakoutStrategy(Strategy):
    """
    20日均线突破策略。

    入场条件：
        收盘价从下往上突破20日均线 -> 做多

    出场条件：
        收盘价从上往下跌破20日均线 -> 平多

    特点：
        - 纯多头，不做空
        - 每次全仓操作1手
        - 简单的固定止损（可扩展）
    """

    strategy_name = "MaBreakout"
    author = "trade_plus"

    ma_window: int = 20        # 均线窗口期
    price_add: float = 0.001   # 下单价格偏移（滑点）

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
        self.write_log(f"{self.strategy_name} 策略初始化")
        self.write_log(f"均线窗口：{self.ma_window} 日")

    def on_trade(self, trade: TradeData) -> None:
        self.write_log(
            f"成交回报 | {trade.vt_symbol} | "
            f"方向={'买入' if trade.direction == Direction.LONG else '卖出'} | "
            f"价格={trade.price:.2f} | 数量={trade.volume}"
        )

    def on_bars(self, bars: dict[str, BarData]) -> None:
        for vt_symbol, bar in bars.items():
            if bar.close_price <= 0:
                continue

            self._prices[vt_symbol].append(bar.close_price)

            if len(self._prices[vt_symbol]) < self.ma_window + 1:
                continue

            prices = self._prices[vt_symbol][-self.ma_window:]

            ma = sum(prices) / len(prices)

            pos = self.get_pos(vt_symbol)

            if bar.close_price > ma and pos == 0:
                order_price = bar.close_price * (1 + self.price_add)
                self.buy(vt_symbol, order_price, volume=1.0)
                self.set_target(vt_symbol, 1.0)

            elif bar.close_price < ma and pos > 0:
                order_price = bar.close_price * (1 - self.price_add)
                self.sell(vt_symbol, order_price, pos)
                self.set_target(vt_symbol, 0.0)
