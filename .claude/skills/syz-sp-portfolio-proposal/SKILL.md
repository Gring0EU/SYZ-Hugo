---
name: syz-sp-portfolio-proposal
description: Builds the SYZ full structured-products portfolio proposal, the 14-page client PDF "Thematic structured products portfolio" (cover, executive summary and KPIs, portfolio table, distance to protection, principles and theme families, three basket cards per page with one-year chart, volatility, correlation, analyst upside, worst low against protection and swap test, income and stress at maturity, issuer concentration, important information, closing page). Reads any mix of inputs - an Excel or CSV proposal sheet, term sheets in PDF, pricer or product pages in HTML - extracts the terms, matches names to tickers, fills missing data from Yahoo Finance and calculates every figure. Use when asked for a structured products portfolio proposal, an SP proposal deck or presentation, a thematic SP portfolio, to recreate or update the portfolio proposal, or to turn Proposal.xlsx, term sheets or pricer pages into the SYZ presentation.
---

# SYZ structured products full portfolio proposal

A bundled Python tool turns the product documents into the SYZ client deck. Your job: gather the
inputs, run the tool, check what it extracted and matched, write the words where it could not, and
hand over. Never type a figure into the deck yourself: every number comes from the documents or is
calculated by the tool.

## When to use

- "Make the portfolio proposal from Proposal.xlsx", "update the SP proposal with today's prices".
- "Build the presentation from these three term sheets", "turn these pricer pages into our deck".
- "Recreate the thematic structured products portfolio for the client", "same deck, new baskets".

Do not use it for: a single stock or currency view (`syz-technical-review`), charts of baskets
against strike and barrier only (`syz-proposal-charts`), a PowerPoint review of products a client
already holds (`syz-client-presentations`), the weekly market documents.

## Where to run it

| Where | Command |
| --- | --- |
| Claude Code, in this repository | `python .claude/skills/syz-sp-portfolio-proposal/scripts/build_deck.py <inputs> [options]` |
| Claude Code on Windows | `.\.venv\Scripts\python .claude\skills\syz-sp-portfolio-proposal\scripts\build_deck.py <inputs>` |
| claude.ai (skill uploaded) | `python scripts/build_deck.py /mnt/user-data/uploads/<file> [options]` from the skill folder |

Dependencies: `pip install -r scripts/requirements.txt` (yfinance, openpyxl, pdfplumber,
beautifulsoup4, lxml, pypdf). The PDF is printed by Playwright when installed, otherwise by Chrome or
Edge in headless mode. If none is found the tool stops with a clear message and the HTML is still
written; say so and hand over the HTML.

Options: `--asof YYYY-MM-DD` prices as of a past date (default today). `--story FILE` the words.
`--tickers FILE` checked symbols. `--out FILE` the PDF (default `/mnt/user-data/outputs` on
claude.ai, `./out` elsewhere). `--stop-after 4` extraction only. `--products FILE` rebuild from a
corrected extraction. `--offline` cached prices. `--no-swap` skip the swap test.

## Instructions

1. **Collect the inputs.** Take every file the user gave: proposal sheet (`.xlsx`, `.csv`), term
   sheets (`.pdf`), pricer pages (`.html`). Formats can be mixed. If the user only typed the baskets,
   write a CSV in the sheet format of [references/inputs.md](references/inputs.md).
2. **Anonymise.** No client name, account number, address or amount in the inputs, the story file
   or the file names. Remove a `Size` column with amounts if the deck is for a client; weights stay.
3. **Extract and check first** when the inputs are term sheets or pricer pages:
   ```bash
   python scripts/build_deck.py TS1.pdf pricer.html --stop-after 4
   ```
   Read every `NAME -> SYMBOL (how)` line and every `missing` line. Fix a wrong symbol with a
   `--tickers` file, or correct a field in the printed `*_products.json` and rebuild with
   `--products`. A product with no coupon stops there: ask for it, never estimate it.
4. **Choose the words.** `assets/stories/thematic_proposal.json` holds the October 2026 proposal
   (18 products) and is used automatically when it covers the products. For other baskets, copy it,
   write a theme and a one-line thesis per product and the theme families, and pass `--story`.
   Without a story the tool writes plain themes and lists the products to complete. Rules in
   [references/story-file.md](references/story-file.md).
5. **Build:**
   ```bash
   python scripts/build_deck.py Proposal.xlsx --story story.json
   ```
   The console prints the eight steps, the output paths and a "Check before sending" list.
6. **Review** against [references/review.md](references/review.md): the KPIs, every product whose
   weakest name's one-year low was at or below its protection, the swap-test suggestions, auto-written
   themes, symbols matched by Yahoo search. Look at the pages when you can (render page images).
7. **Hand over:** link the PDF; one line on the inputs used and the price date; the open points from
   the review; and that compliance must validate the deck before it goes to a client.

## Output

`SYZ_proposal_<date>.pdf`, A4 portrait, 14 pages for 18 products (three basket cards per page), plus
the HTML it was printed from and `SYZ_proposal_<date>_products.json` with every extracted term and
its source. The layout, fonts (Nunito Sans), palette, vector logo, cover photograph and closing page
are fixed in `assets/`; equal 14 mm margins on every page.

## Rules

- Coupons, strikes, barriers, step-downs, issuers and weights come from the inputs. Prices, vol,
  correlation, lows, upside, swap test, KPIs and stress are calculated. Nothing else is typed in.
- Levels assume a strike at today's close for new products; products already struck are placed at
  their term-sheet initial levels. The deck says which; keep those notes and the disclaimer.
- The story file holds words only. Numbers in principles are placeholders filled by the tool.
- Never edit the PDF by hand: change the inputs or the story and rebuild.

## Example

**Input:** "Update the structured products portfolio proposal with today's prices." with
`Proposal.xlsx` (18 products and a cash line).

**Steps:** `python scripts/build_deck.py Proposal.xlsx`; the story file covers the 18 products;
every name matched from the built-in table; review of the console list.

**Output:** `SYZ_proposal_2026-11-04.pdf` is linked. Then:

> 18 products, 7.53% average coupon on the invested part (7.00% with cash), 20% on indices, 33%
> average fall to protection; prices as of 04.11.2026.
> One-year lows at or below protection: products 3 (Microsoft 68% vs 72%), 6 (VAT 56% vs 69%),
> 7 (Palo Alto 40% vs 62%), 12, 14, 15, 18.
> Swap test, alternatives worth pricing: Merck for McKesson (14), Richemont for Ferrari (17).
> Compliance should validate the deck before it goes to the client.

## Additional resources

- [references/inputs.md](references/inputs.md): the sheet columns, what is read from term sheets and
  pricer pages, the tickers file and the products file. Read when an input does not parse or a field
  is missing.
- [references/story-file.md](references/story-file.md): the story file format, placeholders and
  writing rules. Read before writing words for new baskets.
- [references/review.md](references/review.md): what each figure means, how it is calculated, the
  review list and the hand-over. Read before handing over or when asked how a figure is made.
