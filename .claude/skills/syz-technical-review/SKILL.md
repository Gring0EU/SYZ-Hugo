---
name: syz-technical-review
description: "Turns one or more stock tickers or currency pairs (e.g. CHF/EUR, EUR/USD) into one-page SYZ technical review PDFs, in the layout of the SYZ structured-products proposal PDFs, with the SYZ logo. Each page gives a verdict (exit / reduce, neutral / hold within the range, or positive / buy on pullbacks), a short catalyst story on what is driving the stock up or down (written from the latest news), the plan for holders, new money and structured products, a one-year chart with the 50 and 200-day averages, the exit or buy-on-dip zone and the stop level, eight signals in plain English with the technical name in small type, the key levels table, the performance against a benchmark, and a short FinSA-style disclaimer. The aim is to spot opportunities, including exiting a position to avoid further losses. Use when asked for a technical analysis, technical review, chart view, quick comment or one-pager on a stock or a currency pair (e.g. 'technical analysis on Oracle, SYZ one-pager', 'do the same for Booking and Apple', 'do it for CHF/EUR'), or whether to exit, hold, hedge or buy on technical grounds."
---

# SYZ technical review

A bundled pure-Python script loads two years of daily prices, computes the signals, decides the
verdict and draws the page. Your job: get the right tickers, write the catalyst story from the
news, build, check, and hand over. Do not compute indicators, pick levels or write the verdict
yourself; the script does it the same way for every stock. The story is the only text you write.

## When to use

- "Technical analysis on Oracle, SYZ one-pager", "quick comment and technical view on Apple".
- "Do the same for Booking and Apple", "same format for Nestlé".
- "Should we exit X / is there an entry point on Y?" when the answer is a technical one.
- "Do it for CHF/EUR", "technical view on EUR/USD", "should we hedge our CHF?".

Do not use it for: structured product baskets against strike and barrier (`syz-proposal-charts`),
client portfolio reviews, proposals or decks (`syz-portfolio-proposal`), chart slides of a stock inside a
PowerPoint deck (`syz-client-presentations --chart`), or fundamental research.

## Where to run it

| Where | Command |
| --- | --- |
| SYZ Advisory workspace (Claude Code, Windows) | `.\.venv\Scripts\python apps\P02\P02_run.py <TICKER> [<TICKER> ...] [options]` |
| This skill's folder (claude.ai, a Mac, any Python 3.10+) | `python scripts/technical_review.py <TICKER> [...] [options]` |

Standard library only, nothing to install. In the workspace the packaged `scripts/` folder is not
present; use the first command.

Options: `--bench SYMBOL "NAME"` sets the benchmark (default `^GSPC "S&P 500"`). `--name` sets the
display name (one ticker). `--story FILE` adds the catalyst stories (JSON, one per ticker).
`--news` prints the latest headlines per ticker and stops. `--out-dir DIR` (default `data/P02/out`,
or `/mnt/user-data/outputs` on claude.ai). `--offline` uses cached prices. `--open` opens the PDFs
on Windows.

## Instructions

1. **Get the tickers.** Use Yahoo symbols: `AAPL`, `BKNG`, `ORCL`; European and Swiss lines with
   their suffix: `MC.PA`, `ASML.AS`, `SAP.DE`, `NESN.SW`, `ROG.SW`. Turn names into symbols
   yourself ("Booking" is `BKNG`). For a name you are not sure of, say which symbol you used.
   Ask only when a name is ambiguous (several listings, share classes).
2. **Pick the benchmark** from the stock's home market, unless the user names one:

   | Home market | `--bench` |
   | --- | --- |
   | US (default) | `^GSPC "S&P 500"` |
   | Eurozone | `^STOXX50E "Euro Stoxx 50"` |
   | Switzerland | `^SSMI "SMI"` |
   | UK | `^FTSE "FTSE 100"` |

   Build stocks with different benchmarks in separate runs.

   **Currency pairs** work too: `CHFEUR=X` (EUR per CHF), `EURCHF=X`, `EURUSD=X`, `USDCHF=X`. Use
   the quote the user wrote ("CHF/EUR" is `CHFEUR=X`). The page switches to FX mode by itself: six
   signals (no volume, no benchmark), 4-decimal levels, "Long CHF / Buying CHF" lines and an
   FX-linked-notes line. `--news` returns nothing for pairs: research the story on the web
   (central banks, rate differentials, safe-haven flows, intervention).
3. **Write the catalysts** ("What's driving it", first line of the verdict box):
   - Run `python scripts/technical_review.py BKNG AAPL --news` for the latest headlines, and search
     the web for what explains the bigger moves (the year, the last month).
   - Per stock, two or three sentences, about 300 characters: what has driven the stock up or down
     (results, guidance, products, regulation, deals, sector themes), with dates, then the next
     catalyst (results date, investor day). Facts from the news only, never from memory; no source
     names, no "we recommend". Keep the numbers consistent with the page (performance, P/E).
     See [references/catalysts.md](references/catalysts.md) for the pattern and examples.
   - Save them as JSON, e.g. `stories.json`: `{"BKNG": "...", "AAPL": "..."}` (in the workspace:
     `data/P02/in/stories_<date>.json`). Without a story the box shows a mechanical "Why" line instead.
4. **Build:**
   ```bash
   python scripts/technical_review.py BKNG AAPL --story stories.json
   ```
   Each stock prints `Wrote <file>`, a summary line (verdict, signal count, zone, stop, results
   date) and the four plan lines. A `WARNING <ticker>` line means that stock failed (unknown
   symbol, or less than about 18 months of prices): fix the symbol or report it.
5. **Check the output** against the printed lines:
   - The verdict fits the signals (exit with mostly negative signals, positive with mostly positive).
   - The levels are on the right side of the price (exit zone above it, stop below it).
   - The results date is in the future; it is an estimate, so flag it when it is within a few weeks.
   - Read [references/signals.md](references/signals.md) when a verdict looks surprising.
6. **Hand over**, written for the advisor:
   - Link the PDFs.
   - Per stock, three or four lines: the verdict and signal count, the catalysts in one line, the
     action for holders and for new money with the levels, and the structured-products line.
   - List the news sources you used for the catalysts (links), for the advisor, not on the page.
   - Say the results dates are estimates, and that compliance should validate the disclaimer
     before anything goes to clients.

## Output

`P02_technical_<TICKER>_<date>.pdf`, A4 portrait, one page:
title and signal, five headline figures, the verdict box (what's driving it, holders, new money,
structured products), the one-year chart, signals and levels side by side, performance against the
benchmark, then the "Important information" disclaimer and the SYZ footer.

## Rules

- Prices come from the script's market data; every number on the page is calculated by it. Never
  type a price or a level in, and never edit the PDF by hand.
- The page names no data vendor ("market data providers"), and the disclaimer stays. Do not
  present the page as a recommendation, a forecast or research; it is a technical reading.
- No client names, account numbers or holdings on the page, in file names or in the hand-over.
- One page per stock. If the user asks for wording or layout changes, change `apps/P02/P02_run.py`
  (layout) or `src/syz_advisory/technicals.py` (signals, verdict, wording), run the tests, rebuild.

## Example

**Input:** "Technical review for Booking and Apple, same SYZ format."

**Steps:** `--news BKNG AAPL`, a web search on each stock's year, `stories.json` written, then
`BKNG AAPL --story stories.json`.

**Output:** The two PDFs are linked (`P02_technical_BKNG_<date>.pdf`, `P02_technical_AAPL_<date>.pdf`). Then:

> **Booking: neutral, hold within the range** (2 positive, 3 negative signals). Down 24% this year on
> fears that AI agents squeeze online travel agencies; EU probe into fake listings on 21.10. Holders:
> hold above USD 154.06 (-4.4%); a close above 168 (+5%) turns it positive. Results on 03.11
> (estimated) can break the range.
>
> **Apple: positive, buy on pullbacks** (8 of 8). Record high on iPhone Duo demand and Siri AI;
> buy dips into USD 329–339, stop USD 325.81. The average analyst target (USD 328) is below the price.
>
> Sources for the catalysts: (links to the articles used).

**Input:** "Do it for CHF/EUR."

**Steps:** web search on the franc (SNB, ECB, safe-haven flows), `stories_fx.json` with the key
`CHFEUR=X`, then `CHFEUR=X --story stories_fx.json`.

**Output:** `P02_technical_CHFEUR_<date>.pdf` is linked. Then:

> **CHF/EUR: CHF in an uptrend, add on pullbacks** (4 of 6 signals; the 50-day is still below the
> 200-day). The franc recovered its September dip as European debt worries revived demand; the SNB
> holds at 0%. Long CHF: keep, stop EUR 1.0542 (-2.8%). Buying CHF: on dips into 1.0777–1.0826.
> Vol ~4.7%: thin coupons on FX-linked notes.

## Additional resources

- [references/signals.md](references/signals.md): how each signal, the verdict, the zones and the
  stop are decided, and how to explain them to a client. Read before answering "why is it exit?"
  or when a verdict looks wrong.
- [references/catalysts.md](references/catalysts.md): how to research and write the "What's
  driving it" story, with examples. Read before writing the stories.
