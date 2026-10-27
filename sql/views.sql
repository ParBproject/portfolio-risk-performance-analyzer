-- Analysis-ready layer. Built after schema.sql and data load (see prpa.db.build).

-- Stress windows: fixed dates around large SPY declines (approximate peak to trough).
DROP TABLE IF EXISTS stress_periods;
CREATE TABLE stress_periods (name TEXT PRIMARY KEY, start_date TEXT NOT NULL, end_date TEXT NOT NULL);
INSERT INTO stress_periods VALUES
  ('GFC 2007-09',          '2007-10-09', '2009-03-09'),
  ('Euro crisis 2011',     '2011-04-29', '2011-10-03'),
  ('Q4 2018 sell-off',     '2018-09-20', '2018-12-24'),
  ('COVID crash 2020',     '2020-02-19', '2020-03-23'),
  ('2022 rate shock',      '2022-01-03', '2022-10-12');

-- One long table of daily simple returns: 6 ETFs (from adj_close) + 2 strategies.
DROP VIEW IF EXISTS v_returns;
CREATE VIEW v_returns AS
SELECT date, series, ret FROM (
    SELECT date, ticker AS series,
           adj_close / LAG(adj_close) OVER (PARTITION BY ticker ORDER BY date) - 1 AS ret
    FROM prices
) WHERE ret IS NOT NULL
UNION ALL
SELECT date, strategy AS series, ret FROM strategy_returns;

-- Monthly and annual compounded returns: prod(1+r)-1 = exp(sum(ln(1+r)))-1.
DROP VIEW IF EXISTS v_monthly;
CREATE VIEW v_monthly AS
SELECT series, substr(date, 1, 7) AS month, COUNT(*) AS n_days,
       exp(SUM(ln(1 + ret))) - 1 AS ret
FROM v_returns GROUP BY series, month;

DROP VIEW IF EXISTS v_annual;
CREATE VIEW v_annual AS
SELECT series, substr(date, 1, 4) AS year, COUNT(*) AS n_days,
       exp(SUM(ln(1 + ret))) - 1 AS ret,
       sqrt((SUM(ret * ret) - SUM(ret) * SUM(ret) / COUNT(*)) / (COUNT(*) - 1)) * sqrt(252) AS vol
FROM v_returns GROUP BY series, year;

-- Wealth index, running peak (starting $1 counts as a peak) and drawdown.
DROP VIEW IF EXISTS v_drawdown;
CREATE VIEW v_drawdown AS
WITH w AS (
    SELECT series, date,
           exp(SUM(ln(1 + ret)) OVER (PARTITION BY series ORDER BY date
                                      ROWS UNBOUNDED PRECEDING)) AS wealth
    FROM v_returns
), p AS (
    SELECT series, date, wealth,
           MAX(1.0, MAX(wealth) OVER (PARTITION BY series ORDER BY date
                                      ROWS UNBOUNDED PRECEDING)) AS peak
    FROM w
)
SELECT series, date, wealth, peak, wealth / peak - 1 AS drawdown FROM p;
