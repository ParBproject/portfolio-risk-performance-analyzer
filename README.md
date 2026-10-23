# Portfolio Risk & Performance Analyzer

**Question:** how does a diversified ETF portfolio compare with an equity benchmark (SPY) in return, risk and drawdowns?

Stage 1 of a staged build: real data pipeline → SQLite → equal-weight portfolio vs SPY → Streamlit dashboard. Stage 2 adds an analysis-ready SQL layer; stage 3 adds Sortino, Calmar, beta and rolling metrics; stage 4 adds a rolling minimum-variance portfolio. 

![dashboard](docs/dashboard.png)

## Setup
```bash
python -m venv .venv && . .venv/bin/activate
make install      # pip install -e ".[dev]"
make all          # recompute results, build SQLite + run SQL queries, ruff, pytest
make app          # streamlit run app/streamlit_app.py
```
The price snapshot in `data/raw/` is frozen and verified against `data/manifest.json` (SHA-256). `make data` re-downloads it, which will change the hashes.

## Data
- **Source:** Yahoo Finance via `yfinance` (`auto_adjust=False`), daily, 2006-01-03 to 2026-09-30, downloaded 2026-10-23.
- **Adjustments:** returns use `Adj Close`, which Yahoo back-adjusts for splits and cash distributions, so a return is a *total* return (price + reinvested dividends). Raw `Close` is kept in SQLite for comparison.
- **Missing values:** prices are aligned to SPY's trading calendar; gaps of ≤3 days would be forward-filled (zero return), longer gaps dropped. In this snapshot there were **0 missing values** (5,218 rows for every ETF).
- **Risk-free rate:** 13-week T-bill yield (`^IRX`) ÷ 100 ÷ 252 per day; averaged 1.69%/yr over the sample.
- **Limitations:** Yahoo is a free, unaudited source and its adjusted history can be revised; there is one historical path (2006–2026) with ETFs that survived (selection bias); ^IRX is a discount yield used as a simple approximation.

## Method
- Universe (one ETF per asset class): SPY US equity, EFA developed ex-US equity, AGG US aggregate bonds, TLT long Treasuries, GLD gold, VNQ US REITs.
- Equal weight 1/6 each, no estimation (so no lookahead). Weights drift daily and are reset on the last trading day of each month.
- Costs: 10 bp one-way × turnover at each rebalance, plus 10 bp on the initial purchase. SPY is buy-and-hold with no cost.
- Metrics: total & annualised (geometric) return, annualised vol (daily std × √252), Sharpe (mean daily excess return / std × √252), max drawdown, daily correlations.

## Findings so far (`results/stage1.json`, 2006-01-04 to 2026-09-30)
| | Equal weight | SPY |
|---|---|---|
| Total return | 312.0% | 778.8% |
| Annualised return | 7.08% | 11.07% |
| Annualised vol | 11.11% | 19.20% |
| Sharpe (vs T-bills) | 0.52 | 0.55 |
| Max drawdown | −32.2% | −55.2% |

- The diversified portfolio cut volatility by ~42% and max drawdown from −55% to −32% (both troughs on 2009-03-09), but gave up ~4 pp/yr of return. Risk-adjusted, it was roughly even with SPY (Sharpe 0.52 vs 0.55) — **diversification reduced risk, not improved Sharpe, in this sample**.
- Correlation of the portfolio with SPY: 0.81. SPY's daily correlation: EFA 0.88, VNQ 0.74, GLD 0.07, AGG 0.00, TLT −0.30 — bonds and gold do the diversifying.
- Average monthly turnover 2.5%; total cost drag ≈ 0.73% over 20 years.
- `sql/worst_days.sql`: on SPY's worst day (2020-03-16, −10.9%) TLT rose 6.5%; but on 2020-03-12 the hedges failed: AGG −4.0% and GLD −4.0% fell with SPY (−9.6%).

## Stage 2: SQL analysis layer
`make sql` (= `python scripts/run_queries.py`) rebuilds `data/prices.sqlite`, runs every query in `sql/` and saves each result to `results/sql/<query>.csv`. `tests/test_sql_layer.py` checks the SQL against independent pandas calculations (returns, monthly compounding, annual vol, drawdowns, rolling vol, stress returns, correlations, hit rates).

- **Tables:** `assets`, `prices` (raw + adjusted close), `risk_free`, `strategy_returns` (net daily equal-weight returns from the Python backtest), `stress_periods` (5 fixed windows).
- **Views:** `v_returns` (long table of daily returns for 6 ETFs + EQUAL_WEIGHT), `v_monthly` / `v_annual` (compounded via `exp(sum(ln(1+r)))`, annual vol), `v_drawdown` (wealth, running peak, drawdown).
- **Queries:** `annual_summary`, `monthly_hit_rate`, `rolling_vol_63d` / `rolling_vol_summary`, `drawdown_episodes`, `stress_periods`, `correlation_by_regime`, `stock_bond_corr_by_year`.

### Stage 2 findings
- **Calendar years** (`annual_summary.csv`): the portfolio beat SPY in 8 of 21 years (2026 is Jan–Sep only), including 2008 (−13.6% vs −36.8%), and lost by 31.7 pp in 2013. Its volatility was lower than SPY's in every year.
- **Monthly** (`monthly_hit_rate.csv`): it beat SPY in 39.8% of 249 months: 74.4% of SPY's 82 down months but only 22.8% of its 167 up months. Lower risk, lower return.
- **Rolling 63-day vol** (`rolling_vol_summary.csv`): averaged 9.7% vs 16.5% for SPY; peaks were 41.6% (2008-12-16) vs 74.3% (2008-12-11).
- **Drawdown episodes** (`drawdown_episodes.csv`): worst −32.2% (peak 2008-05-19, trough 2009-03-09, recovered 2010-03-17, 667 days), compared with SPY's −55.2% (2007-10-09 → 2009-03-09, recovered 2012-08-20, 1,777 days). But the portfolio's second-worst drawdown, 2022 (−23.9%), took **longer** to recover (924 days, to 2024-07-12) than SPY's (−24.5%, 710 days).
- **Stress windows** (`stress_periods.csv`): the portfolio lost less than SPY in all five: GFC −30.5% vs −55.2%, 2011 −4.4% vs −18.6%, Q4 2018 −6.1% vs −19.4%, COVID −17.6% vs −33.7%. The 2022 rate shock was the exception that mattered: −22.7% vs −24.5%, because TLT (−29.3%) and AGG (−14.4%) fell with stocks.
- **Correlation regimes** (`correlation_by_regime.csv`, `stock_bond_corr_by_year.csv`): in stress windows SPY's correlation with EFA rose to 0.93 (calm 0.85) and with VNQ to 0.80 (0.69), so equity diversification weakens when it is needed most. TLT stayed negative (−0.40 stress, −0.25 calm). But the SPY–TLT correlation was negative every year 2007–2021 and **positive every year 2022–2026** (0.36 in 2026 YTD): the bond hedge has broken down in the inflation regime.

Caveats: stress windows are fixed approximate SPY peak-to-trough dates (they are SPY-centric by construction), and correlations are descriptive, not tested for significance.

## Stage 3: full metric set and rolling metrics
`src/prpa/metrics.py` now also has Sortino, Calmar, beta, a correlation matrix and rolling return, volatility, Sharpe and correlation. Each one has a hand-checked test in `tests/test_metrics_stage3.py`. `python -m prpa.stage3` writes `results/stage3.json`.

- **Sortino** = mean daily excess return ÷ downside deviation × √252. The downside deviation is √mean(min(excess, 0)²) over *all* days, with the T-bill rate as the target.
- **Calmar** = annualised (geometric) return ÷ |max drawdown| over the full sample.
- **Beta** = cov(portfolio, SPY) ÷ var(SPY), from daily returns.
- **Rolling** windows are 252 trading days (1 year) for return, Sharpe and correlation, and 63 days for volatility. They stay NaN until the window is full.

### Stage 3 findings (`results/stage3.json`, 2006-01-04 to 2026-09-30)
| | Equal weight | SPY |
|---|---|---|
| Sharpe | 0.52 | 0.55 |
| Sortino | 0.73 | 0.78 |
| Calmar | 0.22 | 0.20 |
| Beta vs SPY | 0.47 | 1.00 |

- The ratios split. SPY was slightly ahead on Sharpe and Sortino, while the portfolio was slightly ahead on Calmar (return per unit of worst drawdown). None of these differences has been tested for significance, so none should be presented as a win.
- **Rolling 1-year windows** (4,966 windows):
  - The portfolio beat SPY on return in 33.2% of windows and on Sharpe in 46.4%.
  - It lost money in 15.0% of windows, against 17.0% for SPY.
  - Its worst 1-year return was −28.7% (window ending 2009-03-03), against −47.4% for SPY (ending 2009-03-05).
  - Its best was +44.3% (ending 2010-03-09), against +77.5% for SPY (ending 2021-03-23).
- **Rolling 1-year correlation with SPY** ranged from 0.32 (ending 2017-12-14) to 0.92 (ending 2008-10-30). The portfolio moved most like SPY during the 2008 crash, when diversification was needed most.

## Stage 4: minimum-variance portfolio
- **Estimation:** at each month-end close, the sample covariance of the trailing **252** daily returns (1 year, a standard window that was not tuned) goes into a long-only, fully invested minimum-variance solve. `src/prpa/optimize.py` solves it exactly by trying every support set (63 for 6 assets), so no solver dependency is needed.
- **Application:** weights are applied from the **next** trading day and drift until the next month-end. Costs are the same 10 bp one-way × turnover, plus 10 bp on the initial purchase.
- **Fair comparison:** min variance, equal weight (rerun on the same dates) and SPY are all measured over 2007-02-01 to 2026-09-30 (4,947 days), the period after the first full estimation window.
- **Tests** (`tests/test_min_variance.py`): hand-checked 2-asset cases, the long-only constraint binding, a brute-force grid check, weights sum to 1 and are ≥ 0, no-lookahead (scrambling future returns leaves past weights unchanged), next-day application, and a pin on the results.

### Stage 4 findings (`results/stage4.json`, `results/stage4_weights.csv`)
| 2007-02-01 to 2026-09-30 | Min variance | Equal weight | SPY |
|---|---|---|---|
| Annualised return | 3.31% | 6.59% | 10.89% |
| Annualised vol | 5.38% | 11.26% | 19.58% |
| Sharpe | 0.35 | 0.49 | 0.55 |
| Sortino | 0.48 | 0.69 | 0.77 |
| Max drawdown | −19.7% (trough 2022-10-20) | −32.2% | −55.2% |
| Calmar | 0.17 | 0.20 | 0.20 |
| Beta vs SPY | 0.09 | 0.47 | 1.00 |

- **Lowest risk, worst risk-adjusted return.** Min variance did what it is built to do: volatility was about half of equal weight's and drawdown was smallest. But its Sharpe (0.35) was the lowest of the three.
- **It is essentially an AGG portfolio.** The average weights were AGG 88.2%, SPY 7.3%, GLD 1.7%, TLT 1.4%, EFA 1.2% and VNQ 0.2%, with about 2.6 holdings above 1% on average. The latest estimate (2026-09-30) is 100% AGG. The optimiser concentrates in the lowest-volatility asset, so "minimum variance" here means "mostly bonds", not diversification.
- **Its worst drawdown came in 2022, not 2008,** because bonds were the risk in the rate shock.
- **Turnover and costs:** min variance averaged 3.7% per month (44% a year), with a largest single rebalance of 95.8%, against 2.6% per month (31% a year) for equal weight. Total cost drag was 0.97% vs 0.71% over the period, about 5 bp vs 4 bp a year, so costs did not explain the gap.

## Project layout
`src/prpa/` (config, ingest, clean, db, metrics, portfolio, analysis) · `sql/` schema + queries · `data/raw/` frozen CSVs · `app/` Streamlit · `tests/` pytest.

## License
MIT
