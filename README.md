# Portfolio Risk & Performance Analyzer

[![CI](https://github.com/ParBproject/portfolio-risk-performance-analyzer/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/ParBproject/portfolio-risk-performance-analyzer/actions/workflows/ci.yml)

A six-ETF portfolio against SPY, from January 2006 through September 2026: return, volatility, drawdowns, and a long-only minimum-variance variant.

Over the full sample the equal-weight portfolio (SPY, EFA, AGG, TLT, GLD, VNQ) had annualised volatility of 11.11% against SPY's 19.20% (about 42% lower) and a worst drawdown of −32.2% against −55.2%. Annualised return was 7.08% against 11.07%. Sharpe ratios were close, 0.52 and 0.55. The minimum-variance portfolio cut volatility further, to 5.38%, and held mostly bonds; its Sharpe was 0.35.

**Dashboard:** https://parb-portfolio-analyzer.streamlit.app/

**Static pages:** https://parbproject.github.io/portfolio-risk-performance-analyzer/

![dashboard](docs/dashboard.png)

## Setup

```bash
git clone https://github.com/ParBproject/portfolio-risk-performance-analyzer
cd portfolio-risk-performance-analyzer
python -m venv .venv && . .venv/bin/activate
make install      # pip install -e ".[dev]"
make all          # rebuild results, run the SQL, ruff, pytest
make app          # Streamlit at http://localhost:8501
make coverage
```

`make all` reads the CSVs in `data/raw/` and checks them against the SHA-256 hashes in `data/manifest.json`. `make data` downloads a fresh snapshot from Yahoo Finance, which changes the hashes and the results.

## Data

Yahoo Finance via `yfinance` (`auto_adjust=False`), downloaded 2026-10-23. Each ETF file has 5,218 rows from 2006-01-03 to 2026-09-30 (`results/sql/coverage.csv`).

| Ticker | What it is |
|---|---|
| SPY | US large-cap equity, and the benchmark |
| EFA | Developed markets ex-US equity |
| AGG | US aggregate bonds |
| TLT | Long-term US Treasuries |
| GLD | Gold |
| VNQ | US REITs |

The risk-free series is the 13-week T-bill yield (`^IRX`), divided by 100 and by 252. It averaged 1.69% a year (`results/stage1.json`). `^IRX` is a discount yield, so this is an approximation of a daily rate.

Returns use `Adj Close`, which includes dividends and splits. Raw `Close` is kept in SQLite. Prices are aligned to SPY's calendar. Gaps of up to 3 days are forward-filled; longer gaps are dropped. This snapshot had no missing prices after that step (`results/stage1.json`, `cleaning`). Dates must be sorted and unique, prices must be positive, and a daily move above 25% fails validation.

## Method

**Equal weight.** Each ETF starts at 1/6. Weights drift with prices and reset on the last trading day of the month. Cost is 10 bp one-way times turnover, including 10 bp on the first purchase. The SPY line in this comparison is buy-and-hold. Code: `src/prpa/portfolio.py`, `src/prpa/analysis.py`. Output: `results/stage1.json`.

**Minimum variance.** At each month-end the weights are the long-only, fully invested minimum-variance portfolio on the trailing 252 daily returns. With six names that is an exact search over the 63 subsets. Weights apply from the next session, with the same 10 bp cost. Equal weight and SPY are recomputed on the same dates, 2007-02-01 to 2026-09-30, once a full window exists. Code: `src/prpa/optimize.py`, `src/prpa/stage4.py`.

**Metrics** in `src/prpa/metrics.py` use simple daily returns and 252 days per year.

| Metric | Definition |
|---|---|
| Annualised return | (1 + total return) ^ (252 / n) − 1 |
| Annualised vol | sample standard deviation × √252 |
| Sharpe | mean(r − rf) / std(r − rf) × √252 |
| Sortino | mean excess / √mean(min(excess, 0)²) × √252, with the downside taken over every day |
| Max drawdown | min of wealth / running peak − 1; the peak starts at $1 |
| Calmar | annualised return / \|max drawdown\| |
| Beta | cov(r, SPY) / var(SPY) |
| Rolling | 252-day return, Sharpe and correlation; 63-day volatility |

**SQL.** `make sql` loads `assets`, `prices`, `risk_free`, `strategy_returns` and `stress_periods`, builds `v_returns`, `v_monthly`, `v_annual` and `v_drawdown`, and writes `results/sql/*.csv`. The tests recompute the same figures in pandas.

## Results

### Equal weight and SPY, 2006-01-04 to 2026-09-30

`results/stage1.json` and `results/stage3.json`.

| | Equal weight | SPY |
|---|---|---|
| Total return | 312.0% | 778.8% |
| Annualised return | 7.08% | 11.07% |
| Annualised vol | 11.11% | 19.20% |
| Sharpe | 0.52 | 0.55 |
| Sortino | 0.73 | 0.78 |
| Max drawdown | −32.2% | −55.2% |
| Calmar | 0.22 | 0.20 |
| Beta vs SPY | 0.47 | 1.00 |

Both drawdowns bottomed on 2009-03-09. Correlation of the portfolio with SPY was 0.81. Average monthly turnover was 2.5%, and the cost drag over the whole sample was about 0.73% (`results/stage1.json`).

Daily correlation of SPY with the other ETFs: EFA 0.88, VNQ 0.74, GLD 0.07, AGG 0.00, TLT −0.30.

### Up months, down months, stress windows

`results/sql/`.

The portfolio beat SPY in 39.8% of 249 months (`monthly_hit_rate.csv`): 74.4% of SPY's 82 down months and 22.8% of its 167 up months.

It beat SPY in 8 of 21 years (`annual_summary.csv`). 2026 in that file is January through September. In 2008 the portfolio returned −13.6% and SPY −36.8%. In 2013 the portfolio trailed by 31.7 percentage points. Portfolio volatility was below SPY's in every year in the file.

Stress windows in `stress_periods.csv` (compounded return from the day after the start date through the end date):

| Window | Equal weight | SPY | TLT | AGG |
|---|---|---|---|---|
| GFC 2007-10-09 → 2009-03-09 | −30.5% | −55.2% | +25.1% | +7.4% |
| Euro crisis 2011 | −4.4% | −18.6% | +34.6% | +5.3% |
| Q4 2018 sell-off | −6.1% | −19.4% | +4.5% | +1.6% |
| COVID 2020-02-19 → 2020-03-23 | −17.6% | −33.7% | +14.2% | −1.3% |
| 2022 rate shock | −22.7% | −24.5% | −29.3% | −14.4% |

In the 2022 window bonds fell with equities, and the equal-weight result (−22.7%) sits next to SPY (−24.5%). SPY–TLT daily correlation was negative in each year from 2007 through 2021 and positive in each year from 2022 through 2026 (0.36 in 2026 year-to-date) (`stock_bond_corr_by_year.csv`).

On stress days, correlation of SPY with EFA was 0.93, against 0.85 on other days, and with VNQ 0.80 against 0.69 (`correlation_by_regime.csv`).

SPY took 1,777 days to recover the 2007–09 drawdown. The portfolio took 667 days to recover its 2008–09 drawdown, and 924 days to recover the 2022 drawdown, compared with 710 days for SPY (`drawdown_episodes.csv`).

63-day volatility averaged 9.7% for the portfolio and 16.5% for SPY. The peaks were 41.6% and 74.3%, both in December 2008 (`rolling_vol_summary.csv`).

### Rolling one-year windows

`results/stage3.json`, 4,966 windows.

The portfolio's one-year return was above SPY's in 33.2% of windows, and its one-year Sharpe was above SPY's in 46.4%. The portfolio return was negative in 15.0% of windows and SPY's in 17.0%. The worst window was −28.7% for the portfolio and −47.4% for SPY. The best was +44.3% and +77.5%. Rolling correlation with SPY ranged from 0.32 (window ending 2017-12-14) to 0.92 (ending 2008-10-30).

### Minimum variance, 2007-02-01 to 2026-09-30

`results/stage4.json`, `results/stage4_weights.csv`.

| | Min variance | Equal weight | SPY |
|---|---|---|---|
| Annualised return | 3.31% | 6.59% | 10.89% |
| Annualised vol | 5.38% | 11.26% | 19.58% |
| Sharpe | 0.35 | 0.49 | 0.55 |
| Sortino | 0.48 | 0.69 | 0.77 |
| Max drawdown | −19.7% | −32.2% | −55.2% |
| Calmar | 0.17 | 0.20 | 0.20 |
| Beta vs SPY | 0.09 | 0.47 | 1.00 |
| Avg monthly turnover | 3.7% | 2.6% | |
| Total cost | 0.97% | 0.71% | |

The average AGG weight was 88.2%, and the average number of holdings above 1% was about 2.6. On 2026-09-30 the estimate is 100% AGG. The minimum-variance drawdown troughed on 2022-10-20. The largest single rebalance turned over 95.8%. Cost over the sample was 0.97%, about 5 bp a year, next to an annualised-return gap of roughly 3 percentage points versus equal weight.

## Limitations

- The sample is one path, 2006–2026, covering the decline in yields into 2021 and the 2022 bond sell-off. The Sharpe gap of 0.52 versus 0.55 is small.
- The six ETFs all survived. They were chosen as one fund per asset class with history through 2008.
- Yahoo revises adjusted history. The files here are hashed, and they are still a free vendor snapshot.
- Costs are a flat 10 bp one-way. Spreads, impact and taxes are left out. ETF expense ratios are already in the prices. The SPY buy-and-hold line pays no trading cost.
- The covariance is a one-year sample, with no shrinkage and no weight cap.
- Stress dates are fixed windows around large SPY declines.
- Changing the dashboard dates slices the stored return series. It does not rerun the backtest from the new start date.

## Dashboard

`make app` opens Streamlit. The sidebar picks strategies and a date range. Three tabs: Performance (risk table, growth of $1, drawdown, rolling Sharpe), Weights, and Stress & correlation.

| | Desktop | Mobile |
|---|---|---|
| Performance | ![](docs/dashboard-desktop-performance.png) | ![](docs/dashboard-mobile-performance.png) |
| Weights | ![](docs/dashboard-desktop-weights.png) | ![](docs/dashboard-mobile-weights.png) |
| Stress & correlation | ![](docs/dashboard-desktop-stress.png) | ![](docs/dashboard-mobile-stress.png) |

`make site` rewrites `site/data.json` from the result files. The page plots week-ending samples of the daily series, plus the last day, so a trough that falls mid-week can look slightly shallower than the max-drawdown figure in the table.

## Tests

`make all` runs ruff and pytest. `make coverage` adds a coverage report.

Covered: metric examples (a +20% day then a −25% day is a −25% drawdown; uncorrelated assets with volatility 10% and 20% get weights 0.8 and 0.2), future-return checks on both backtests, SQL against pandas, hash and schema failures, a Streamlit `AppTest`, a rebuild of `results/stage1.json`, `stage3.json`, `stage4.json` and `stage4_weights.csv`, and `tests/test_readme.py`, which checks the figures in this file against those outputs.

A constant excess return makes the Sharpe denominator zero; that case returns NaN. A target weight that omits an asset is rejected.

## Layout

```
src/prpa/    config, ingest, clean, db, metrics, portfolio, optimize,
             analysis, stage3, stage4, dashboard, site
sql/         schema, views, queries
scripts/     run_queries.py, deploy_pages.sh
site/        index.html, app.js, style.css, data.json
data/raw/    Yahoo CSVs and data/manifest.json
results/     stage1.json, stage3.json, stage4.json, stage4_weights.csv, sql/
app/         streamlit_app.py
tests/
docs/        screenshots
```

## License

MIT. See [LICENSE](LICENSE).
