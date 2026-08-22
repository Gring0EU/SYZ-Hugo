# Yahoo list — UCITS / accumulating screen and AUM ranking

Scope: only the **Yahoo sleeve** (`source = extra`, 204 rows) was touched.
The **Thematic** (`source = thematic`, 54 rows) and **Selection**
(`source = ucits`, 97 rows) sleeves are passed through byte-identical.

## Result

| | rows |
|---|---|
| Yahoo list in | 204 |
| removed — non-UCITS | 8 |
| removed — duplicate / near-duplicate | 75 |
| **Yahoo list out** | **121** |

## Files

- `yahoo_list.csv` — the screened list, ranked by AUM descending.
- `yahoo_list_removed.csv` — every removed line with its reason and the
  ticker kept in its place.
- `panel_curated.csv` — full panel: curated Yahoo sleeve + the two
  untouched sleeves (272 rows).
- `build_yahoo_list.py` — reproduces all three from `panel_355_funds.csv`.

## Method

**UCITS.** Every surviving line is a UCITS fund domiciled in Ireland,
Luxembourg, France or Germany and listed on a European venue (London,
Xetra, Paris, Milan, Amsterdam, SIX). Eight lines are physically-backed
**ETCs** — debt securities, not UCITS funds, with no diversification rules
and no Acc/Dist share-class split — so they fail the screen: `SGLD.SW`,
`SGLE.MI`, `SGLN.L`, `EGLN.L`, `SSLN.L`, `4GLD.DE`, `XGDU.DE`, `XAD6.MI`.
That removes all precious-metals exposure from the Yahoo sleeve. Gold is a
legitimate sleeve and these are the standard instruments for it — if you
want it back, the decision to make is "ETCs allowed", not "these tickers
are wrong". `SGLD.SW` at ~USD 32.5bn is the one to re-add.

**Accumulating.** Confirmed share-class by share-class from the fund name
(`Acc`, `1C`, `2C`, `-C`, `Cap`) and, where the name was silent, from the
issuer or justETF: `HEMC.L`, `EMGB.L`, `FGBL.PA`, `ERNA.L`, `DTLA.L`,
`EUNA.DE`. No distributing share class survives in the list.

**Duplicates.** Collapsed in two passes, keeping the larger line:
*same fund* (a second listing or currency line of one share class — e.g.
`XDWT.DE`/`XDWT.SW`, `SMGB.L`/`SMHV.SW`, `2B79.DE`/`DGIT.L`/`DGTL.L`), then
*same exposure* (different fund, materially the same bet — e.g. four broad
EM trackers collapsed to `XMMS.L`, five developed-world trackers to
`XDWD.L`). Currency-**hedged** share classes were deliberately kept as
distinct exposures rather than folded away, flagged in the
`currency_hedged_of` column: `C099.DE`, `PSPH.PA`, `XSXE.DE`, `EUNA.DE`.

## Data caveats

`aum_usd_m` in the source file is **not** consistently USD — it is the raw
Yahoo `netAssets` in each line's own currency (`SMGB.L` 8053.4 is GBP,
`MEUD.PA` is EUR). The ranking is therefore indicative at the margin;
adjacent lines within ~30% of each other should not be read as strictly
ordered.

22 lines had no AUM at all, including the two largest funds in the sleeve.
These were filled from issuer factsheets and justETF (August 2026) and
converted at EUR/USD 1.17, and are marked `estimated` in the `aum_source`
column. Everything else is marked `yahoo` and is unchanged from the input.

## Other things worth knowing

- **Miscategorised:** `GDIG.L` was filed under Technology & Cybersecurity;
  it is VanEck S&P Global Mining (removed as a duplicate of `GIGB.L`).
  `CSNDX.SW` was filed under Emerging Markets; it is the iShares Nasdaq 100
  (removed as a duplicate of `CNDX.L`).
- **40 lines** arrived with the ticker in the name field; all were resolved
  and the real names written back.
- **Cross-sleeve overlap** was left alone. Several kept Yahoo lines
  duplicate a Thematic or Selection line (e.g. `BATT.L` vs thematic
  `VOLT.L`, `CSBGU7.SW` vs Selection `CBU7.L`, `SJPA.L` vs Selection
  `IJPA.L`). Resolving those means editing the other two lists, which was
  out of scope.
- **Sub-scale:** 11 kept lines are under USD 300m — thin for a live panel
  but none breach the stated screen, so they were kept.
