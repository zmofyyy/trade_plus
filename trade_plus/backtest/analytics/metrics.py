from typing import Optional
import numpy as np


def calculate_sharpe(daily_returns: np.ndarray, risk_free: float = 0.0) -> float:
    if daily_returns.size == 0 or daily_returns.std() == 0:
        return 0.0
    return (daily_returns.mean() - risk_free) / daily_returns.std() * np.sqrt(240)


def calculate_sortino(
    daily_returns: np.ndarray, risk_free: float = 0.0
) -> float:
    downside_returns = daily_returns[daily_returns < 0]
    if downside_returns.size == 0:
        return float("inf")
    downside_std = np.sqrt(np.mean(downside_returns**2))
    if downside_std == 0:
        return 0.0
    return (daily_returns.mean() - risk_free) / downside_std * np.sqrt(240)


def calculate_calmar(
    total_return: float, max_drawdown: float
) -> float:
    if max_drawdown == 0:
        return 0.0
    return total_return / abs(max_drawdown)


def calculate_win_rate(pnl_list: np.ndarray) -> float:
    if pnl_list.size == 0:
        return 0.0
    return (pnl_list > 0).sum() / pnl_list.size


def calculate_profit_loss_ratio(pnl_list: np.ndarray) -> float:
    profits = pnl_list[pnl_list > 0]
    losses = pnl_list[pnl_list < 0]
    if losses.size == 0 or profits.size == 0:
        return 0.0
    return abs(profits.mean() / losses.mean())


def calculate_max_consecutive_wins(pnl_list: np.ndarray) -> int:
    if pnl_list.size == 0:
        return 0
    consecutive = 0
    max_consecutive = 0
    for pnl in pnl_list:
        if pnl > 0:
            consecutive += 1
            max_consecutive = max(max_consecutive, consecutive)
        else:
            consecutive = 0
    return max_consecutive


def calculate_max_consecutive_losses(pnl_list: np.ndarray) -> int:
    if pnl_list.size == 0:
        return 0
    consecutive = 0
    max_consecutive = 0
    for pnl in pnl_list:
        if pnl < 0:
            consecutive += 1
            max_consecutive = max(max_consecutive, consecutive)
        else:
            consecutive = 0
    return max_consecutive


def calculate_rolling_max_drawdown(balance: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    highwater = np.maximum.accumulate(balance)
    drawdown = balance - highwater
    return drawdown, drawdown / highwater * 100


def calculate_rolling_sharpe(
    daily_returns: np.ndarray, window: int = 60
) -> np.ndarray:
    if daily_returns.size < window:
        return np.array([])

    sharpes = np.zeros(daily_returns.size - window + 1)
    for i in range(window, daily_returns.size + 1):
        window_returns = daily_returns[i - window : i]
        if window_returns.std() > 0:
            sharpes[i - window] = (
                window_returns.mean() / window_returns.std() * np.sqrt(240)
            )
    return sharpes
