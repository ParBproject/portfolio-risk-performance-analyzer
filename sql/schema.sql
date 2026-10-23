DROP VIEW IF EXISTS v_drawdown;
DROP VIEW IF EXISTS v_annual;
DROP VIEW IF EXISTS v_monthly;
DROP VIEW IF EXISTS v_returns;
DROP TABLE IF EXISTS prices;
DROP TABLE IF EXISTS assets;
DROP TABLE IF EXISTS risk_free;
CREATE TABLE assets (ticker TEXT PRIMARY KEY, asset_class TEXT NOT NULL);
CREATE TABLE prices (
    date TEXT NOT NULL,
    ticker TEXT NOT NULL REFERENCES assets(ticker),
    close REAL NOT NULL CHECK (close > 0),       -- raw traded close
    adj_close REAL NOT NULL CHECK (adj_close > 0), -- split + dividend adjusted
    volume REAL,
    PRIMARY KEY (date, ticker)
);
CREATE TABLE risk_free (date TEXT PRIMARY KEY, rf_daily REAL NOT NULL);
DROP TABLE IF EXISTS strategy_returns;
-- Net daily returns of strategies computed in Python (prpa.portfolio.backtest).
CREATE TABLE strategy_returns (
    date TEXT NOT NULL, strategy TEXT NOT NULL, ret REAL NOT NULL,
    PRIMARY KEY (date, strategy)
);
