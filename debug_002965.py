# -*- coding: utf-8 -*-
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from datetime import datetime
from trade_plus.backtest.utils import TdxDataLoader

loader = TdxDataLoader(vipdoc_path=r"D:\new_tdx\vipdoc")

# 检查所有买入日期的原始数据
check_dates = ["2025-01-14", "2025-01-27", "2025-03-04", "2025-03-13", "2025-03-14", "2025-03-21", "2025-04-23", "2025-05-20", "2025-09-16", "2025-09-30"]

bars = loader.load_daily_bars(
    code="002965",
    market="sz",
    start_date=datetime(2025, 1, 1),
    end_date=datetime(2025, 12, 31)
)

print("002965 交易日期对应的K线数据:")
print(f"{'日期':<12} {'开盘':>8} {'最高':>8} {'最低':>8} {'收盘':>8}")
print("-" * 50)

bar_dict = {bar.datetime.date(): bar for bar in bars}

for date_str in check_dates:
    dt = datetime.strptime(date_str, "%Y-%m-%d").date()
    if dt in bar_dict:
        bar = bar_dict[dt]
        print(f"{date_str}  {bar.open_price:8.2f} {bar.high_price:8.2f} {bar.low_price:8.2f} {bar.close_price:8.2f}")
    else:
        print(f"{date_str}  - 数据不存在")