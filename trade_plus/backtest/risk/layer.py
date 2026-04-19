from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from enum import Enum

from ..data import Direction, Offset, OrderData, TradeData, BarData

if TYPE_CHECKING:
    from ..engine.execution import ExecutionEngine


class RiskLevel(Enum):
    PASS = "pass"
    REJECT = "reject"
    WARN = "warn"


@dataclass
class RiskCheckResult:
    passed: bool
    level: RiskLevel
    message: str
    adjusted_volume: float | None = None


@dataclass
class RiskRule:
    name: str
    enabled: bool = True

    def check(
        self,
        order: OrderData,
        engine: "ExecutionEngine",
    ) -> RiskCheckResult:
        raise NotImplementedError


class MaxPositionPerSymbolRule(RiskRule):
    def __init__(self, max_pct: float = 0.2):
        super().__init__("max_position_per_symbol")
        self.max_pct = max_pct

    def check(
        self,
        order: OrderData,
        engine: "ExecutionEngine",
    ) -> RiskCheckResult:
        portfolio_value = engine.get_portfolio_value()
        if portfolio_value <= 0:
            return RiskCheckResult(True, RiskLevel.PASS, "portfolio_value <= 0, skip")

        pos = engine.get_pos(order.vt_symbol)
        size = engine.get_contract_size(order.vt_symbol)
        price = order.price

        if order.offset in (Offset.CLOSE, Offset.CLOSETODAY, Offset.CLOSEYESTERDAY):
            return RiskCheckResult(True, RiskLevel.PASS, "close order, skip position check")

        target_pos_value = abs(pos + order.volume) * price * size
        pct = target_pos_value / portfolio_value

        if pct > self.max_pct:
            max_vol = int((portfolio_value * self.max_pct) / (price * size))
            if max_vol <= 0:
                return RiskCheckResult(
                    False, RiskLevel.REJECT,
                    f"position {pct:.2%} exceeds limit {self.max_pct:.2%}"
                )
            return RiskCheckResult(
                False, RiskLevel.WARN,
                f"position capped from {order.volume} to {max_vol}",
                adjusted_volume=float(max_vol)
            )

        return RiskCheckResult(True, RiskLevel.PASS, "ok")


class MaxTotalPositionRule(RiskRule):
    def __init__(self, max_pct: float = 0.95):
        super().__init__("max_total_position")
        self.max_pct = max_pct

    def check(
        self,
        order: OrderData,
        engine: "ExecutionEngine",
    ) -> RiskCheckResult:
        portfolio_value = engine.get_portfolio_value()
        available = engine.get_cash_available()
        if portfolio_value <= 0:
            return RiskCheckResult(True, RiskLevel.PASS, "portfolio_value <= 0, skip")

        if order.offset in (Offset.CLOSE, Offset.CLOSETODAY, Offset.CLOSEYESTERDAY):
            return RiskCheckResult(True, RiskLevel.PASS, "close order, skip")

        size = engine.get_contract_size(order.vt_symbol)
        order_value = order.volume * order.price * size
        current_holding_value = engine.get_holding_value()

        total_target = current_holding_value + order_value
        pct = total_target / portfolio_value

        if pct > self.max_pct:
            max_value = portfolio_value * self.max_pct - current_holding_value
            if max_value <= 0:
                return RiskCheckResult(
                    False, RiskLevel.REJECT,
                    f"total position {pct:.2%} exceeds limit {self.max_pct:.2%}"
                )
            max_vol = int(max_value / (order.price * size))
            if max_vol <= 0:
                return RiskCheckResult(
                    False, RiskLevel.REJECT,
                    f"total position capped to 0"
                )
            return RiskCheckResult(
                False, RiskLevel.WARN,
                f"total position capped from {order.volume} to {max_vol}",
                adjusted_volume=float(max_vol)
            )

        return RiskCheckResult(True, RiskLevel.PASS, "ok")


class MaxOrderSizeRule(RiskRule):
    def __init__(self, max_size: float = 1000):
        super().__init__("max_order_size")
        self.max_size = max_size

    def check(
        self,
        order: OrderData,
        engine: "ExecutionEngine",
    ) -> RiskCheckResult:
        if order.volume > self.max_size:
            return RiskCheckResult(
                False, RiskLevel.REJECT,
                f"order size {order.volume} exceeds max {self.max_size}"
            )
        return RiskCheckResult(True, RiskLevel.PASS, "ok")


class MinOrderSizeRule(RiskRule):
    def __init__(self, min_size: float = 1):
        super().__init__("min_order_size")
        self.min_size = min_size

    def check(
        self,
        order: OrderData,
        engine: "ExecutionEngine",
    ) -> RiskCheckResult:
        if order.volume < self.min_size:
            return RiskCheckResult(
                False, RiskLevel.REJECT,
                f"order size {order.volume} below min {self.min_size}"
            )
        return RiskCheckResult(True, RiskLevel.PASS, "ok")


class MaxDrawdownRule(RiskRule):
    def __init__(self, max_drawdown_pct: float = 0.2):
        super().__init__("max_drawdown")
        self.max_drawdown_pct = max_drawdown_pct

    def check(
        self,
        order: OrderData,
        engine: "ExecutionEngine",
    ) -> RiskCheckResult:
        dd, dd_pct = engine.get_current_drawdown()
        if dd_pct < -self.max_drawdown_pct:
            return RiskCheckResult(
                False, RiskLevel.REJECT,
                f"drawdown {dd_pct:.2%} exceeds limit {self.max_drawdown_pct:.2%}"
            )
        return RiskCheckResult(True, RiskLevel.PASS, "ok")


class MaxSingleOrderValueRule(RiskRule):
    def __init__(self, max_pct: float = 0.3):
        super().__init__("max_single_order_value")
        self.max_pct = max_pct

    def check(
        self,
        order: OrderData,
        engine: "ExecutionEngine",
    ) -> RiskCheckResult:
        portfolio_value = engine.get_portfolio_value()
        if portfolio_value <= 0:
            return RiskCheckResult(True, RiskLevel.PASS, "skip")

        size = engine.get_contract_size(order.vt_symbol)
        order_value = order.volume * order.price * size
        pct = order_value / portfolio_value

        if pct > self.max_pct:
            max_vol = int((portfolio_value * self.max_pct) / (order.price * size))
            if max_vol <= 0:
                return RiskCheckResult(
                    False, RiskLevel.REJECT,
                    f"order value {pct:.2%} exceeds {self.max_pct:.2%}"
                )
            return RiskCheckResult(
                False, RiskLevel.WARN,
                f"order value capped from {order.volume} to {max_vol}",
                adjusted_volume=float(max_vol)
            )

        return RiskCheckResult(True, RiskLevel.PASS, "ok")


class PriceReasonablenessRule(RiskRule):
    def __init__(self, max_deviation_pct: float = 0.1):
        super().__init__("price_reasonableness")
        self.max_deviation_pct = max_deviation_pct

    def check(
        self,
        order: OrderData,
        engine: "ExecutionEngine",
    ) -> RiskCheckResult:
        bar = engine.get_bar(order.vt_symbol)
        if bar is None or bar.close_price <= 0:
            return RiskCheckResult(True, RiskLevel.PASS, "no bar data")

        deviation = abs(order.price - bar.close_price) / bar.close_price
        if deviation > self.max_deviation_pct:
            return RiskCheckResult(
                False, RiskLevel.WARN,
                f"order price deviates {deviation:.2%} from last close {bar.close_price}"
            )
        return RiskCheckResult(True, RiskLevel.PASS, "ok")


class RiskControlLayer:
    def __init__(self):
        self._rules: list[RiskRule] = []
        self._enabled: bool = True
        self._rejected_count: int = 0
        self._warned_count: int = 0

    def add_rule(self, rule: RiskRule) -> "RiskControlLayer":
        self._rules.append(rule)
        return self

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False

    def check_order(
        self,
        order: OrderData,
        engine: "ExecutionEngine",
    ) -> RiskCheckResult:
        if not self._enabled:
            return RiskCheckResult(True, RiskLevel.PASS, "risk layer disabled")

        for rule in self._rules:
            if not rule.enabled:
                continue

            result = rule.check(order, engine)
            if not result.passed:
                if result.level == RiskLevel.REJECT:
                    self._rejected_count += 1
                    return result
                elif result.level == RiskLevel.WARN:
                    self._warned_count += 1
                    if result.adjusted_volume is not None:
                        order.volume = result.adjusted_volume
                    return result

        return RiskCheckResult(True, RiskLevel.PASS, "all rules passed")

    def get_stats(self) -> dict:
        return {
            "enabled": self._enabled,
            "rule_count": len(self._rules),
            "rejected_count": self._rejected_count,
            "warned_count": self._warned_count,
        }

    def clear_stats(self) -> None:
        self._rejected_count = 0
        self._warned_count = 0

    @classmethod
    def default(cls) -> "RiskControlLayer":
        layer = cls()
        layer.add_rule(MaxOrderSizeRule(max_size=10000))
        layer.add_rule(MinOrderSizeRule(min_size=1))
        layer.add_rule(MaxSingleOrderValueRule(max_pct=0.3))
        return layer
