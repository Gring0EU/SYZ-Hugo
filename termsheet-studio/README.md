# Life Syzcle

*Born on a term sheet, raised on coupons.* A structured product's whole
life, from the first quote to the last coupon, with Syz in the middle of it.

`T01_life_syzcle.html` is the Advisory Workbench's Term Sheet module on its
own: one HTML file, opened in the browser, nothing to install.

| Tab | What it does |
|---|---|
| **Term sheet** | Drop a LYNQS or Visibility pricer page (or fill the form): builds the one-glance card. *Copy table* gives the Outlook table (editable after pasting), *Copy image* / *Save image* the PNG. |
| **Fact sheet** | A client-ready product proposal from the Term sheet's quote, with charts from the market-data snapshot in the page. Print to PDF or save as HTML. |
| **Lifecycle events** | Drop the LYNQS product page of a product that ended: autocalled, expired above the strike (event email + rollover), or expired below it (delivery email). Copy the emails into Outlook. |

Every visit starts clean: no sample basket, no coupon, and the last session's
quote and fact sheet settings are not brought back. The date of the market
data is shown top right.

Left out of this page: the Portfolio Screener, the Structured Product Screener
(themes, underlyings, basket lab, optimiser, compare), the Excel export and
the simulator.

## Rebuilding

The page is generated from the workbench's single-file build, so it follows
the workbench when that changes:

```
python3 -I termsheet-studio/build_from_workbench.py path/to/G01_workbench_YYYY-MM-DD.html
```

Every cut the script makes must match exactly once; if the workbench moved
the code, the build stops and names what it could not find.

## Refreshing the market data (Yahoo Finance)

The Fact sheet's charts and figures come from Yahoo Finance data stored in the
page (quotes and daily closes for the ~2,300 Core List symbols). To bring it
to today:

```
pip install yfinance
python3 termsheet-studio/refresh_market_data.py
```

It downloads 13 months of daily bars for every symbol (about 3 minutes),
re-takes the last 10 stored days, appends the new closes, recomputes the
price-based quote fields (price, 52-week range, 1-year change, distance to the
200-day average), and rewrites the page in place. During market hours the
last point is the live price, not a close. Rebuilding from a workbench file
brings back that file's data, so refresh again after a rebuild.
