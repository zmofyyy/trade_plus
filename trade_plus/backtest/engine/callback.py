from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from .execution import ExecutionEngine


class StrategyCallback(metaclass=ABCMeta):
    """策略回调接口，由策略实现"""

    @abstractmethod
    def on_init(self) -> None:
        """策略初始化回调"""
        pass

    @abstractmethod
    def on_bars(self, bars: dict[str, "BarData"]) -> None:
        """K线切片回调"""
        pass

    @abstractmethod
    def on_trade(self, trade: "TradeData") -> None:
        """成交回报回调"""
        pass
