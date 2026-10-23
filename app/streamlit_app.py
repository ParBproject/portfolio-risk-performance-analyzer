"""Streamlit dashboard. Run: make app"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from prpa import config, dashboard

EMERALD, BG, GREY, AMBER = "#10B981", "#06080b", "#9ca3af", "#f59e0b"
COLORS = {"Min variance": AMBER, "Equal weight": EMERALD, "SPY": GREY}

st.set_page_config(page_title="Portfolio Risk & Performance Analyzer", layout="wide")
st.markdown(
    """<style>
    .block-container {padding-top: 2rem; max-width: 1200px;}
    @media (max-width: 640px) {
      .block-container {padding: 3.5rem 0.6rem 1rem;}
      h1 {font-size: 1.5rem !important;}
      h2, h3 {font-size: 1.15rem !important;}
    }
    </style>""",
    unsafe_allow_html=True,
)
st.title("Portfolio Risk & Performance Analyzer")
st.caption(
    "Six-ETF portfolios vs SPY on real Yahoo Finance data (frozen snapshot to 2026-09-30). "
    "Monthly rebalancing, 10 bp one-way costs, T-bill (^IRX) risk-free rate."
)


@st.cache_data
def data():
    return dashboard.load()


d = data()
rets_all, rf_all = d["rets"], d["rf"]
lo, hi = rets_all.index[0].date(), rets_all.index[-1].date()

with st.sidebar:
    st.header("Controls")
    chosen = st.multiselect("Strategies", dashboard.STRATEGIES, default=list(dashboard.STRATEGIES))
    start = st.date_input("Start", lo, min_value=lo, max_value=hi)
    end = st.date_input("End", hi, min_value=lo, max_value=hi)
    st.caption(
        "Strategies run continuously from 2007-02-01 (first full 252-day window); "
        "the dates only slice the results."
    )

if not chosen:
    st.warning("Pick at least one strategy.")
    st.stop()
try:
    rets = dashboard.filter_dates(rets_all[chosen], start, end)
    table = dashboard.risk_table(rets, rf_all)
except ValueError as e:
    st.error(str(e))
    st.stop()


def styled(fig, height=340):
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=BG,
        plot_bgcolor=BG,
        height=height,
        margin=dict(l=8, r=8, t=40, b=60),
        legend=dict(orientation="h", yanchor="top", y=-0.12, x=0, title_text=""),
    )
    return fig


def lines(df, title, fmt=None):
    fig = go.Figure()
    for c in df.columns:
        fig.add_scatter(x=df.index, y=df[c], name=c, line_color=COLORS.get(c, EMERALD))
    fig.update_layout(title=title)
    if fmt:
        fig.update_layout(yaxis_tickformat=fmt)
    return styled(fig)


tab_perf, tab_w, tab_stress = st.tabs(["Performance", "Weights", "Stress & correlation"])

with tab_perf:
    st.subheader("Risk summary")
    pct = ["Total return", "Ann. return", "Ann. vol", "Max DD"]
    st.dataframe(
        table.style.format(
            {c: "{:.1%}" for c in pct} | {c: "{:.2f}" for c in ("Sharpe", "Sortino", "Calmar")}
        ),
        use_container_width=True,
    )
    st.plotly_chart(lines(dashboard.growth(rets), "Growth of $1"), use_container_width=True)
    st.plotly_chart(lines(dashboard.drawdowns(rets), "Drawdown", ".0%"), use_container_width=True)
    rs = dashboard.rolling_sharpe(rets, rf_all)
    if len(rs):
        st.plotly_chart(lines(rs, "Rolling 1-year Sharpe"), use_container_width=True)
    else:
        st.info("Rolling Sharpe needs at least 252 days in the selected range.")

with tab_w:
    who = st.selectbox("Strategy", chosen, key="wsel")
    w = d["weights"][who]
    when, cur = dashboard.weights_as_of(w, end)
    st.subheader(f"Current weights ({when.date()})")
    bar = px.bar(
        x=cur.index,
        y=cur.values,
        labels={"x": "", "y": "Weight"},
        color_discrete_sequence=[COLORS[who]],
    )
    st.plotly_chart(
        styled(bar.update_layout(yaxis_tickformat=".0%"), 280), use_container_width=True
    )
    hist = w.loc[pd.Timestamp(start) : pd.Timestamp(end)]
    if len(hist):
        area = px.area(hist, title="Target weights at each month-end")
        st.plotly_chart(
            styled(area.update_layout(yaxis_tickformat=".0%")), use_container_width=True
        )
    st.caption(
        "Min variance: long-only, fully invested, trailing 252-day sample covariance, "
        "re-estimated each month-end and applied from the next day."
    )

with tab_stress:
    st.subheader("Stress periods (SQL: sql/stress_periods.sql)")
    stress = dashboard.stress_table()
    st.dataframe(
        stress.style.format(
            {c: "{:.1f}%" for c in stress.columns if c not in ("start_date", "end_date")}
        ),
        use_container_width=True,
    )
    st.caption("Equal weight here is the stage 1 series from 2006; values are % returns.")
    st.subheader("SPY correlation: calm vs stress (sql/correlation_by_regime.sql)")
    rc = dashboard.regime_corr()
    st.plotly_chart(
        styled(px.bar(rc, barmode="group", color_discrete_sequence=[GREY, EMERALD]), 300),
        use_container_width=True,
    )
    yb = dashboard.sql_result("stock_bond_corr_by_year").set_index("year")
    fig = lines(
        yb.rename(columns={"spy_tlt_corr": "SPY–TLT", "spy_agg_corr": "SPY–AGG"}),
        "Stock–bond correlation by year (sql/stock_bond_corr_by_year.sql)",
    )
    st.plotly_chart(fig, use_container_width=True)
    corr = d["asset_rets"].loc[rets.index].corr()
    heat = px.imshow(
        corr,
        text_auto=".2f",
        zmin=-1,
        zmax=1,
        color_continuous_scale=["#111827", EMERALD],
        title="Daily ETF correlations (selected dates)",
    )
    st.plotly_chart(styled(heat, 420), use_container_width=True)

st.caption(f"Data: {config.ROOT.name} · one historical path; see README for limitations.")
