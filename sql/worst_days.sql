-- Ten worst SPY days and what the other ETFs did on the same day (diversification check).
WITH r AS (
    SELECT date, ticker,
           adj_close / LAG(adj_close) OVER (PARTITION BY ticker ORDER BY date) - 1 AS ret
    FROM prices
)
SELECT s.date, ROUND(s.ret*100,2) AS SPY_pct,
       ROUND(MAX(CASE WHEN o.ticker='AGG' THEN o.ret END)*100,2) AS AGG_pct,
       ROUND(MAX(CASE WHEN o.ticker='TLT' THEN o.ret END)*100,2) AS TLT_pct,
       ROUND(MAX(CASE WHEN o.ticker='GLD' THEN o.ret END)*100,2) AS GLD_pct
FROM r s JOIN r o ON o.date = s.date
WHERE s.ticker = 'SPY' AND s.ret IS NOT NULL
GROUP BY s.date ORDER BY s.ret ASC LIMIT 10;
