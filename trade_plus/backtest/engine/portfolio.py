from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..data import Direction, TradeData, BarData
else:
    from ..data import Direction


@dataclass
class ContractDailyResult:
    date: date
    close_price: float = 0.0
    pre_close: float = 0.0

    trades: list["TradeData"] = field(default_factory=list)
    trade_count: int = 0

    start_pos: float = 0.0
    end_pos: float = 0.0

    turnover: float = 0.0
    commission: float = 0.0

    trading_pnl: float = 0.0
    holding_pnl: float = 0.0
    total_pnl: float = 0.0
    net_pnl: float = 0.0

    def add_trade(self, trade_or_vt_symbol, direction=None, offset=None, price=None, volume=None) -> None:
        if isinstance(trade_or_vt_symbol, str):
            from ..data import TradeData as TD
            trade = TD(
                symbol=trade_or_vt_symbol,
                direction=direction,
                offset=offset,
                price=price,
                volume=volume,
            )
        else:
            trade = trade_or_vt_symbol
        self.trades.append(trade)

    def calculate_pnl(
        self,
        pre_close: float,
        start_pos: float,
        size: float,
        long_rate: float,
        short_rate: float,
    ) -> None:
        if pre_close:
            self.pre_close = pre_close

        self.start_pos = start_pos
        self.end_pos = start_pos

        self.holding_pnl = self.start_pos * (self.close_price - self.pre_close) * size

        self.trade_count = len(self.trades)

        for trade in self.trades:
            if trade.direction == Direction.LONG:
                pos_change: float = trade.volume
                rate: float = long_rate
            else:
                pos_change = -trade.volume
                rate = short_rate

            self.end_pos += pos_change

            turnover: float = trade.volume * size * trade.price

            self.trading_pnl += pos_change * (self.close_price - trade.price) * size
            self.turnover += turnover
            self.commission += turnover * rate

        self.total_pnl = self.trading_pnl + self.holding_pnl
        self.net_pnl = self.total_pnl - self.commission

    def update_close_price(self, close_price: float) -> None:
        self.close_price = close_price


@dataclass
class PortfolioDailyResult:
    date: date
    close_prices: dict[str, float] = field(default_factory=dict)

    contract_results: dict[str, ContractDailyResult] = field(default_factory=dict)

    trade_count: int = 0
    turnover: float = 0.0
    commission: float = 0.0
    trading_pnl: float = 0.0
    holding_pnl: float = 0.0
    total_pnl: float = 0.0
    net_pnl: float = 0.0

    pre_closes: dict[str, float] = field(default_factory=dict)
    start_poses: dict[str, float] = field(default_factory=dict)
    end_poses: dict[str, float] = field(default_factory=dict)

    def __post_init__(self):
        for vt_symbol, close_price in self.close_prices.items():
            self.contract_results[vt_symbol] = ContractDailyResult(
                self.date, close_price
            )

    def add_trade(self, trade_or_vt_symbol, direction=None, offset=None, price=None, volume=None) -> None:
        if isinstance(trade_or_vt_symbol, str):
            from ..data import TradeData as TD, Exchange
            trade = TD(
                symbol=trade_or_vt_symbol.split('.')[0] if '.' in trade_or_vt_symbol else trade_or_vt_symbol,
                exchange=Exchange.SZSE if 'SZSE' in str(trade_or_vt_symbol) else Exchange.SSE if 'SSE' in str(trade_or_vt_symbol) else Exchange.Unknown,
                direction=direction,
                offset=offset,
                price=price,
                volume=volume,
            )
        else:
            trade = trade_or_vt_symbol

        vt_symbol = getattr(trade, 'vt_symbol', None)
        if vt_symbol is None:
            vt_symbol = f"{getattr(trade, 'symbol', '')}.{getattr(trade, 'exchange', '')}"

        if vt_symbol not in self.contract_results:
            self.contract_results[vt_symbol] = ContractDailyResult(self.date, 0.0)
        self.contract_results[vt_symbol].add_trade(trade)

    def calculate_pnl(
        self,
        pre_closes: dict[str, float],
        start_poses: dict[str, float],
        sizes: dict[str, float],
        long_rates: dict[str, float],
        short_rates: dict[str, float],
    ) -> None:
        self.pre_closes = pre_closes
        self.start_poses = start_poses

        for vt_symbol, contract_result in self.contract_results.items():
            contract_result.calculate_pnl(
                pre_closes.get(vt_symbol, 0),
                start_poses.get(vt_symbol, 0),
                sizes[vt_symbol],
                long_rates[vt_symbol],
                short_rates[vt_symbol],
            )

            self.trade_count += contract_result.trade_count
            self.turnover += contract_result.turnover
            self.commission += contract_result.commission
            self.trading_pnl += contract_result.trading_pnl
            self.holding_pnl += contract_result.holding_pnl
            self.total_pnl += contract_result.total_pnl
            self.net_pnl += contract_result.net_pnl

            self.end_poses[vt_symbol] = contract_result.end_pos

    def update_close_prices(self, close_prices: dict[str, float]) -> None:
        self.close_prices.update(close_prices)

        for vt_symbol, close_price in close_prices.items():
            contract_result: ContractDailyResult | None = self.contract_results.get(
                vt_symbol, None
            )
            if contract_result:
                contract_result.update_close_price(close_price)
            else:
                self.contract_results[vt_symbol] = ContractDailyResult(
                    self.date, close_price
                )


class PortfolioManager:
    def __init__(self, initial_capital: float):
        self.initial_capital: float = initial_capital
        self.cash: float = initial_capital

        self._positions: dict[str, float] = defaultdict(float)

        self.long_rates: dict[str, float] = {}
        self.short_rates: dict[str, float] = {}
        self.sizes: dict[str, float] = {}
        self.priceticks: dict[str, float] = {}

        self.daily_results: dict[date, PortfolioDailyResult] = {}

        self._pre_closes: dict[str, float] = defaultdict(float)

        self._high_water_mark: float = initial_capital
        self._high_water_date: date | None = None

        self._balance_series: list[float] = []
        self._date_series: list[date] = []

    def update_position(self, vt_symbol: str, direction: "Direction", volume: float) -> None:
        if direction == "Direction".LONG or str(direction.value) == "long":
            self._positions[vt_symbol] += volume
        else:
            self._positions[vt_symbol] -= volume

    def set_contract_config(
        self,
        vt_symbol: str,
        size: float,
        long_rate: float,
        short_rate: float,
        pricetick: float,
    ) -> None:
        self.sizes[vt_symbol] = size
        self.long_rates[vt_symbol] = long_rate
        self.short_rates[vt_symbol] = short_rate
        self.priceticks[vt_symbol] = pricetick

    def get_pos(self, vt_symbol: str) -> float:
        return self._positions[vt_symbol]

    def get_all_positions(self) -> dict[str, float]:
        return dict(self._positions)

    def get_cash_available(self) -> float:
        return self.cash

    def get_holding_value(self, bars: dict[str, "BarData"] | None = None) -> float:
        if not bars:
            return 0.0
        holding_value: float = 0.0
        for vt_symbol, pos in self._positions.items():
            if abs(pos) < 1e-9:
                continue
            bar = bars.get(vt_symbol)
            if not bar or bar.close_price <= 0:
                continue
            size = self.sizes.get(vt_symbol, 1.0)
            holding_value += bar.close_price * pos * size
        return holding_value

    def get_portfolio_value(self) -> float:
        return self.cash + self.get_holding_value()

    def update_daily_close(self, bars: dict[str, "BarData"], dt: datetime) -> None:
        d: date = dt.date()

        close_prices: dict[str, float] = {}
        for vt_symbol, bar in bars.items():
            if not bar.close_price:
                close_prices[vt_symbol] = self._pre_closes[vt_symbol]
            else:
                close_prices[vt_symbol] = bar.close_price

        daily_result: PortfolioDailyResult | None = self.daily_results.get(d, None)

        if daily_result:
            daily_result.update_close_prices(close_prices)
        else:
            self.daily_results[d] = PortfolioDailyResult(d, close_prices)

        for symbol, price in close_prices.items():
            self._pre_closes[symbol] = price

    def calculate_daily_results(self) -> None:
        pre_closes: dict[str, float] = {}
        start_poses: dict[str, float] = {}

        for daily_result in self.daily_results.values():
            daily_result.calculate_pnl(
                pre_closes,
                start_poses,
                self.sizes,
                self.long_rates,
                self.short_rates,
            )

            pre_closes = daily_result.close_prices
            start_poses = daily_result.end_poses

            self.cash += daily_result.net_pnl

    def get_current_drawdown(self) -> tuple[float, float]:
        current_value = self.get_portfolio_value()
        dd = self._high_water_mark - current_value
        dd_pct = dd / self._high_water_mark if self._high_water_mark > 0 else 0.0
        return dd, dd_pct

    def update_high_water_mark(self) -> None:
        current_value = self.get_portfolio_value()
        if current_value >= self._high_water_mark:
            self._high_water_mark = current_value

    def apply_trade(
        self,
        vt_symbol: str,
        direction: "Direction",
        offset: "Offset",
        price: float,
        volume: float,
        trade_dt: datetime | None = None,
    ) -> tuple[float, float]:
        size = self.sizes.get(vt_symbol, 1.0)
        turnover = price * volume * size

        if direction.value == "long":
            self.cash -= turnover
            self._positions[vt_symbol] += volume
            rate = self.long_rates.get(vt_symbol, 0.0)
        else:
            self.cash += turnover
            self._positions[vt_symbol] -= volume
            rate = self.short_rates.get(vt_symbol, 0.0)

        commission = turnover * rate
        self.cash -= commission

        if trade_dt is not None:
            trade_date = trade_dt.date()
            if trade_date not in self.daily_results:
                self.daily_results[trade_date] = PortfolioDailyResult(trade_date, {})
            self.daily_results[trade_date].add_trade(
                vt_symbol, direction=direction, offset=offset, price=price, volume=volume
            )

        return turnover, commission

    def record_trade(
        self,
        vt_symbol: str,
        direction: "Direction",
        offset: "Offset",
        price: float,
        volume: float,
        trade_dt: datetime,
    ) -> None:
        trade_date = trade_dt.date()
        if trade_date not in self.daily_results:
            self.daily_results[trade_date] = PortfolioDailyResult(trade_date, {})
        self.daily_results[trade_date].add_trade(
            vt_symbol, direction=direction, offset=offset, price=price, volume=volume
        )
