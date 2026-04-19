from datetime import datetime
from typing import Optional, Type

from ..data import BarData, Interval, Exchange
from .backtesting import BacktestingExecutionEngine
from .portfolio import PortfolioManager
from ..risk import RiskControlLayer
from ..strategy.template import Strategy
from ..visual import plot_full_report


class BacktestEngine:
    """
    回测引擎总控Facade。

    整合数据加载、策略初始化、回测执行、统计分析、可视化全流程。
    """

    def __init__(
        self,
        initial_capital: float = 1_000_000.0,
        risk_layer: Optional[RiskControlLayer] = None,
    ) -> None:
        self._initial_capital = initial_capital
        self._risk_layer = risk_layer or RiskControlLayer.default()

        self._vt_symbols: list[str] = []
        self._contracts: dict[str, dict] = {}
        self._interval: Interval = Interval.DAILY
        self._start: datetime | None = None
        self._end: datetime | None = None

        self._data: dict[str, list[BarData]] = {}

        self._strategy_class: Type[Strategy] | None = None
        self._strategy_setting: dict = {}

        self._execution_engine: Optional[BacktestingExecutionEngine] = None
        self._portfolio: Optional[PortfolioManager] = None
        self._statistics: dict = {}

    def set_data(
        self,
        vt_symbol: str,
        bars: list[BarData],
    ) -> "BacktestEngine":
        self._data[vt_symbol] = bars
        if vt_symbol not in self._vt_symbols:
            self._vt_symbols.append(vt_symbol)
        return self

    def set_symbols(self, vt_symbols: list[str]) -> "BacktestEngine":
        self._vt_symbols = vt_symbols
        return self

    def set_interval(self, interval: Interval) -> "BacktestEngine":
        self._interval = interval
        return self

    def set_period(self, start: datetime, end: datetime) -> "BacktestEngine":
        self._start = start
        self._end = end
        return self

    def set_contract(
        self,
        vt_symbol: str,
        size: float = 1.0,
        long_rate: float = 0.0,
        short_rate: float = 0.0,
        pricetick: float = 0.01,
    ) -> "BacktestEngine":
        self._contracts[vt_symbol] = {
            "size": size,
            "long_rate": long_rate,
            "short_rate": short_rate,
            "pricetick": pricetick,
        }
        return self

    def add_contract(
        self,
        vt_symbol: str,
        size: float = 1.0,
        long_rate: float = 0.0,
        short_rate: float = 0.0,
        pricetick: float = 0.01,
    ) -> "BacktestEngine":
        return self.set_contract(vt_symbol, size, long_rate, short_rate, pricetick)

    def use_strategy(
        self,
        strategy_class: Type[Strategy],
        setting: Optional[dict] = None,
    ) -> "BacktestEngine":
        self._strategy_class = strategy_class
        self._strategy_setting = setting or {}
        return self

    def use_risk_layer(self, layer: RiskControlLayer) -> "BacktestEngine":
        self._risk_layer = layer
        return self

    def load_bar_data(
        self,
        vt_symbol: str,
        interval: Interval,
        start: datetime,
        end: datetime,
    ) -> list[BarData]:
        return self._data.get(vt_symbol, [])

    def run(self) -> dict:
        if self._strategy_class is None:
            raise RuntimeError("Strategy not set, call use_strategy() first")
        if not self._data:
            raise RuntimeError("Data not set, call set_data() first")

        self._portfolio = PortfolioManager(self._initial_capital)

        for vt_symbol in self._vt_symbols:
            if vt_symbol not in self._contracts:
                self._contracts[vt_symbol] = {
                    "size": 1.0,
                    "long_rate": 0.0,
                    "short_rate": 0.0,
                    "pricetick": 0.01,
                }

        self._execution_engine = BacktestingExecutionEngine(
            portfolio=self._portfolio,
            contracts=self._contracts,
            risk_layer=self._risk_layer,
        )
        self._execution_engine.set_symbols(self._vt_symbols)
        self._execution_engine.set_interval(self._interval)

        strategy = self._strategy_class(
            self._execution_engine,
            self._strategy_class.__name__,
            self._vt_symbols,
            self._strategy_setting,
        )
        self._execution_engine.set_strategy(strategy)

        self._execution_engine.load_data(
            self._data,
            self._start or datetime.min,
            self._end or datetime.max,
        )

        self._execution_engine.run()

        self._statistics = self._execution_engine.calculate_statistics()

        return self._statistics

    def get_stats(self) -> dict:
        return self._statistics

    def print_stats(self) -> None:
        self._execution_engine.print_statistics(self._statistics)

    def get_trades(self) -> list:
        if self._execution_engine is None:
            return []
        return self._execution_engine.get_all_trades()

    def get_orders(self) -> list:
        if self._execution_engine is None:
            return []
        return self._execution_engine.get_all_orders()

    def get_logs(self) -> list[str]:
        if self._execution_engine is None:
            return []
        return self._execution_engine.get_logs()

    def get_risk_stats(self) -> dict:
        if self._risk_layer is None:
            return {}
        return self._risk_layer.get_stats()

    def plot(self, output_path: Optional[str] = None) -> None:
        if not self._statistics or "daily_df" not in self._statistics:
            print("No data to plot, run backtest first")
            return

        df = self._statistics["daily_df"]
        plot_full_report(
            dates=df["dates"],
            balance=df["balance"],
            drawdown=df["drawdown"],
            net_pnl=df["net_pnl"],
            title=f"{self._strategy_class.__name__ if self._strategy_class else 'Strategy'} Backtest",
            output_path=output_path,
        )
