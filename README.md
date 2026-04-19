# trade_plus

参考 VeighNa (vnpy) 架构设计的**新一代量化交易回测框架**。

## 核心设计改进

相比 vnpy.alpha，本框架做了以下关键改进：

### 1. 策略与回测引擎解耦 ✅

vnpy.alpha 中策略直接持有 `BacktestingEngine` 引用，本框架引入 `ExecutionEngine` 接口抽象：

```
Strategy <---> ExecutionEngine <---> BacktestingExecutionEngine
                         <---> LiveExecutionEngine (未来扩展)
```

策略只依赖接口，不直接依赖具体实现，可独立进行单元测试。

### 2. 内置风控层 ✅

vnpy.alpha 的下单路径**没有任何风控检查**，本框架内置 `RiskControlLayer`：

| 风控规则 | 说明 |
|----------|------|
| `MaxPositionPerSymbolRule` | 单标的仓位上限 |
| `MaxTotalPositionRule` | 总仓位上限 |
| `MaxSingleOrderValueRule` | 单笔订单价值上限 |
| `MaxOrderSizeRule` | 单笔订单数量上限 |
| `MinOrderSizeRule` | 单笔订单数量下限 |
| `MaxDrawdownRule` | 回撤上限（事前阻断） |
| `PriceReasonablenessRule` | 价格合理性检查 |

### 3. 两套持仓系统 + 自动调仓

与 vnpy.alpha 一致，支持 `pos_data`（实际持仓）和 `target_data`（目标持仓）分离，策略只需设置目标持仓，`execute_trading()` 自动完成平仓/开仓。

## 目录结构

```
trade_plus/
├── trade_plus/
│   └── backtest/
│       ├── data/           # 数据模型（BarData/OrderData/TradeData等）
│       ├── engine/         # 回测引擎
│       │   ├── execution.py   # ExecutionEngine 接口
│       │   ├── backtesting.py # 回测执行引擎
│       │   ├── portfolio.py   # 组合管理（持仓/资金/日结算）
│       │   └── facade.py      # BacktestEngine 总控Facade
│       ├── risk/           # 风控层
│       │   └── layer.py     # RiskControlLayer + 各种风控规则
│       ├── strategy/       # 策略模板
│       │   └── template.py  # Strategy 基类
│       ├── strategies/     # 示例策略
│       │   └── demo.py      # 双均线 / 均值回归
│       ├── analytics/       # 统计分析
│       │   └── metrics.py  # Sharpe/Sortino/Calmar等
│       └── visual/         # 可视化
│           └── charts.py   # Plotly图表
└── run_example.py          # 使用示例
```

## 快速开始

```python
from datetime import datetime
from trade_plus.backtest import (
    BacktestEngine, BarData, Interval, Exchange,
    RiskControlLayer,
)
from trade_plus.backtest.strategies import DualMovingAverageStrategy

# 1. 创建引擎
engine = (
    BacktestEngine(initial_capital=1_000_000.0)
    .set_symbols(["000001.SZSE"])
    .set_period(datetime(2024, 1, 1), datetime(2024, 12, 31))
    .add_contract("000001.SZSE", size=100, long_rate=0.0003, short_rate=0.0003)
    .set_data("000001.SZSE", your_bar_data_list)   # 注入K线数据
)

# 2. 配置风控
engine.use_risk_layer(RiskControlLayer.default())

# 3. 加载策略
engine.use_strategy(DualMovingAverageStrategy, {"fast_window": 5, "slow_window": 20})

# 4. 运行
stats = engine.run()
engine.print_stats(stats)

# 5. 绘图
engine.plot()
```

## 数据格式

### BarData

```python
BarData(
    symbol="000001",
    exchange=Exchange.SZSE,
    datetime=datetime(2024, 1, 1),
    interval=Interval.DAILY,
    open_price=100.0,
    high_price=101.0,
    low_price=99.0,
    close_price=100.5,
    volume=10000.0,
)
```

### 策略模板

```python
from trade_plus.backtest import Strategy, BacktestEngine
from trade_plus.backtest.data import BarData, TradeData, Direction

class MyStrategy(Strategy):
    strategy_name = "MyStrategy"

    def on_init(self):
        self.write_log("初始化")

    def on_bars(self, bars):
        for symbol, bar in bars.items():
            if self.get_pos(symbol) == 0:
                self.buy(symbol, bar.close_price, 1.0)
            else:
                self.sell(symbol, bar.close_price, self.get_pos(symbol))

    def on_trade(self, trade):
        self.write_log(f"成交: {trade.vt_symbol} {trade.direction} {trade.volume}")
```

## 安装

```bash
pip install -e .
```

可选依赖：
```bash
pip install plotly  # 用于图表可视化
```
