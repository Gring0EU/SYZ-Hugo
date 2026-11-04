# Proposal deck: documents in, SYZ presentation out

Rebuilds the **Thematic structured products portfolio** presentation (the 14-page compact deck:
cover, executive summary, portfolio table, distance to protection, thematic rationale, basket cards,
income and stress, important information, closing page) from whatever describes the products:

| Input | Example | What is read |
| --- | --- | --- |
| Proposal sheet, Excel or CSV | `Proposal.xlsx` | one row per product: underlyings, coupon, protection, maturity, weight, step-down, issuer (+ currency, ISIN, fixing dates, theme if the columns exist) |
| Term sheet / final terms, PDF | `CH1601886398.pdf` | ISIN, issuer, currency, coupon, strike, barrier and its type, autocall levels, initial / final fixing and redemption dates, underlyings with Bloomberg tickers and initial levels |
| Pricer or product page, HTML | a saved LYNQS / Visibility / issuer page | the same fields, from the page's labels and tables |

Formats can be mixed in one run: a sheet for the proposal and term sheets for products already bought,
or three pricer pages for a new idea.

## Install (once)

```bash
pip install -r proposal-deck/requirements.txt
```

The PDF is printed by a browser engine: Playwright if installed (`pip install playwright` then
`playwright install chromium`), otherwise Chrome or Edge in headless mode (always there on Windows).

## Run

```bash
# the 18-product proposal, priced today
python proposal-deck/build_deck.py Proposal.xlsx

# the same, priced as of a past date (to reproduce a deck already sent)
python proposal-deck/build_deck.py Proposal.xlsx --asof 2026-10-21

# a new idea from term sheets and pricer pages
python proposal-deck/build_deck.py TS_rare_earths.pdf pricer_tech.html pricer_swiss.html

# check the extraction first, correct it, then build from the corrected file
python proposal-deck/build_deck.py TS_*.pdf --stop-after 4
python proposal-deck/build_deck.py --products out/SYZ_proposal_<date>_products.json
```

Windows (workspace): `.\.venv\Scripts\python proposal-deck\build_deck.py data\G01\in\Proposal.xlsx`.

Output in `proposal-deck/out/` (or `--out`): the PDF, the HTML it was printed from, and
`*_products.json` with every extracted term and where it came from.

## What happens, step by step

The console prints each step, so you can see what was understood and what was assumed.

1. **Recognise each document**: sheet, term sheet (PDF) or pricer page (HTML), by its format.
2. **Extract the terms**: underlyings, strike, barrier (European or American), coupon, step-down,
   initial and final fixing dates, maturity, issuer, currency, ISIN. PDFs and HTML pages go through
   the same parser, so a field is read the same way from both.
3. **Match each name to a Yahoo symbol**, in this order: `--tickers` file, the Bloomberg code in the
   document (`NVDA UW` → `NVDA`, `NESN SW` → `NESN.SW`), the built-in table (indices and the
   names the desk writes most), the Core List (`data/core_list.csv`), Yahoo search. Every match is
   printed with how it was found; a Yahoo-search match says "confirm".
4. **Fill the gaps with market data** (Yahoo Finance via yfinance): long names, currencies,
   the initial level of a product already struck (close on its initial fixing date) when the
   document does not give it, the tenor from the fixing dates. An issuer that is not given is shown
   as TBD. **A coupon is never estimated**: a product without one is flagged.
5. **Analyse**: one year of closes rebased to 100 today; one-year volatility; correlation, average
   and weakest pair (daily returns, weekly when a basket mixes regions, because markets close at
   different hours); each name's lowest close against the protection; fall to protection; the
   analysts' target upside; the reading of the basket; the swap test against the Core List names of
   the same theme (it suggests a name only when it clearly improves the weakest correlation and is
   not already in the proposal); the portfolio KPIs, theme weights, issuer concentration and the
   symmetric stress at maturity.
6. **Write the words**: from the story file (`--story`, see below). Products it does not cover get
   a theme from the sheet's Theme column, the Core List or the Yahoo sector, and a plain thesis
   naming the basket; the console lists them so the advisor can write the words.
7. **Draw the pages**: one A4 HTML document in the SYZ layout (Nunito Sans, the house palette, the
   cover photograph and logo), with vector charts.
8. **Print the PDF** and append the SYZ closing page.

Then the console lists what to check before sending: the KPIs, every product whose weakest name's
one-year low was at or below its protection, and the swap-test suggestions.

## The story file

`stories/thematic_proposal.json` holds the words of the October 2026 proposal: title, objective,
theme families and, per product, a theme name and a one-line thesis. It is used automatically when
it covers the products. For another proposal, copy it and change the words. Numbers never go in it:
the six principles use placeholders that are filled from the analysis (`{index_weight}`, `{cash}`,
`{max_issuer}`...), so the text stays true when the products change. Principles that do not apply
(no index basket, no cash) are left out, and the title counts what remains.

## Levels and what they mean

- **New products** (no fixing yet): levels assume a strike at today's close, as in the original deck.
- **Products already struck** (a term sheet with initial fixing levels): the protection is placed at
  its real price level, shown as a share of today's price, for the name closest to it. A basket
  already below its strike shows "below" in pink.
- Prices are daily closes, not adjusted for dividends (the levels a product observes). Chart lows
  are history, not a backtest or a forecast; the deck says so.

## Files

| Path | Role |
| --- | --- |
| `build_deck.py` | the command, steps 1 to 8 |
| `syzdeck/ingest.py` | recognising documents, reading sheets, the term-sheet parser |
| `syzdeck/names.py` | names, Bloomberg codes, issuers, the Core List |
| `syzdeck/market.py` | symbols, prices, profiles, filling the gaps (cached in `out/.market_cache.json`) |
| `syzdeck/analytics.py` | every calculated figure |
| `syzdeck/story.py` | the words and the principles |
| `syzdeck/render.py`, `syzdeck/charts.py` | the pages and charts |
| `syzdeck/pdf.py` | printing and the closing page |
| `assets/` | cover photograph, logo, fonts, closing page |
| `samples/` | a fictional four-product sheet and a tickers file to try the tool |

Compliance should validate the deck before it goes to a client. No client name, account number or
amount belongs in the inputs, the story file or the file names.
