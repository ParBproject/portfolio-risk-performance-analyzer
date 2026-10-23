-- How often the portfolio beat SPY, and how it did in SPY's up vs down months.
SELECT CASE WHEN s.ret < 0 THEN 'SPY down month' ELSE 'SPY up month' END AS regime,
       COUNT(*) AS n_months,
       ROUND(AVG(e.ret > s.ret), 4) AS ew_beat_rate,
       ROUND(AVG(e.ret) * 100, 3) AS ew_avg_pct,
       ROUND(AVG(s.ret) * 100, 3) AS spy_avg_pct
FROM v_monthly e JOIN v_monthly s ON s.month = e.month AND s.series = 'SPY'
WHERE e.series = 'EQUAL_WEIGHT'
GROUP BY regime
UNION ALL
SELECT 'All months', COUNT(*), ROUND(AVG(e.ret > s.ret), 4),
       ROUND(AVG(e.ret) * 100, 3), ROUND(AVG(s.ret) * 100, 3)
FROM v_monthly e JOIN v_monthly s ON s.month = e.month AND s.series = 'SPY'
WHERE e.series = 'EQUAL_WEIGHT';
