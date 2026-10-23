-- Data coverage per ticker: first and last date and number of trading days.
SELECT p.ticker, a.asset_class, MIN(p.date) AS first_date, MAX(p.date) AS last_date,
       COUNT(*) AS n_days
FROM prices p JOIN assets a USING (ticker)
GROUP BY p.ticker ORDER BY p.ticker;
