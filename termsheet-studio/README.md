# Term Sheet Studio

`T01_termsheet_studio.html` is the Advisory Workbench's Term Sheet module on its
own: one HTML file, opened in the browser, nothing to install.

| Tab | What it does |
|---|---|
| **Term sheet** | Drop a LYNQS or Visibility pricer page (or fill the form): builds the one-glance card. *Copy table* gives the Outlook table (editable after pasting), *Copy image* / *Save image* the PNG. |
| **Fact sheet** | A client-ready product proposal from the Term sheet's quote, with charts from the market-data snapshot in the page. Print to PDF or save as HTML. |
| **Lifecycle events** | Drop the LYNQS product page of a product that ended: autocalled, expired above the strike (event email + rollover), or expired below it (delivery email). Copy the emails into Outlook. |

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
