-- Five deepest drawdown episodes per strategy: peak date, trough, depth, recovery date.
-- An episode starts at a new high and ends at the next new high (NULL = not yet recovered).
WITH d AS (
    SELECT series, date, drawdown,
           SUM(CASE WHEN wealth >= peak THEN 1 ELSE 0 END)
               OVER (PARTITION BY series ORDER BY date ROWS UNBOUNDED PRECEDING) AS ep
    FROM v_drawdown WHERE series IN ('EQUAL_WEIGHT', 'SPY')
), e AS (
    SELECT series, ep, MIN(date) AS peak_date, MIN(drawdown) AS depth, MAX(date) AS last_date
    FROM d GROUP BY series, ep
), t AS (
    SELECT e.*,
           (SELECT date FROM d WHERE d.series = e.series AND d.ep = e.ep
            ORDER BY drawdown ASC LIMIT 1) AS trough_date,
           LEAD(peak_date) OVER (PARTITION BY series ORDER BY ep) AS recovery_date
    FROM e WHERE depth < 0
), r AS (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY series ORDER BY depth) AS rk FROM t
)
SELECT series, rk, peak_date, trough_date, ROUND(depth * 100, 2) AS depth_pct, recovery_date,
       CAST(julianday(COALESCE(recovery_date, last_date)) - julianday(peak_date) AS INT)
           AS days_peak_to_recovery
FROM r WHERE rk <= 5 ORDER BY series, rk;
