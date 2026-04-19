from typing import Optional
import numpy as np

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False


def plot_balance_curve(
    dates: list[str],
    balance: list[float],
    title: str = "Balance Curve",
    output_path: Optional[str] = None,
) -> None:
    if not PLOTLY_AVAILABLE:
        print("Plotly not available, skipping chart generation")
        return

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(x=dates, y=balance, mode="lines", name="Balance")
    )
    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title="Balance",
        template="plotly_white",
    )

    if output_path:
        fig.write_html(output_path)
    else:
        fig.show()


def plot_drawdown(
    dates: list[str],
    drawdown: list[float],
    title: str = "Drawdown",
    output_path: Optional[str] = None,
) -> None:
    if not PLOTLY_AVAILABLE:
        print("Plotly not available, skipping chart generation")
        return

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=drawdown,
            fill="tozeroy",
            fillcolor="rgba(255,75,75,0.3)",
            mode="lines",
            name="Drawdown",
            line_color="red",
        )
    )
    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title="Drawdown",
        template="plotly_white",
    )

    if output_path:
        fig.write_html(output_path)
    else:
        fig.show()


def plot_daily_pnl(
    dates: list[str],
    net_pnl: list[float],
    title: str = "Daily PnL",
    output_path: Optional[str] = None,
) -> None:
    if not PLOTLY_AVAILABLE:
        print("Plotly not available, skipping chart generation")
        return

    colors = ["green" if p >= 0 else "red" for p in net_pnl]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(x=dates, y=net_pnl, marker_color=colors, name="Daily PnL")
    )
    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title="PnL",
        template="plotly_white",
    )

    if output_path:
        fig.write_html(output_path)
    else:
        fig.show()


def plot_full_report(
    dates: list[str],
    balance: list[float],
    drawdown: list[float],
    net_pnl: list[float],
    title: str = "Backtest Report",
    output_path: Optional[str] = None,
) -> None:
    if not PLOTLY_AVAILABLE:
        print("Plotly not available, skipping chart generation")
        return

    fig = make_subplots(
        rows=4,
        cols=1,
        subplot_titles=["Balance", "Drawdown", "Daily PnL", "PnL Distribution"],
        vertical_spacing=0.06,
    )

    fig.add_trace(
        go.Scatter(x=dates, y=balance, mode="lines", name="Balance"),
        row=1, col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=dates,
            y=drawdown,
            fill="tozeroy",
            fillcolor="rgba(255,75,75,0.3)",
            mode="lines",
            name="Drawdown",
            line_color="red",
        ),
        row=2, col=1,
    )

    colors = ["green" if p >= 0 else "red" for p in net_pnl]
    fig.add_trace(
        go.Bar(x=dates, y=net_pnl, marker_color=colors, name="Daily PnL"),
        row=3, col=1,
    )

    fig.add_trace(
        go.Histogram(
            x=net_pnl,
            nbinsx=50,
            name="Distribution",
            marker_color="steelblue",
        ),
        row=4, col=1,
    )

    fig.update_layout(
        title=title,
        height=1000,
        width=1000,
        template="plotly_white",
        showlegend=False,
    )

    if output_path:
        fig.write_html(output_path)
    else:
        fig.show()


def plot_performance_comparison(
    dates: list[str],
    strategy_balance: list[float],
    benchmark_balance: list[float],
    title: str = "Strategy vs Benchmark",
    output_path: Optional[str] = None,
) -> None:
    if not PLOTLY_AVAILABLE:
        print("Plotly not available, skipping chart generation")
        return

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=dates, y=strategy_balance,
            mode="lines", name="Strategy"
        )
    )
    fig.add_trace(
        go.Scatter(
            x=dates, y=benchmark_balance,
            mode="lines", name="Benchmark"
        )
    )

    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title="Balance",
        template="plotly_white",
    )

    if output_path:
        fig.write_html(output_path)
    else:
        fig.show()
