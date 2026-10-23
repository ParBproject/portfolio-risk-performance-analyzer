-- Calendar-year daily correlation of SPY with TLT and AGG (does the bond hedge hold up?).
WITH x AS (
    SELECT substr(s.date, 1, 4) AS year, o.series AS other, s.ret AS a, o.ret AS b
    FROM v_returns s JOIN v_returns o ON o.date = s.date
    WHERE s.series = 'SPY' AND o.series IN ('TLT', 'AGG')
)
SELECT year,
       ROUND(MAX(CASE WHEN other = 'TLT' THEN c END), 4) AS spy_tlt_corr,
       ROUND(MAX(CASE WHEN other = 'AGG' THEN c END), 4) AS spy_agg_corr
FROM (
    SELECT year, other,
           (AVG(a * b) - AVG(a) * AVG(b))
           / sqrt((AVG(a * a) - AVG(a) * AVG(a)) * (AVG(b * b) - AVG(b) * AVG(b))) AS c
    FROM x GROUP BY year, other
) GROUP BY year ORDER BY year;
