-- Calendar-year return and volatility: equal-weight portfolio vs SPY.
SELECT e.year,
       ROUND(e.ret * 100, 2) AS ew_ret_pct, ROUND(s.ret * 100, 2) AS spy_ret_pct,
       ROUND((e.ret - s.ret) * 100, 2) AS diff_pct,
       ROUND(e.vol * 100, 2) AS ew_vol_pct, ROUND(s.vol * 100, 2) AS spy_vol_pct
FROM v_annual e JOIN v_annual s ON s.year = e.year AND s.series = 'SPY'
WHERE e.series = 'EQUAL_WEIGHT' ORDER BY e.year;
