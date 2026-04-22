from abc import ABCMeta, abstractmethod
from collections import defaultdict
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..engine.execution import ExecutionEngine
    from ..data import BarData, TradeData, OrderData, Direction, Offset

from ..data import BarData, TradeData, OrderData, Direction, Offset


class Strategy:
    """
    策略基类。

    策略通过 ExecutionEngine 接口与执行层交互，
    不直接依赖 BacktestingEngine，实现策略与回测/实盘引擎的解耦。
    """

    strategy_name: str = "Strategy"
    author: str = ""

    def __init__(
        self,
        execution_engine: "ExecutionEngine",
        strategy_name: str,
        vt_symbols: list[str],
        setting: dict,
    ) -> None:
        self._engine: "ExecutionEngine" = execution_engine
        self.strategy_name: str = strategy_name
        self.vt_symbols: list[str] = vt_symbols

        self.pos_data: dict[str, float] = defaultdict(float)
        self.target_data: dict[str, float] = defaultdict(float)

        self.orders: dict[str, OrderData] = {}
        self.active_orderids: set[str] = set()

        for k, v in setting.items():
            if hasattr(self, k):
                setattr(self, k, v)

    @abstractmethod
    def on_init(self) -> None:
        """策略初始化回调"""
        pass

    @abstractmethod
    def on_bars(self, bars: dict[str, BarData]) -> None:
        """K线切片回调"""
        pass

    @abstractmethod
    def on_trade(self, trade: TradeData) -> None:
        """成交回报回调"""
        pass

    def update_trade(self, trade: TradeData) -> None:
        if trade.direction == Direction.LONG:
            self.pos_data[trade.vt_symbol] += trade.volume
        else:
            self.pos_data[trade.vt_symbol] -= trade.volume
        self.on_trade(trade)

    def update_order(self, order: OrderData) -> None:
        self.orders[order.vt_orderid] = order
        if not order.is_active and order.vt_orderid in self.active_orderids:
            self.active_orderids.remove(order.vt_orderid)

    def buy(
        self, vt_symbol: str, price: float, volume: float
    ) -> list[str]:
        return self.send_order(vt_symbol, Direction.LONG, Offset.OPEN, price, volume)

    def sell(
        self, vt_symbol: str, price: float, volume: float
    ) -> list[str]:
        return self.send_order(vt_symbol, Direction.SHORT, Offset.CLOSE, price, volume)

    def short(
        self, vt_symbol: str, price: float, volume: float
    ) -> list[str]:
        return self.send_order(vt_symbol, Direction.SHORT, Offset.OPEN, price, volume)

    def cover(
        self, vt_symbol: str, price: float, volume: float
    ) -> list[str]:
        return self.send_order(vt_symbol, Direction.LONG, Offset.CLOSE, price, volume)

    def exit_long(
        self, vt_symbol: str, price: float, volume: float
    ) -> "TradeData":
        return self._engine.direct_trade(
            self, vt_symbol, Direction.SHORT, Offset.CLOSE, price, volume
        )

    def entry_long(
        self, vt_symbol: str, price: float, volume: float
    ) -> "TradeData":
        return self._engine.direct_trade(
            self, vt_symbol, Direction.LONG, Offset.OPEN, price, volume
        )

    def send_order(
        self,
        vt_symbol: str,
        direction: Direction,
        offset: Offset,
        price: float,
        volume: float,
    ) -> list[str]:
        vt_orderids: list = self._engine.send_order(
            self, vt_symbol, direction, offset, price, volume
        )
        for vt_orderid in vt_orderids:
            self.active_orderids.add(vt_orderid)
        return vt_orderids

    def cancel_order(self, vt_orderid: str) -> None:
        self._engine.cancel_order(self, vt_orderid)

    def cancel_all(self) -> None:
        for vt_orderid in list(self.active_orderids):
            self.cancel_order(vt_orderid)

    def get_pos(self, vt_symbol: str) -> float:
        return self.pos_data.get(vt_symbol, 0.0)

    def get_target(self, vt_symbol: str) -> float:
        return self.target_data.get(vt_symbol, 0.0)

    def set_target(self, vt_symbol: str, target: float) -> None:
        self.target_data[vt_symbol] = target

    def execute_trading(self, bars: dict[str, BarData], price_add: float = 0.0) -> None:
        """
        根据目标持仓自动调仓。

        Args:
            bars: 当前K线字典
            price_add: 下单价格偏移比例（正数为向上偏移，负数向下偏移）
        """
        self.cancel_all()

        for vt_symbol, bar in bars.items():
            target: float = self.get_target(vt_symbol)
            pos: float = self.get_pos(vt_symbol)
            diff: float = target - pos

            if abs(diff) < 1e-9:
                continue

            if price_add > 0:
                order_price = bar.close_price * (1 + price_add)
            elif price_add < 0:
                order_price = bar.close_price * (1 + price_add)
            else:
                order_price = bar.close_price

            if diff > 0:
                cover_volume: float = 0.0
                buy_volume: float = 0.0

                if pos < 0:
                    cover_volume = min(diff, abs(pos))
                    buy_volume = diff - cover_volume
                else:
                    buy_volume = diff

                if cover_volume > 0:
                    self.cover(vt_symbol, order_price, cover_volume)
                if buy_volume > 0:
                    self.buy(vt_symbol, order_price, buy_volume)

            elif diff < 0:
                sell_volume: float = 0.0
                short_volume: float = 0.0

                if pos > 0:
                    sell_volume = min(abs(diff), pos)
                    short_volume = abs(diff) - sell_volume
                else:
                    short_volume = abs(diff)

                if sell_volume > 0:
                    self.sell(vt_symbol, order_price, sell_volume)
                if short_volume > 0:
                    self.short(vt_symbol, order_price, short_volume)

    def write_log(self, msg: str) -> None:
        self._engine.write_log(msg, self)

    def get_cash_available(self) -> float:
        return self._engine.get_cash_available()

    def get_holding_value(self) -> float:
        return self._engine.get_holding_value()

    def get_portfolio_value(self) -> float:
        return self._engine.get_portfolio_value()
