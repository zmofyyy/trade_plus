"""
通达信本地数据读取器

使用 pytdx.reader 从本地通达信安装目录读取K线数据，
转换为 trade_plus 所需的 BarData 格式。
"""

from datetime import datetime
from typing import Optional

import pandas as pd
from pytdx.reader import TdxDailyBarReader

from ..data import BarData, Exchange, Interval


class TdxDataLoader:
    """
    通达信本地数据加载器。

    从通达信安装目录的 vipdoc 文件夹读取K线数据，
    转换为 BarData 列表供回测使用。

    Usage:
        loader = TdxDataLoader(vipdoc_path='D:\\new_tdx\\vipdoc')
        bars = loader.load_daily_bars('000001', 'sz', start_date, end_date)
    """

    MARKET_MAP = {
        'sz': 0,
        'sh': 1,
    }

    EXCHANGE_MAP = {
        'sz': Exchange.SZSE,
        'sh': Exchange.SSE,
    }

    def __init__(self, vipdoc_path: str) -> None:
        import os
        nul_fd = os.open('NUL', os.O_WRONLY)
        old_stderr_fd = os.dup(2)
        os.dup2(nul_fd, 2)
        os.close(nul_fd)
        try:
            self._reader = TdxDailyBarReader(vipdoc_path=vipdoc_path)
        finally:
            os.dup2(old_stderr_fd, 2)
            os.close(old_stderr_fd)

    def load_daily_bars(
        self,
        code: str,
        market: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> list[BarData]:
        """
        加载日K线数据（复权数据）。

        Args:
            code: 股票代码，如 '000001'
            market: 市场标识，'sz' 或 'sh'
            start_date: 起始日期（可选）
            end_date: 结束日期（可选）

        Returns:
            BarData 列表（复权数据）
        """
        import os

        nul_fd = os.open('NUL', os.O_WRONLY)
        old_stderr_fd = os.dup(2)
        os.dup2(nul_fd, 2)
        os.close(nul_fd)

        try:
            df = self._reader.get_df(f"{self._reader.vipdoc_path}\\{market}\\lday\\{market}{code}.day")
        except Exception:
            df = None
        finally:
            os.dup2(old_stderr_fd, 2)
            os.close(old_stderr_fd)

        if df is None or df.empty:
            return []

        if start_date is not None:
            df = df[df.index >= pd.Timestamp(start_date)]
        if end_date is not None:
            df = df[df.index <= pd.Timestamp(end_date)]

        bars = []
        exchange = self.EXCHANGE_MAP.get(market, Exchange.Unknown)

        for dt, row in df.iterrows():
            bar = BarData(
                symbol=code,
                exchange=exchange,
                datetime=dt.to_pydatetime(),
                interval=Interval.DAILY,
                open_price=float(row['open']),
                high_price=float(row['high']),
                low_price=float(row['low']),
                close_price=float(row['close']),
                volume=float(row['volume']),
                turnover=float(row['amount']),
                gateway_name='TDX',
            )
            bars.append(bar)

        return bars

    def get_security_list(self, market: str) -> pd.DataFrame:
        """
        获取合约列表信息。

        Args:
            market: 'sz' 或 'sh'

        Returns:
            合约信息 DataFrame
        """
        vipdoc_path = self._reader.vipdoc_path
        reader = TdxDailyBarReader(vipdoc_path=vipdoc_path)

        if market == 'sz':
            list_file = f"{vipdoc_path}/sz/sz000001.day"
        else:
            list_file = f"{vipdoc_path}/sh/sh000001.day"

        return reader.get_df_by_file(list_file)

    def load_index_bars(
        self,
        code: str,
        market: str = 'sz',
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> list[BarData]:
        """
        加载指数K线数据。

        Args:
            code: 指数代码，如 '000001' (上证指数), '399001' (深证成指)
            market: 'sz' 或 'sh'
            start_date: 起始日期（可选）
            end_date: 结束日期（可选）

        Returns:
            BarData 列表
        """
        df = self._reader.get_df_by_code(code, market)

        if start_date is not None:
            df = df[df.index >= pd.Timestamp(start_date)]
        if end_date is not None:
            df = df[df.index <= pd.Timestamp(end_date)]

        bars = []
        exchange = self.EXCHANGE_MAP.get(market, Exchange.Unknown)

        for dt, row in df.iterrows():
            bar = BarData(
                symbol=code,
                exchange=exchange,
                datetime=dt.to_pydatetime(),
                interval=Interval.DAILY,
                open_price=float(row['open']),
                high_price=float(row['high']),
                low_price=float(row['low']),
                close_price=float(row['close']),
                volume=float(row['volume']),
                turnover=float(row['amount']),
                gateway_name='TDX_INDEX',
            )
            bars.append(bar)

        return bars
