# SYZ-Hugo — earnings-surprise research lab

BQuant (BQL) notebook app that flags earnings surprises across an index, marks
them on the price chart, and reports how the market paid for them.

## Layout

The app is seven notebook cells, one per file in `app/`, run in order in a
BQuant notebook or QuApp:

| Cell | File | What it owns |
| --- | --- | --- |
| 1 | `app/cell1_core.py` | Config, brand theme, BQL client, data store |
| 2 | `app/cell2_ingest.py` | Step 1 — live ingest (constituents, prices, EPS, dates, GICS) |
| 3 | `app/cell3_events.py` | Step 2 — SUE scoring, Bollinger bands, event table |
| 4 | `app/cell4_analytics.py` | Aggregations, catalog and search |
| 5 | `app/cell5_gallery.py` | Step 3 — per-asset chart gallery |
| 6 | `app/cell6_dashboard.py` | Step 4 — index conclusion dashboard |
| 7 | `app/cell7_app.py` | Pipeline orchestration and app shell |

## Signal definition

A print is scored on fundamentals first: Standardised Unexpected Earnings
against consensus, falling back to the Foster-Olsen-Shevlin time-series model,
standardised on that name's own prior surprises only.

A rated surprise becomes a **tradeable signal** only when price confirms it: the
close must cross the Bollinger band during the reaction window (t-1 → t+1),
having been inside the band before the print. Bands are measured over
`Config.bb_window` = 100 sessions at ±`Config.bb_sigma` = 2σ — a quarter of
trading days, so the dispersion is the name's inter-earnings volatility rather
than the fortnight before the release, and a cross is a genuine range break.

* `SIGNAL = LONG` — positive surprise, close broke the upper band
* `SIGNAL = SHORT` — negative surprise, close broke the lower band
* `SIGNAL = DIVERGENT` — surprise confirmed by a break the other way
* `SIGNAL = NONE` — no crossing

The dashboard's band-signal table compares confirmed signals against surprises
that never broke the band, so the filter has to earn its place.
