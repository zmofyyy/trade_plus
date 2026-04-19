from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import TYPE_CHECKING, Optional
import traceback

if TYPE_CHECKING:
    from ..data import (
        BarData, OrderData, TradeData, Direction, Offset,
        Status, Interval,
    )
    from ..strategy.template import Strategy
    from ..risk import RiskControlLayer
    from .portfolio import PortfolioManager

from ..data import Direction, Offset, Status, Interval, BarData, OrderData, TradeData
from ..utils import round_to, extract_vt_symbol
from .execution import ExecutionEngine
from .portfolio import PortfolioManager, PortfolioDailyResult


class BacktestingExecutionEngine(ExecutionEngine):
    gateway_name: str = "BACKTESTING"

    def __init__(
        self,
        portfolio: PortfolioManager,
        contracts: dict[str, dict],
        risk_layer: Optional["RiskControlLayer"] = None,
    ) -> None:
        self._portfolio = portfolio
        self._contracts = contracts
        self._risk_layer = risk_layer

        self._vt_symbols: list[str] = []
        self._interval: Interval = Interval.MINUTE

        self._bars: dict[str, BarData] = {}
        self._datetime: datetime | None = None

        self._limit_order_count: int = 0
        self._limit_orders: dict[str, OrderData] = {}
        self._active_limit_orders: dict[str, OrderData] = {}

        self._trade_count: int = 0
        self._trades: dict[str, TradeData] = {}

        self._strategy: "Strategy | None" = None

        self._history_data: dict[tuple, BarData] = {}
        self._dts: set[datetime] = set()

        self._pre_closes: defaultdict = defaultdict(float)

        self._logs: list[str] = []

        self._signals: dict[datetime, dict] = {}

    def set_symbols(self, vt_symbols: list[str]) -> None:
        self._vt_symbols = vt_symbols
        for symbol in vt_symbols:
            cfg = self._contracts.get(symbol, {})
            self._portfolio.set_contract_config(
                symbol,
                size=cfg.get("size", 1.0),
                long_rate=cfg.get("long_rate", 0.0),
                short_rate=cfg.get("short_rate", 0.0),
                pricetick=cfg.get("pricetick", 0.01),
            )

    def set_interval(self, interval: Interval) -> None:
        self._interval = interval

    def set_strategy(self, strategy: "Strategy") -> None:
        self._strategy = strategy

    def set_signals(self, signals: dict[datetime, dict]) -> None:
        self._signals = signals

    def load_data(
        self,
        data: dict[str, list[BarData]],
        start: datetime,
        end: datetime,
    ) -> None:
        self._history_data.clear()
        self._dts.clear()

        empty_symbols: list[str] = []

        for vt_symbol, bars in data.items():
            for bar in bars:
                if start <= bar.datetime <= end:
                    self._dts.add(bar.datetime)
                    self._history_data[(bar.datetime, vt_symbol)] = bar

            if not any(
                start <= b.datetime <= end for b in bars
            ):
                empty_symbols.append(vt_symbol)

        if empty_symbols:
            self._logs.append(f"警告：以下合约历史数据为空：{empty_symbols}")

    def run(self) -> None:
        if self._strategy is None:
            raise RuntimeError("Strategy not set, call set_strategy first")

        self._strategy.on_init()

        dts: list = sorted(self._dts)

        for dt in dts:
            self._datetime = dt
            try:
                self._new_bars(dt)
            except Exception:
                self._logs.append("回测触发异常，已终止")
                self._logs.append(traceback.format_exc())
                return

    def _new_bars(self, dt: datetime) -> None:
        bars: dict[str, BarData] = {}

        for vt_symbol in self._vt_symbols:
            last_bar = self._bars.get(vt_symbol, None)
            if last_bar and last_bar.close_price:
                self._pre_closes[vt_symbol] = last_bar.close_price

            bar: BarData | None = self._history_data.get((dt, vt_symbol), None)

            if bar:
                self._bars[vt_symbol] = bar
                bars[vt_symbol] = bar
            elif vt_symbol in self._bars:
                old_bar: BarData = self._bars[vt_symbol]

                fill_bar = BarData(
                    symbol=old_bar.symbol,
                    exchange=old_bar.exchange,
                    datetime=dt,
                    open_price=old_bar.close_price,
                    high_price=old_bar.close_price,
                    low_price=old_bar.close_price,
                    close_price=old_bar.close_price,
                    gateway_name=old_bar.gateway_name,
                )
                self._bars[vt_symbol] = fill_bar

        self._cross_order()
        self._strategy.on_bars(bars)
        self._portfolio.update_daily_close(self._bars, dt)

    def _cross_order(self) -> None:
        for order in list(self._active_limit_orders.values()):
            bar: BarData = self._bars.get(order.vt_symbol)
            if not bar:
                continue

            long_cross_price: float = bar.low_price
            short_cross_price: float = bar.high_price
            long_best_price: float = bar.open_price
            short_best_price: float = bar.open_price

            if order.status == Status.SUBMITTING:
                order.status = Status.NOTTRADED
                self._strategy.update_order(order)

            pricetick: float = self._portfolio.priceticks.get(order.vt_symbol, 0.01)
            pre_close: float = self._pre_closes.get(order.vt_symbol, 0)

            limit_up: float = round_to(pre_close * 1.1, pricetick)
            limit_down: float = round_to(pre_close * 0.9, pricetick)

            long_cross: bool = (
                order.direction == Direction.LONG
                and order.price >= long_cross_price
                and long_cross_price > 0
                and bar.low_price < limit_up
            )

            short_cross: bool = (
                order.direction == Direction.SHORT
                and order.price <= short_cross_price
                and short_cross_price > 0
                and bar.high_price > limit_down
            )

            if not long_cross and not short_cross:
                continue

            order.traded = order.volume
            order.status = Status.ALLTRADED
            self._strategy.update_order(order)

            if order.vt_orderid in self._active_limit_orders:
                self._active_limit_orders.pop(order.vt_orderid)

            self._trade_count += 1

            if long_cross:
                trade_price = min(order.price, long_best_price)
            else:
                trade_price = max(order.price, short_best_price)

            trade: TradeData = TradeData(
                symbol=order.symbol,
                exchange=order.exchange,
                orderid=order.orderid,
                tradeid=str(self._trade_count),
                direction=order.direction,
                offset=order.offset,
                price=trade_price,
                volume=order.volume,
                datetime=self._datetime,
                gateway_name=self.gateway_name,
            )

            self._apply_trade(trade)
            self._strategy.update_trade(trade)
            self._trades[trade.vt_tradeid] = trade

    def _apply_trade(self, trade: TradeData) -> None:
        turnover, commission = self._portfolio.apply_trade(
            trade.vt_symbol,
            trade.direction,
            trade.offset,
            trade.price,
            trade.volume,
        )

    def get_signal(self) -> dict:
        if self._datetime is None:
            return {}
        return self._signals.get(self._datetime, {})

    def send_order(
        self,
        strategy: "Strategy",
        vt_symbol: str,
        direction: Direction,
        offset: Offset,
        price: float,
        volume: float,
    ) -> list[str]:
        pricetick = self._portfolio.priceticks.get(vt_symbol, 0.01)
        price = round_to(price, pricetick)
        symbol, exchange = extract_vt_symbol(vt_symbol)

        self._limit_order_count += 1

        order: OrderData = OrderData(
            symbol=symbol,
            exchange=exchange,
            orderid=str(self._limit_order_count),
            direction=direction,
            offset=offset,
            price=price,
            volume=volume,
            status=Status.SUBMITTING,
            datetime=self._datetime,
            gateway_name=self.gateway_name,
        )

        if self._risk_layer:
            result = self._risk_layer.check_order(order, self)
            if not result.passed and result.adjusted_volume is None:
                order.status = Status.REJECTED
                return []

        self._active_limit_orders[order.vt_orderid] = order
        self._limit_orders[order.vt_orderid] = order

        return [order.vt_orderid]

    def cancel_order(self, strategy: "Strategy", vt_orderid: str) -> None:
        if vt_orderid not in self._active_limit_orders:
            return
        order: OrderData = self._active_limit_orders.pop(vt_orderid)
        order.status = Status.CANCELLED
        self._strategy.update_order(order)

    def get_pos(self, vt_symbol: str) -> float:
        return self._portfolio.get_pos(vt_symbol)

    def get_cash_available(self) -> float:
        return self._portfolio.get_cash_available()

    def get_holding_value(self) -> float:
        return self._portfolio.get_holding_value()

    def get_portfolio_value(self) -> float:
        return self._portfolio.get_portfolio_value()

    def get_bar(self, vt_symbol: str) -> BarData | None:
        return self._bars.get(vt_symbol, None)

    def get_contract_size(self, vt_symbol: str) -> float:
        return self._portfolio.sizes.get(vt_symbol, 1.0)

    def get_pricetick(self, vt_symbol: str) -> float:
        return self._portfolio.priceticks.get(vt_symbol, 0.01)

    def get_current_drawdown(self) -> tuple[float, float]:
        return self._portfolio.get_current_drawdown()

    def write_log(self, msg: str, strategy: "Strategy | None" = None) -> None:
        ts = self._datetime.strftime("%Y-%m-%d %H:%M:%S") if self._datetime else "N/A"
        self._logs.append(f"[{ts}] {msg}")

    def get_datetime(self) -> datetime | None:
        return self._datetime

    def get_all_trades(self) -> list[TradeData]:
        return list(self._trades.values())

    def get_all_orders(self) -> list[OrderData]:
        return list(self._limit_orders.values())

    def get_logs(self) -> list[str]:
        return self._logs

    def get_daily_results(self) -> dict[date, PortfolioDailyResult]:
        return self._portfolio.daily_results

    def calculate_statistics(self) -> dict:
        self._portfolio.calculate_daily_results()

        daily_pnl_list: list[float] = []
        daily_dates: list[date] = []

        for d, result in sorted(self._portfolio.daily_results.items()):
            daily_pnl_list.append(result.net_pnl)
            daily_dates.append(d)

        if not daily_pnl_list:
            return {}

        import numpy as np

        cumulative = np.cumsum([0.0] + daily_pnl_list)
        balance = self._portfolio.initial_capital + cumulative

        highlevel = np.maximum.accumulate(balance)
        drawdown = balance - highlevel
        dd_pct = drawdown / highlevel * 100

        total_pnl = sum(daily_pnl_list)
        total_days = len(daily_pnl_list)
        end_balance = balance[-1]
        total_return = (end_balance / self._portfolio.initial_capital - 1) * 100
        annual_return = total_return / total_days * 240 if total_days > 0 else 0

        daily_returns = np.diff(balance) / balance[:-1] * 100
        daily_return = float(np.mean(daily_returns)) if len(daily_returns) > 0 else 0
        return_std = float(np.std(daily_returns)) if len(daily_returns) > 0 else 0

        sharpe = 0.0
        if return_std > 0:
            sharpe = (daily_return - 0.0) / return_std * np.sqrt(240)

        max_dd = float(np.min(drawdown))
        max_dd_pct = float(np.min(dd_pct))
        max_dd_idx = int(np.argmin(drawdown))
        max_dd_date = daily_dates[max_dd_idx] if max_dd_idx < len(daily_dates) else None

        profit_days = sum(1 for p in daily_pnl_list if p > 0)
        loss_days = sum(1 for p in daily_pnl_list if p < 0)

        return {
            "start_date": str(daily_dates[0]) if daily_dates else "",
            "end_date": str(daily_dates[-1]) if daily_dates else "",
            "total_days": total_days,
            "profit_days": profit_days,
            "loss_days": loss_days,
            "capital": self._portfolio.initial_capital,
            "end_balance": end_balance,
            "max_drawdown": max_dd,
            "max_ddpercent": max_dd_pct,
            "max_drawdown_date": str(max_dd_date) if max_dd_date else "",
            "total_pnl": total_pnl,
            "total_return": total_return,
            "annual_return": annual_return,
            "daily_return": daily_return,
            "return_std": return_std,
            "sharpe_ratio": sharpe,
            "daily_df": {
                "dates": [str(d) for d in daily_dates],
                "balance": balance.tolist(),
                "drawdown": drawdown.tolist(),
                "net_pnl": daily_pnl_list,
            },
        }

    def print_statistics(self, stats: dict) -> None:
        print("=" * 50)
        print(f"{'首个交易日':<12}：{stats.get('start_date', '')}")
        print(f"{'最后交易日':<12}：{stats.get('end_date', '')}")
        print(f"{'总交易日':<12}：{stats.get('total_days', 0)}")
        print(f"{'盈利交易日':<12}：{stats.get('profit_days', 0)}")
        print(f"{'亏损交易日':<12}：{stats.get('loss_days', 0)}")
        print(f"{'起始资金':<12}：{stats.get('capital', 0):,.2f}")
        print(f"{'结束资金':<12}：{stats.get('end_balance', 0):,.2f}")
        print(f"{'总收益率':<12}：{stats.get('total_return', 0):.2f}%")
        print(f"{'年化收益':<12}：{stats.get('annual_return', 0):.2f}%")
        print(f"{'最大回撤':<12}：{stats.get('max_drawdown', 0):,.2f}")
        print(f"{'百分比最大回撤':<8}：{stats.get('max_ddpercent', 0):.2f}%")
        print(f"{'Sharpe比率':<12}：{stats.get('sharpe_ratio', 0):.2f}")
        print("=" * 50)
