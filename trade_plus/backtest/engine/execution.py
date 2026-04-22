from __future__ import annotations

from abc import ABCMeta, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from ..data import OrderData, TradeData, BarData, Direction, Offset

if TYPE_CHECKING:
    from ..strategy.template import Strategy


class ExecutionEngine(metaclass=ABCMeta):
    """
    交易执行引擎抽象接口。

    策略不直接依赖 BacktestingEngine，而是依赖这个抽象接口。
    实盘引擎、回测引擎都实现此接口，策略可以无差别调用。
    """

    @abstractmethod
    def send_order(
        self,
        strategy: "Strategy",
        vt_symbol: str,
        direction: "Direction",
        offset: "Offset",
        price: float,
        volume: float,
    ) -> list[str]:
        """
        发送订单。

        Returns:
            list[str]: 订单vt_orderid列表
        """
        pass

    @abstractmethod
    def cancel_order(self, strategy: "Strategy", vt_orderid: str) -> None:
        """撤销订单"""
        pass

    @abstractmethod
    def get_pos(self, vt_symbol: str) -> float:
        """查询当前持仓"""
        pass

    @abstractmethod
    def get_cash_available(self) -> float:
        """查询可用资金"""
        pass

    @abstractmethod
    def get_holding_value(self) -> float:
        """查询持仓市值"""
        pass

    @abstractmethod
    def get_portfolio_value(self) -> float:
        """查询总权益"""
        pass

    @abstractmethod
    def get_bar(self, vt_symbol: str) -> BarData | None:
        """查询当前K线数据"""
        pass

    @abstractmethod
    def get_contract_size(self, vt_symbol: str) -> float:
        """查询合约乘数"""
        pass

    @abstractmethod
    def get_pricetick(self, vt_symbol: str) -> float:
        """查询价格跳动"""
        pass

    @abstractmethod
    def get_current_drawdown(self) -> tuple[float, float]:
        """查询当前回撤 (dd, dd_pct)"""
        pass

    @abstractmethod
    def write_log(self, msg: str, strategy: Optional["Strategy"] = None) -> None:
        """输出日志"""
        pass

    @abstractmethod
    def get_datetime(self) -> Optional[datetime]:
        """获取当前回测/实盘时间"""
        pass

    @abstractmethod
    def direct_trade(
        self,
        strategy: "Strategy",
        vt_symbol: str,
        direction: "Direction",
        offset: "Offset",
        price: float,
        volume: float,
    ) -> "TradeData":
        """
        直接成交，不经过订单撮合。

        用于止损等需要立即成交的场景。
        """
        pass
