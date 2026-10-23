-- Rolling 63-trading-day (~3 month) annualised volatility, only once a full window exists.
WITH s AS (
    SELECT series, date, ret,
           ROW_NUMBER() OVER w AS rn,
           SUM(ret) OVER (w ROWS 62 PRECEDING) AS s1,
           SUM(ret * ret) OVER (w ROWS 62 PRECEDING) AS s2
    FROM v_returns
    WINDOW w AS (PARTITION BY series ORDER BY date)
)
SELECT series, date, sqrt((s2 - s1 * s1 / 63.0) / 62.0) * sqrt(252) AS vol_63d
FROM s WHERE rn >= 63 ORDER BY series, date;
