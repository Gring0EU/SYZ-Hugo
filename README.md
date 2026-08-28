# SYZ-Hugo — earnings-surprise research lab

BQuant (BQL) notebook app that flags earnings surprises across an index,
confirms them technically against a Bollinger band, and reports how the market
paid for them.

## Cells

Run in order in a BQuant notebook or QuApp. The long cells are split in two so
a copy-paste that loses its tail fails loudly instead of silently.

| Cell | File | What it owns |
| --- | --- | --- |
| 1 | `app/cell1_core.py` | Config, brand theme, BQL client, data store |
| 2 | `app/cell2_ingest.py` | Step 1 — live ingest (constituents, prices, EPS, dates, GICS) |
| 3 | `app/cell3_events.py` | Step 2 — SUE scoring, Bollinger bands, band signal, event table |
| 4 | `app/cell4_analytics.py` | Aggregations, catalog and search |
| 5 | `app/cell5_gallery.py` | Step 3 — per-asset chart gallery |
| 6 | `app/cell6_dashboard.py` | Step 4 — cards, tables, figures |
| 6b | `app/cell6b_dashboard_ui.py` | Step 4 — tabbed panel with window/sector/signal controls |
| 7 | `app/cell7_app.py` | Pipeline orchestration and app shell |

`app/cell3b_keep_all_prints.py` is a paste-in patch for a running session on an
older Cell 3; it is already folded into `cell3_events.py`.

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

Every announcement that lands on the plotted price calendar is kept, including
the newest print whose reaction window has not closed — its return columns stay
NaN and every mean skips them.

## Reading the chart

Close, the 100-day band and its shaded interior, MA200, and one marker per
print coloured by surprise severity — the same six traces the chart has always
had. A signalled print is emphasis on its own marker: a thick coloured outline,
a solid coloured guide on the announcement date, and a dated label. The y-axis
fits the band as well as the price, so the band is never clipped.

## Reading the dashboard

Controls: window · sector · band-confirmed signals only. Four tabs:

* **Signals** — KPI strip and the latest band-confirmed signals
* **Breakdown** — sector/quarter/drift figure, per-category table, and the
  signal table comparing confirmed signals against surprises that never broke
  the band
* **Detail** — country and industry
* **Radar** — upcoming reporters and their history
