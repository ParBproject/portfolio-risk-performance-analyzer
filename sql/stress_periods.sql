-- Compounded return of every series inside each stress window.
SELECT p.name, p.start_date, p.end_date,
       ROUND(MAX(CASE WHEN r.series = 'EQUAL_WEIGHT' THEN r.tot END) * 100, 2) AS EW,
       ROUND(MAX(CASE WHEN r.series = 'SPY' THEN r.tot END) * 100, 2) AS SPY,
       ROUND(MAX(CASE WHEN r.series = 'EFA' THEN r.tot END) * 100, 2) AS EFA,
       ROUND(MAX(CASE WHEN r.series = 'AGG' THEN r.tot END) * 100, 2) AS AGG,
       ROUND(MAX(CASE WHEN r.series = 'TLT' THEN r.tot END) * 100, 2) AS TLT,
       ROUND(MAX(CASE WHEN r.series = 'GLD' THEN r.tot END) * 100, 2) AS GLD,
       ROUND(MAX(CASE WHEN r.series = 'VNQ' THEN r.tot END) * 100, 2) AS VNQ
FROM stress_periods p
JOIN (
    SELECT p2.name, v.series, exp(SUM(ln(1 + v.ret))) - 1 AS tot
    FROM stress_periods p2
    JOIN v_returns v ON v.date > p2.start_date AND v.date <= p2.end_date
    GROUP BY p2.name, v.series
) r ON r.name = p.name
GROUP BY p.name ORDER BY p.start_date;
