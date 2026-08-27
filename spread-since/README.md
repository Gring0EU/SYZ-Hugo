# Spread variation since 14 July 2026

Adaptation of the SYZ bond-monitor workbook (`USD.xlsm`) so it produces a
WORST 10 / TOP 10 table of spread moves **since a fixed anchor date** (14.07.2026),
alongside the existing 1-week and 1-month tables.

## Files

| File | What it is |
|---|---|
| `SYZ_Bond_Monitor_USD_spread_since_14Jul2026.xlsm` | The adapted workbook. Existing macros untouched. |
| `SPREAD_SINCE.bas` | New VBA module to import (Alt+F11 → File → Import File…). |
| `build.py` | The openpyxl script that produced the workbook from the original, kept for reproducibility. |

## Workbook changes

- **`Company_desc!D1`** — the anchor date, `14.07.2026`. Blue-on-yellow: it is the only
  cell to edit. `A1`/`A2` stay dynamic (`TODAY()-7`, `TODAY()-30`).
- **`Formulas!Y:AA`** — three new Bloomberg columns driven by `$D$1`:
  - `Y` Spread change since 14.07.2026 — `N − BDP(ISIN & " Corp","YAS_OAS_SPRD","SETTLE_DT",Company_desc!$D$1)`
  - `Z` YTW change since 14.07.2026 — `K − BDP(…,"YAS_BOND_YLD","YAS_YLD_FLAG=15","SETTLE_DT",…$D$1)`
  - `AA` Spread level on 14.07.2026 — `BDP(…,"YAS_OAS_SPRD","SETTLE_DT",…$D$1)`
- **`Formulas!B:U`** — the descriptive columns were empty; they now hold live Bloomberg
  `BDP` formulas (company name, coupon, structure, maturity, country, sector, min piece,
  price, YTW, spread, modified duration, currency) and INDEX/MATCH lookups for the
  SYZ-internal fields (List, Ind LV., Bond Classification, Tax Group, rating) and for the
  company description (`Company_desc!A:C`, falling back to `Sheet1!Q`).
  Every formula is wrapped in `IF($A2="","",…)`, so rows without an ISIN stay blank
  instead of erroring. Rows 2:769 are pre-filled — paste ISINs into column A only.
- **New sheet `Spread - since 14.07.2026`** — filled by the macro.
- **`ReadMe (changes)`** sheet — the same summary inside the workbook.
- **`VBA_SPREAD_SINCE`** (hidden) — the module source as text, in case the `.bas` is lost.

## Macro changes (module `SPREAD_SINCE`, purely additive)

| Procedure | Role |
|---|---|
| `RM_VERSION_WITH_SINCE` | New entry point. Refreshes `Bonds_list_hard`, then runs `Grouping`, `PROCESSTABLEADVANCED`, `TOC`, `AddSinceNavLink`, `MacroSPREADWEEK`, `MacroSPREADMONTH`, `MacroSPREADSINCE`. |
| `ActualiserDonneesBonsFull` | Same as `ActualiserDonneesBons` but copies `A:AA` instead of `A:X`, so `Y/Z/AA` reach `Bonds_list_hard`. |
| `MacroSPREADSINCE` | Builds the new sheet: per currency (USD, EUR, GBP, CHF) a WORST 10 and a TOP 10 table ranked on column `Y`. |
| `AddSinceNavLink` | Adds the 4th link under the "Ranking Sheets" banner on `SpreadRanking`. |

No existing procedure is modified. `MacroSPREADWEEK` / `MacroSPREADMONTH` already append
"column 25 to last column", so the 1-week and 1-month tables pick up the three new columns
as extra context with no change.

## Notes

- The workbook was **not** recalculated offline: every value comes from the Bloomberg
  add-in (`_xll.BDP`), which resolves only on a terminal-connected machine.
- `Formulas!Y1:AA1` spell the date out as static text (Excel table headers cannot hold
  formulas). If `Company_desc!D1` changes, update those three headers.
- The two `UPSLIDE_*` add-in scratch sheets lost their extension-based conditional-format
  rules in the openpyxl round-trip. They hold no data.
