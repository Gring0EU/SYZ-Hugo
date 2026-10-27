# Syz Data Lab

`syz_data_lab.html` shows what the free data sources can do together, on one
illustrative product: a 12-month quanto-CHF worst-of Barrier Reverse
Convertible on Nestlé, ASML and Microsoft (strike 100%, European barrier 60%).

| Source | Used for |
|---|---|
| Yahoo Finance (yfinance) | 7 years of daily closes, dividend, P/E, market cap, beta, results date, the Microsoft option chain |
| ECB data API | Daily CHF and USD reference rates: FX volatility, stock–FX correlation, the quanto drift, a cross-check of Yahoo's FX |
| SNB data portal | SARON (discounting), €STR and SOFR (the drift of the EUR and USD names) |
| TradingView | Live tape and charts, in the browser only |

The engine: Microsoft's implied volatility smile solved from option mid
prices, realised and EWMA volatilities, a 5-year weekly correlation matrix
(and how it moved by period), a 40,000-path daily Monte Carlo giving the fair
coupon under four volatility and barrier scenarios, sensitivities to
correlation, volatility and barrier, and a backtest of every 1-year window
since 2019. Syz colours and type throughout.

Rebuild with fresh data:

```
pip install yfinance numpy
python3 showcase/fetch_data.py      # writes showcase/data
python3 showcase/compute.py         # writes showcase/data/showcase.json
python3 showcase/render.py          # writes showcase/syz_data_lab.html
```

Illustrative analysis, not a price: flat volatility per name, constant rates,
continuous dividend yield, no issuer credit or fees.
