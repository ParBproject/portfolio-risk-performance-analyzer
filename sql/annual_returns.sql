-- Calendar-year total return per ticker from adjusted closes (last close of year vs prior).
WITH year_end AS (
    SELECT ticker, substr(date, 1, 4) AS yr, adj_close,
           ROW_NUMBER() OVER (PARTITION BY ticker, substr(date, 1, 4) ORDER BY date DESC) AS rn
    FROM prices
), ye AS (SELECT ticker, yr, adj_close FROM year_end WHERE rn = 1)
SELECT cur.yr AS year,
       ROUND(MAX(CASE WHEN cur.ticker='SPY' THEN cur.adj_close/prev.adj_close-1 END)*100,2) AS SPY,
       ROUND(MAX(CASE WHEN cur.ticker='EFA' THEN cur.adj_close/prev.adj_close-1 END)*100,2) AS EFA,
       ROUND(MAX(CASE WHEN cur.ticker='AGG' THEN cur.adj_close/prev.adj_close-1 END)*100,2) AS AGG,
       ROUND(MAX(CASE WHEN cur.ticker='TLT' THEN cur.adj_close/prev.adj_close-1 END)*100,2) AS TLT,
       ROUND(MAX(CASE WHEN cur.ticker='GLD' THEN cur.adj_close/prev.adj_close-1 END)*100,2) AS GLD,
       ROUND(MAX(CASE WHEN cur.ticker='VNQ' THEN cur.adj_close/prev.adj_close-1 END)*100,2) AS VNQ
FROM ye cur JOIN ye prev ON prev.ticker = cur.ticker AND CAST(prev.yr AS INT) = CAST(cur.yr AS INT) - 1
GROUP BY cur.yr ORDER BY cur.yr;
