"""
MA突破策略

规则：
- 多头入场：收盘价上穿20日均线，且股价在250日均线上方
- 退出方式：移动追踪止损，跌破持仓期间最高价×95%时以当天收盘价卖出

纯多头策略，按仓位比例入场。
"""

from collections import defaultdict
from typing import TYPE_CHECKING

from ..data import BarData, TradeData, Direction
from ..strategy.template import Strategy


class MaMultiBreakoutStrategy(Strategy):
    """
    MA突破策略。

    入场条件：
        收盘价从下往上突破20日均线
        且收盘价在250日均线上方

    退出方式：
        移动追踪止损：持仓期间最高价 × 95%

    特点：
        - 纯多头，不做空
        - 按仓位比例入场
        - 入场/止损都以当天收盘价执行
    """

    strategy_name = "MaMultiBreakout"
    author = "trade_plus"

    ma20_window: int = 20
    ma250_window: int = 250
    position_pct: float = 1.0

    def __init__(
        self,
        execution_engine,
        strategy_name: str,
        vt_symbols: list[str],
        setting: dict,
    ):
        super().__init__(execution_engine, strategy_name, vt_symbols, setting)
        self._prices: dict[str, list[float]] = defaultdict(list)
        self._entry_price: dict[str, float] = defaultdict(float)
        self._highest_price: dict[str, float] = defaultdict(float)
        self._exit_bar_date: dict[str, object] = defaultdict(lambda: None)

    def _calc_volume(self, vt_symbol: str, price: float) -> int:
        portfolio_value = self._engine.get_portfolio_value()
        target_value = portfolio_value * self.position_pct
        size = self._engine.get_contract_size(vt_symbol)
        volume = int(target_value / price / size)
        if volume < 1:
            volume = 1
        return volume

    def on_init(self) -> None:
        self.write_log(f"{self.strategy_name} 策略初始化")
        self.write_log(f"MA窗口: {self.ma20_window}/{self.ma250_window}")
        self.write_log(f"仓位比例: {self.position_pct * 100:.0f}%")

    def on_trade(self, trade: TradeData) -> None:
        direction_text = "买入" if trade.direction == Direction.LONG else "卖出"
        self.write_log(
            f"成交回报 | {trade.vt_symbol} | "
            f"方向={direction_text} | "
            f"价格={trade.price:.2f} | 数量={trade.volume}"
        )

    def on_bars(self, bars: dict[str, BarData]) -> None:
        for vt_symbol, bar in bars.items():
            if bar.close_price <= 0:
                continue

            self._prices[vt_symbol].append(bar.close_price)

            if len(self._prices[vt_symbol]) < self.ma250_window + 1:
                continue

            prices = self._prices[vt_symbol]

            ma20 = sum(prices[-self.ma20_window:]) / self.ma20_window
            ma250 = sum(prices[-self.ma250_window:]) / self.ma250_window

            prev_ma20 = sum(prices[-self.ma20_window - 1:-1]) / self.ma20_window
            prev_close = prices[-2]

            pos = self.get_pos(vt_symbol)

            if pos > 0:
                self._highest_price[vt_symbol] = max(
                    self._highest_price[vt_symbol], bar.close_price
                )
                trailing_stop = self._highest_price[vt_symbol] * 0.95
                if bar.close_price <= trailing_stop:
                    self.write_log(
                        f"止损触发 | {vt_symbol} | "
                        f"持仓最高价={self._highest_price[vt_symbol]:.2f} | "
                        f"追踪止损={trailing_stop:.2f} | "
                        f"当前收盘={bar.close_price:.2f}"
                    )
                    self.exit_long(vt_symbol, trailing_stop, pos)
                    self.set_target(vt_symbol, 0.0)
                    self._highest_price[vt_symbol] = 0.0
                    self._entry_price[vt_symbol] = 0.0
                    self._exit_bar_date[vt_symbol] = bar.datetime.date()

            elif pos == 0:
                if self._exit_bar_date.get(vt_symbol) == bar.datetime.date():
                    continue

                price_broke_above = bar.close_price >= ma20 and prev_close < prev_ma20
                above_ma250 = bar.close_price > ma250

                if price_broke_above and above_ma250:
                    volume = self._calc_volume(vt_symbol, bar.close_price)
                    self.write_log(
                        f"入场信号 | {vt_symbol} | "
                        f"收盘价={bar.close_price:.2f} | "
                        f"MA20={ma20:.2f} | MA250={ma250:.2f} | 数量={volume}手"
                    )
                    self.entry_long(vt_symbol, bar.close_price, volume)
                    self.set_target(vt_symbol, float(volume))
                    self._entry_price[vt_symbol] = bar.close_price
                    self._highest_price[vt_symbol] = bar.high_price