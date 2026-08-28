# Spread variation since 14 July 2026

`SYZ_Spread_Since_14Jul2026.xlsx` — a clean, **formula-only** workbook (no macro, no VBA)
that shows the spread move of every bond since a fixed anchor date, plus the Bloomberg
company description and reference data.

## Sheets

| Sheet | What it is |
|---|---|
| **Spread Monitor** | One row per bond (763 ISINs). Everything except column A is a formula. Filter/sort with the arrows on row 6. |
| **Top & Bottom** | Top 10 wideners and Top 10 tighteners per currency (USD, EUR, GBP, CHF), pulled live from Spread Monitor. |
| **Company_desc** | Input data — the ISIN → company-description library from the original workbook. |
| **SYZ_static** | Input data — the SYZ-internal fields (SYZ view, Ind LV., Bond Classification, Tax Group, rating) that are not Bloomberg fields. |
| **ReadMe** | Legend and field list, inside the workbook. |

## How it works

`Spread Monitor!B2` holds the anchor date (**14.07.2026**), blue on yellow — the only input
cell. Every "since" column passes it to Bloomberg as `SETTLE_DT`, and the four affected
headers rewrite themselves via `TEXT($B$2,"dd.mm.yyyy")`, so changing that one cell re-bases
the whole analysis.

Columns:

| Col | Source |
|---|---|
| B Company | `PROPER(BDP(ISIN & " Corp","NAME"))` |
| C Company description | `INDEX/MATCH` on Company_desc, falling back to SYZ_static |
| D SYZ view / I Classification | `INDEX/MATCH` on SYZ_static |
| E Sector / F Country / G Ccy / J Structure | `BDP("INDUSTRY_SECTOR")`, `PROPER(BDP("COUNTRY_FULL_NAME"))`, `BDP("CRNCY")`, `BDP("PAYMENT_RANK")` |
| H Rating | SYZ_static lookup, falling back to `BDP("RTG_SP")` |
| K–P | `BDP` for `CPN`, `MATURITY`, `MIN_PIECE`/1000, `PX_LAST`, `YAS_BOND_YLD` (flag 15), `YAS_MOD_DUR` |
| Q Spread today | `BDP("YAS_OAS_SPRD")` |
| R Spread on anchor | `BDP("YAS_OAS_SPRD","SETTLE_DT",$B$2)` |
| S Spread change | `Q − R` (plain subtraction, not a third Bloomberg call) |
| T/U YTW on anchor, YTW change | `BDP("YAS_BOND_YLD",…,"SETTLE_DT",$B$2)` and `O − T` |
| V–Y | Hidden ranking helpers: rank within currency via `COUNTIFS`, with a running `COUNTIFS` tie-break so equal moves never share a rank, and a `ccy|rank` key for the Top & Bottom lookups. |

Every formula is wrapped in `IF($A="","",…)`, so the rows below the last ISIN stay empty
instead of filling with errors. Formulas run to row 850 — paste new ISINs into column A and
they populate themselves.

## Verification

LibreOffice is non-functional in the build container (a three-cell file times out), so the
workbook could not be recalculated the usual way. Instead the logic was checked with the
`formulas` Excel engine on a 90-bond copy with the Bloomberg calls replaced by seeded data
(`verify.py`, `verify2.py`):

- **80/80** ranked rows across 8 blocks matched an independently computed ranking, ties included.
- **360/360** lookup cells (description, SYZ view, classification, rating) matched.
- Rows without an ISIN evaluated to blank in every guarded column.

The `_xll.BDP` values themselves cannot be resolved off a Bloomberg terminal — open the file
with the add-in connected and press Ctrl+Alt+F9.

`build_clean.py` regenerates the workbook from the original `USD.xlsm` data.
