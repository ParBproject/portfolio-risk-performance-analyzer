"""Streamlit dashboard: equal-weight ETF portfolio vs SPY. Run: make app"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from prpa import config, metrics
from prpa.analysis import run

EMERALD, BG = "#10B981", "#06080b"
st.set_page_config(page_title="Portfolio Risk & Performance Analyzer", layout="wide")
st.title("Portfolio Risk & Performance Analyzer")
st.caption(
    "Equal-weight 6-ETF portfolio (monthly rebalance, 10 bp one-way costs) vs SPY. "
    "Real Yahoo Finance data, frozen snapshot through 2026-09-30."
)


@st.cache_data
def full():
    return run()


base = full()["rets"].index
c1, c2 = st.columns(2)
start = c1.date_input("Start", base[0].date(), min_value=base[0].date(), max_value=base[-1].date())
end = c2.date_input("End", base[-1].date(), min_value=base[0].date(), max_value=base[-1].date())
if start >= end:
    st.error("Start must be before end.")
    st.stop()
r = run(str(start), str(end))  # re-runs the backtest from the chosen start (fresh buy-in)
port, bench, rf, rets = r["port"], r["bench"], r["rf"], r["rets"]

st.subheader("Weights")
st.write(", ".join(f"{t} {1 / len(rets.columns):.1%} ({c})" for t, c in config.UNIVERSE.items()))

rows = {"Equal weight": metrics.summary(port, rf), "SPY": metrics.summary(bench, rf)}
tbl = pd.DataFrame(rows).T[
    [
        "total_return",
        "annualized_return",
        "annualized_vol",
        "sharpe",
        "sortino",
        "max_drawdown",
        "calmar",
    ]
]
st.subheader("Risk summary")
st.dataframe(
    tbl.style.format(
        {
            "sharpe": "{:.2f}",
            "sortino": "{:.2f}",
            "calmar": "{:.2f}",
            "total_return": "{:.1%}",
            "annualized_return": "{:.2%}",
            "annualized_vol": "{:.2%}",
            "max_drawdown": "{:.1%}",
        }
    )
)


def styled(fig):
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=BG,
        plot_bgcolor=BG,
        height=360,
        margin=dict(l=10, r=10, t=40, b=10),
    )
    return fig


g = pd.DataFrame({"Equal weight": metrics.cumulative(port), "SPY": metrics.cumulative(bench)})
fig = go.Figure()
fig.add_scatter(x=g.index, y=g["Equal weight"], name="Equal weight", line_color=EMERALD)
fig.add_scatter(x=g.index, y=g["SPY"], name="SPY", line_color="#9ca3af")
st.plotly_chart(styled(fig.update_layout(title="Growth of $1")), use_container_width=True)

dd = pd.DataFrame({"Equal weight": metrics.drawdown(port), "SPY": metrics.drawdown(bench)})
fig = go.Figure()
fig.add_scatter(
    x=dd.index, y=dd["Equal weight"], name="Equal weight", line_color=EMERALD, fill="tozeroy"
)
fig.add_scatter(x=dd.index, y=dd["SPY"], name="SPY", line_color="#9ca3af")
st.plotly_chart(
    styled(fig.update_layout(title="Drawdown", yaxis_tickformat=".0%")), use_container_width=True
)

rs = pd.DataFrame(
    {
        "Equal weight": metrics.rolling_sharpe(port, rf),
        "SPY": metrics.rolling_sharpe(bench, rf),
    }
).dropna()
fig = go.Figure()
fig.add_scatter(x=rs.index, y=rs["Equal weight"], name="Equal weight", line_color=EMERALD)
fig.add_scatter(x=rs.index, y=rs["SPY"], name="SPY", line_color="#9ca3af")
st.plotly_chart(styled(fig.update_layout(title="Rolling 1-year Sharpe")), use_container_width=True)

corr = metrics.correlation_matrix(rets)
fig = px.imshow(
    corr,
    text_auto=".2f",
    color_continuous_scale=["#111827", EMERALD],
    zmin=-1,
    zmax=1,
    title="Daily return correlations",
)
st.plotly_chart(styled(fig), use_container_width=True)
st.caption(
    "Sharpe uses the 13-week T-bill (^IRX) as the risk-free rate. Past performance over "
    "one historical path; see README for limitations."
)
