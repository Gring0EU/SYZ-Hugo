# How the page decides

All of this is computed by `src/syz_advisory/technicals.py` from two years of daily closes. Prices
are plain closes, not dividend-adjusted, so the levels match the quoted prices.

## The eight signals

Each signal is Positive, Neutral or Negative. The page shows the plain name, with the technical
name in small type after it.

| Plain name | Technical | Positive | Negative | Otherwise |
| --- | --- | --- | --- | --- |
| Long-term direction | 200-day average | price above it and the average rising (vs 20 sessions ago) | price below and the average falling | Neutral |
| Medium-term direction | 50-day average | above and rising (vs 10 sessions ago) | below and falling | Neutral |
| Short-term direction | 20-day average | more than 1% above | more than 1% below | Neutral ("at the average") |
| Trend structure | 50/200-day cross | 50-day above the 200-day | 50-day below | – |
| Momentum | MACD 12/26/9 | MACD above its signal line | below | – |
| Buying / selling pressure | RSI 14 (Wilder) | 55 to 70 ("firm") | never | below 55, or 70+ ("overbought") |
| Strength vs the market | 1-month return vs the benchmark | more than +2 pts | less than -2 pts | Neutral |
| Buyers' / sellers' conviction | last day's volume vs the 20-day average | 1.15x or more on an up day | 1.15x or more on a down day | Neutral |

RSI is never Negative on purpose: a weak RSI on its own says little, and an oversold one often
precedes a rebound.

## The verdict

Net score = positives minus negatives.

| Net score | Verdict | Shaded zone on the chart |
| --- | --- | --- |
| -3 or lower | **Exit / reduce**, preferably into a rebound | Exit zone: from the nearest resistance up to the latest swing high above the price |
| -2 to +2 | **Neutral / hold within the range** | Range: from the stop level to the latest swing high above the price (the breakout level) |
| +3 or higher | **Positive / buy on pullbacks** | Buy-on-dip zone: between the 20 and 50-day averages (not below the stop) |

## Levels

- **Swing high / low:** the highest high or lowest low over 11 sessions (5 each side), last 6 months.
- **Stop level:** the most recent swing low below the price. When it is also the 2-year low the
  page says so: below it there is no support in two years of history.
- **Resistances:** the nearest three levels above the price among swing highs (within +30%) and the
  20/50/200-day averages. Supports: the nearest two below, plus the stop. Levels within 1.5% of
  each other count once (the average's name wins).
- **Daily range:** ATR 14 days, in price and as a % of the price.

## Structured products line

- Suggested protection (strike or barrier): 60% or lower for exit, 65% for neutral, 70% for positive.
- Coupons from 3-month realised vol: 40%+ "high", 28–40% "decent", below 28% "low on its own;
  better in a basket".
- "After the results" is added when the estimated results date is within 75 days.

## Currency pairs

Detected from the quote type (e.g. `CHFEUR=X`). The reading is from the base currency's side (CHF
in CHF/EUR: a rising rate means a stronger franc).

- Six signals: the first six above. Volume (FX has none) and strength vs the market (no index to
  compare a currency with) are left out. The verdict thresholds stay at -3 / +3.
- Smaller moves: "at the average" within ±0.3% (not ±1%); levels within 0.3% count once (not 1.5%);
  gaps shown to one decimal, levels to four.
- Plan lines: "Long <base>" (keep / hedge) and "Buying <base>"; in the exit case the zone is a
  "Hedge zone". Structured products: FX-linked notes (dual-currency deposits), coupons from 3-month
  vol (10%+ decent, 6–10% modest, below 6% thin), conversion level beyond the stop.
- No benchmark row in the performance table, no results date.

## Explaining it to a client

- It is a reading of the price trend, not a forecast and not a recommendation (the disclaimer says
  so). Valuation and the analyst target are shown for context only.
- "Exit / reduce" means the trend is down on most measures. The page suggests reducing into
  rebounds rather than selling at support, and a level below which there is no reason to wait.
- "Neutral" means the stock is in a range. The two edges of the range are the decision points.
- "Positive" means the trend is up. The page suggests waiting for pullbacks rather than buying at
  the high, with a stop that moves up as new swing lows form.
