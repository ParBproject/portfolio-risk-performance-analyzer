-- Peak, median-ish (average) and latest 63-day vol for the portfolio vs SPY.
WITH s AS (
    SELECT series, date, ret,
           ROW_NUMBER() OVER w AS rn,
           SUM(ret) OVER (w ROWS 62 PRECEDING) AS s1,
           SUM(ret * ret) OVER (w ROWS 62 PRECEDING) AS s2
    FROM v_returns WHERE series IN ('EQUAL_WEIGHT', 'SPY')
    WINDOW w AS (PARTITION BY series ORDER BY date)
), v AS (
    SELECT series, date, sqrt((s2 - s1 * s1 / 63.0) / 62.0) * sqrt(252) AS vol
    FROM s WHERE rn >= 63
)
SELECT series,
       ROUND(AVG(vol), 4) AS avg_vol_63d,
       ROUND(MAX(vol), 4) AS max_vol_63d,
       (SELECT date FROM v v2 WHERE v2.series = v.series ORDER BY vol DESC LIMIT 1) AS max_date,
       (SELECT ROUND(vol, 4) FROM v v3 WHERE v3.series = v.series ORDER BY date DESC LIMIT 1)
           AS latest_vol_63d
FROM v GROUP BY series ORDER BY series;
