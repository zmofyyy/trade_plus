from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class Direction(Enum):
    LONG = "long"
    SHORT = "short"
    NET = "net"


class Offset(Enum):
    NONE = "none"
    OPEN = "open"
    CLOSE = "close"
    CLOSETODAY = "close_today"
    CLOSEYESTERDAY = "close_yesterday"


class OrderType(Enum):
    LIMIT = "limit"
    MARKET = "market"
    STOP = "stop"
    FAK = "fak"
    FOK = "fok"


class Status(Enum):
    SUBMITTING = "submitting"
    NOTTRADED = "not_traded"
    PARTTRADED = "part_traded"
    ALLTRADED = "all_traded"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class Interval(Enum):
    TICK = "tick"
    MINUTE = "minute"
    HOUR = "hour"
    DAILY = "daily"
    WEEKLY = "weekly"


class Exchange(Enum):
    SSE = "SSE"      # Shanghai Stock Exchange
    SZSE = "SZSE"    # Shenzhen Stock Exchange
    SHFE = "SHFE"    # Shanghai Futures Exchange
    DCE = "DCE"      # Dalian Commodities Exchange
    CZCE = "CZCE"    # Zhengzhou Commodities Exchange
    CFFEX = "CFFEX"  # China Financial Futures Exchange
    INE = "INE"      # Shanghai International Energy Exchange
    GFEX = "GFEX"   # Guangzhou Futures Exchange
    Unknown = "UNKNOWN"


@dataclass
class BaseData:
    gateway_name: str = "UNKNOWN"


@dataclass
class BarData(BaseData):
    symbol: str = ""
    exchange: Exchange = Exchange.Unknown
    datetime: datetime = None
    interval: Interval = Interval.MINUTE

    open_price: float = 0.0
    high_price: float = 0.0
    low_price: float = 0.0
    close_price: float = 0.0
    volume: float = 0.0
    turnover: float = 0.0
    open_interest: float = 0.0

    @property
    def vt_symbol(self) -> str:
        return f"{self.symbol}.{self.exchange.value}"

    def __post_init__(self):
        if isinstance(self.exchange, str):
            self.exchange = Exchange(self.exchange)


@dataclass
class TickData(BaseData):
    symbol: str = ""
    exchange: Exchange = Exchange.Unknown
    datetime: datetime = None

    last_price: float = 0.0
    last_volume: float = 0.0
    open_price: float = 0.0
    high_price: float = 0.0
    low_price: float = 0.0
    open_interest: float = 0.0
    volume: float = 0.0
    turnover: float = 0.0

    bid_price_1: float = 0.0
    bid_price_2: float = 0.0
    bid_price_3: float = 0.0
    bid_price_4: float = 0.0
    bid_price_5: float = 0.0

    ask_price_1: float = 0.0
    ask_price_2: float = 0.0
    ask_price_3: float = 0.0
    ask_price_4: float = 0.0
    ask_price_5: float = 0.0

    bid_volume_1: float = 0.0
    bid_volume_2: float = 0.0
    bid_volume_3: float = 0.0
    bid_volume_4: float = 0.0
    bid_volume_5: float = 0.0

    ask_volume_1: float = 0.0
    ask_volume_2: float = 0.0
    ask_volume_3: float = 0.0
    ask_volume_4: float = 0.0
    ask_volume_5: float = 0.0

    @property
    def vt_symbol(self) -> str:
        return f"{self.symbol}.{self.exchange.value}"

    def __post_init__(self):
        if isinstance(self.exchange, str):
            self.exchange = Exchange(self.exchange)


@dataclass
class OrderData(BaseData):
    symbol: str = ""
    exchange: Exchange = Exchange.Unknown
    orderid: str = ""
    direction: Direction = Direction.LONG
    offset: Offset = Offset.NONE
    type: OrderType = OrderType.LIMIT
    price: float = 0.0
    volume: float = 0.0
    traded: float = 0.0
    status: Status = Status.SUBMITTING
    datetime: datetime = None

    @property
    def vt_symbol(self) -> str:
        return f"{self.symbol}.{self.exchange.value}"

    @property
    def vt_orderid(self) -> str:
        return f"{self.gateway_name}.{self.orderid}"

    @property
    def is_active(self) -> bool:
        return self.status in {Status.SUBMITTING, Status.NOTTRADED, Status.PARTTRADED}

    def __post_init__(self):
        if isinstance(self.exchange, str):
            self.exchange = Exchange(self.exchange)
        if isinstance(self.direction, str):
            self.direction = Direction(self.direction)
        if isinstance(self.offset, str):
            self.offset = Offset(self.offset)
        if isinstance(self.type, str):
            self.type = OrderType(self.type)
        if isinstance(self.status, str):
            self.status = Status(self.status)


@dataclass
class TradeData(BaseData):
    symbol: str = ""
    exchange: Exchange = Exchange.Unknown
    orderid: str = ""
    tradeid: str = ""
    direction: Direction = Direction.LONG
    offset: Offset = Offset.NONE
    price: float = 0.0
    volume: float = 0.0
    datetime: datetime = None

    @property
    def vt_symbol(self) -> str:
        return f"{self.symbol}.{self.exchange.value}"

    @property
    def vt_orderid(self) -> str:
        return f"{self.gateway_name}.{self.orderid}"

    @property
    def vt_tradeid(self) -> str:
        return f"{self.gateway_name}.{self.tradeid}"

    def __post_init__(self):
        if isinstance(self.exchange, str):
            self.exchange = Exchange(self.exchange)
        if isinstance(self.direction, str):
            self.direction = Direction(self.direction)
        if isinstance(self.offset, str):
            self.offset = Offset(self.offset)


@dataclass
class PositionData(BaseData):
    symbol: str = ""
    exchange: Exchange = Exchange.Unknown

    long_pos: float = 0.0
    long_yd: float = 0.0
    long_td: float = 0.0
    short_pos: float = 0.0
    short_yd: float = 0.0
    short_td: float = 0.0

    @property
    def vt_symbol(self) -> str:
        return f"{self.symbol}.{self.exchange.value}"

    def __post_init__(self):
        if isinstance(self.exchange, str):
            self.exchange = Exchange(self.exchange)


@dataclass
class AccountData(BaseData):
    accountid: str = ""
    balance: float = 0.0
    frozen: float = 0.0

    @property
    def available(self) -> float:
        return self.balance - self.frozen


@dataclass
class ContractData(BaseData):
    symbol: str = ""
    exchange: Exchange = Exchange.Unknown
    name: str = ""
    size: float = 1.0
    pricetick: float = 0.0
    long_margin_ratio: float = 0.0
    short_margin_ratio: float = 0.0

    @property
    def vt_symbol(self) -> str:
        return f"{self.symbol}.{self.exchange.value}"

    def __post_init__(self):
        if isinstance(self.exchange, str):
            self.exchange = Exchange(self.exchange)


@dataclass
class LogData(BaseData):
    datetime: datetime = None
    msg: str = ""
    level: str = "INFO"
