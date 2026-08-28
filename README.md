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

**The band defines the surprise.** At an earnings announcement, a close that
crosses out through the upper Bollinger band is a positive surprise; through
the lower band, a negative one. A stock can rise on a print and still not leave
its own range — that is not news. Volatility is the yardstick, so the crossing
is the event.

The close must have been inside the band before the print and outside it after
(measured over the reaction window, t-1 → t+1), so a name already riding a band
does not re-fire every quarter. Bands run over `Config.bb_window` = 100 sessions
at ±`Config.bb_sigma` = 2σ — a quarter of trading days, so the dispersion is the
name's inter-earnings volatility rather than the fortnight before the release.

* `SIGNAL = LONG` — closed through the upper band: positive surprise
* `SIGNAL = SHORT` — closed through the lower band: negative surprise
* `SIGNAL = NONE` — stayed inside the band

Standardised Unexpected Earnings is kept as **context, not a condition**:
SIGMA and CATEGORY still say how surprising the fundamentals were (consensus
model, falling back to Foster-Olsen-Shevlin, standardised on the name's own
prior surprises), and `SUE_AGREES` records whether EPS pointed the same way as
the band. Neither gates the signal.

Every announcement that lands on the plotted price calendar is kept, including
the newest print whose reaction window has not closed — its return columns stay
NaN and every mean skips them.

## Reading the chart

Close, the 100-day band and its shaded interior, MA200, and one marker per
print. **Every quarterly report is a light vertical bar** behind the price:
neutral grey where the print stayed inside the band, green where it closed
through the upper band, orange through the lower — so the earnings calendar and
its outcomes read at a glance. Crossings also carry a dated `▲ Positive` /
`▼ Negative` label. Marker symbol and size are the EPS context (direction and
severity of the SUE), not the surprise itself. One tooltip for the point under
the cursor. The y-axis fits the band as well as the price, so the band is never
clipped.

The gallery filters all ask about the **latest print** ("Latest print · major
surprise"): they choose which *names* appear in the result list. The chart
always shows every print in the plotted window — the latest one is ringed in
Space Blue, carries a dashed guide and a `Latest · <category> · <date>` label,
so the print the filter asked about is identifiable without hiding the rest.

Direction is the marker symbol, severity is its size, and an In Line print is
small and grey so the surprises read first. A key strip under the chart names
the whole vocabulary.

## Reading the dashboard

The dashboard measures **Bollinger band crossings that follow an earnings
report**, and nothing else — no EPS, no SUE, no consensus. A report either
moved price out of its own volatility range or it did not, and every panel
describes the two populations that follow.

Controls: window · sector · band crossings only. Four tabs:

* **Signals** — reports, crossings, upper/lower counts with their reactions,
  drift for each direction against the drift of reports that stayed in range,
  and the latest crossings with date, direction, band, close, reaction and drift
* **Breakdown** — crossings by sector and by quarter, mean return by what the
  band did (upper / lower / no cross), the direction split, and the table
  comparing all three groups
* **Detail** — crossings by country and industry
* **Radar** — upcoming reporters with how often each leaves its range, which
  way, and what it paid

SUE stays in the event table as chart context only — the marker symbols in the
gallery — and never reaches these numbers.
