-- Daily Pearson correlation of SPY with each other ETF: inside stress windows vs calm days.
WITH x AS (
    SELECT s.date, o.series AS other, s.ret AS a, o.ret AS b,
           CASE WHEN EXISTS (SELECT 1 FROM stress_periods p
                             WHERE s.date > p.start_date AND s.date <= p.end_date)
                THEN 'stress' ELSE 'calm' END AS regime
    FROM v_returns s JOIN v_returns o ON o.date = s.date
    WHERE s.series = 'SPY' AND o.series IN ('EFA', 'AGG', 'TLT', 'GLD', 'VNQ')
)
SELECT regime, other, COUNT(*) AS n_days,
       ROUND((AVG(a * b) - AVG(a) * AVG(b))
             / sqrt((AVG(a * a) - AVG(a) * AVG(a)) * (AVG(b * b) - AVG(b) * AVG(b))), 4) AS corr
FROM x GROUP BY regime, other ORDER BY other, regime;
