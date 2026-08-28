# Spread variation since 14 July 2026 — USD and EUR lists

`Spread_Variation_USD_EUR_since_14Jul2026.xlsx` — one sheet, two tables, all Bloomberg
formulas. No macro.

Scope is exactly the two lists supplied: **18 USD bonds** and **47 EUR bonds**.

## Layout

| | |
|---|---|
| `B2` | Anchor date, **14.07.2026** — blue on yellow, the only input cell. Both tables pass it to Bloomberg as `SETTLE_DT`; the two section titles restate it via `TEXT($B$2,"dd.mm.yyyy")`. |
| `tblUSD` (rows 6–30) | The 18 USD ISINs + 6 spare rows. |
| `tblEUR` (rows 44–97) | The 47 EUR ISINs + 6 spare rows. |
| Summary under each table | Bonds priced, average and median spread change, wider/tighter split, and the biggest widener and tightener with the issuer name. |

Both are real Excel tables, so each has its own filter arrows and can be sorted
independently. Spare rows are live: paste an ISIN into column A and the row fills itself.

## Columns

| Col | Formula |
|---|---|
| B Security | `BDP(ISIN & " Corp","SECURITY_DES")` |
| C Company | `PROPER(BDP("NAME"))` |
| D Company description | `BDP("CIE_DES")` |
| E / F Sector, Industry group | `BDP("INDUSTRY_SECTOR")` / `BDP("INDUSTRY_GROUP")` |
| G Country | `PROPER(BDP("COUNTRY_FULL_NAME"))` |
| H Ccy | `BDP("CRNCY")` |
| I Rating (comp.) | `BDP("BB_COMPOSITE")`, falling back to `BDP("RTG_SP")` |
| J Structure | `BDP("PAYMENT_RANK")` |
| K / L Coupon, Maturity | `BDP("CPN")` / `BDP("MATURITY")` |
| M Den. (k) | `BDP("MIN_PIECE")/1000` |
| N Price | `BDP("PX_LAST")` |
| O YTW (%) | `BDP("YAS_BOND_YLD","YAS_YLD_FLAG=15")` |
| P Mod. dur. | `BDP("YAS_MOD_DUR")` |
| Q Spread today (bp) | `BDP("YAS_OAS_SPRD")` |
| R Spread @ anchor (bp) | `BDP("YAS_OAS_SPRD","SETTLE_DT",$B$2)` |
| **S Spread change (bp)** | `Q − R` — red when wider, green when tighter |
| T YTW @ anchor (%) | `BDP("YAS_BOND_YLD","YAS_YLD_FLAG=15","SETTLE_DT",$B$2)` |
| U YTW change (%) | `O − T` |

Every formula is wrapped in `IF($A="","",…)` so spare rows stay blank. The two change
columns are subtractions of the visible columns, not extra Bloomberg calls, so the three
numbers on a row always agree.

## Notes

- Open with the Bloomberg add-in connected and press **Ctrl+Alt+F9**. `_xll.BDP` resolves
  only on a terminal, so the cells read blank until then.
- The `"since"` columns are headed `@ anchor` rather than a spelled-out date: an Excel table
  header cannot hold a formula, so this way nothing goes stale when you change `B2`.
- `CIE_DES` and `BB_COMPOSITE` are not populated for every issuer; both are wrapped in
  `IFERROR` so one missing field cannot blank a row.
- Only 1 of these 65 ISINs appears in the description library from the old workbook, so the
  descriptions come from Bloomberg rather than that lookup.

## Verification

LibreOffice is non-functional in the build container, so the workbook could not be
recalculated the usual way. `verify_two.py` instead evaluates it with the `formulas` Excel
engine on a copy with the Bloomberg calls replaced by seeded numbers: both summary blocks —
counts, average, median, wider/tighter split, max/min and the two `INDEX/MATCH` "which bond"
lines — matched an independent computation, and every spare row evaluated blank.
The ISINs in the file were diffed against the supplied lists: exact match, in order.

`build_two.py` regenerates the workbook from `lists.json`.
