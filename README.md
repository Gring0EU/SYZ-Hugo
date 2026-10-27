# SYZ-Hugo

| Folder | What it is |
|---|---|
| `workbench/` | The Advisory Workbench (`G01_workbench.html`): Portfolio Screener, Structured Product Screener, Term Sheet module |
| `termsheet-studio/` | Life Syzcle (`T01_life_syzcle.html`): the Term Sheet module on its own, see its README |
| `merle/` | Merle (`B01_app.html`): term sheet PDF file naming and event emails |
| `market-data/` | The Yahoo Finance refresh shared by the workbench and Life Syzcle |

## Market data, refreshed automatically

The workbench and Life Syzcle carry their market data inside the page (quotes
and daily history for ~2,300 symbols, from Yahoo Finance). The GitHub job
`.github/workflows/refresh-market-data.yml` refreshes it with nobody touching it:

| When (Zurich, winter / summer) | What |
|---|---|
| Mon to Fri 06:30 / 07:30 | Prices and daily history: price, 52-week range, 1-year change, 200-day average |
| Mon to Fri 21:45 / 22:45 | The same, after the US close |
| Saturday 05:00 / 06:00 | The same plus fundamentals: P/E, forward P/E, dividend yield, average daily traded value, next earnings date |

The refreshed pages are published on the **`live` branch** (one commit,
replaced at every run, so the repository does not grow):

* `live/workbench/G01_workbench.html`
* `live/termsheet-studio/T01_life_syzcle.html`

Open them from GitHub (switch to the `live` branch, open the file, *Download
raw file*), or turn on GitHub Pages for the `live` branch (Settings → Pages →
Deploy from a branch → `live`, `/ (root)`) to have a fixed address that always
serves the latest data.

The page code, the Core List, themes and stories come from `main`: change a
page on `main` and the next run publishes it with fresh data. The market data
carries on from the last `live` copy. A run where Yahoo returns fewer than 80%
of the symbols fails and publishes nothing, so `live` keeps the last good data;
GitHub e-mails the repository owner when a scheduled run fails.

Run it now: Actions → *Refresh market data* → *Run workflow* (tick
*fundamentals* to include them). By hand, from a checkout:

```
pip install yfinance
python3 market-data/refresh_market_data.py [--fundamentals] [page.html ...]
```
