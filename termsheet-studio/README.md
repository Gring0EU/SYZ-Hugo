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

How Lifecycle events decides between case 2 (100% back) and case 3 (delivery) at the final fixing:
**delivery only when the worst underlying ends below its strike AND, on a barrier product, the
barrier was hit**. A price below the barrier counts as a hit (European or American); the page's
"Barrier Hit" flag covers an American barrier touched during the life. What the page states
("Cash Redemption", or shares to deliver) wins, and the prices cross-check it: any mismatch, or a
case the page and prices cannot settle, is flagged before the email is sent. The rule lives in
`event_fix.py`, applied by the build.

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
page (quotes and daily closes for the ~2,300 Core List symbols). A scheduled
GitHub job refreshes it every weekday, see the repository README. To refresh a
copy by hand:

```
pip install yfinance
python3 market-data/refresh_market_data.py termsheet-studio/T01_life_syzcle.html
```

Rebuilding from a workbench file brings back that file's data, so refresh
again after a rebuild.
