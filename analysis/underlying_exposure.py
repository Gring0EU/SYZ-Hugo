"""Look-through exposure of each underlying in the structured products portfolio.

Each note's weight is split equally across the underlyings of its basket
(equal-split view). The gross view assigns the full note weight to every
underlying, which reflects worst-of risk: any single name can drive the note.

Original weights are on the old portfolio total (EUR 17,498,610); new weights
on the new total (EUR 18,747,986), as in the export.
"""
import re
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).parent
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "export_portfolio.csv"
OUT = HERE / "underlying_exposure.xlsx"
NEW_TOTAL = 18_747_986.00

# Tickers truncated in the export, mapped to the full ticker
ALIASES = {"UB": "UBSG", "SM": "SMI"}

NAMES = {
    "RACE": ("Ferrari", "Single stock"), "CFR": ("Richemont", "Single stock"),
    "RMS": ("Hermes", "Single stock"), "AAPL": ("Apple", "Single stock"),
    "MSFT": ("Microsoft", "Single stock"), "AMZN": ("Amazon", "Single stock"),
    "BABA": ("Alibaba", "Single stock"), "1211": ("BYD", "Single stock"),
    "MELI": ("MercadoLibre", "Single stock"), "BKNG": ("Booking Holdings", "Single stock"),
    "CVX": ("Chevron", "Single stock"), "MCD": ("McDonald's", "Single stock"),
    "HD": ("Home Depot", "Single stock"), "MA": ("Mastercard", "Single stock"),
    "WMT": ("Walmart", "Single stock"), "GEBN": ("Geberit", "Single stock"),
    "GIVN": ("Givaudan", "Single stock"), "SREN": ("Swiss Re", "Single stock"),
    "ASML": ("ASML", "Single stock"), "OR": ("L'Oreal", "Single stock"),
    "DG": ("Vinci", "Single stock"), "ABBN": ("ABB", "Single stock"),
    "NOVN": ("Novartis", "Single stock"), "UBSG": ("UBS Group", "Single stock"),
    "PANW": ("Palo Alto Networks", "Single stock"), "ANET": ("Arista Networks", "Single stock"),
    "APH": ("Amphenol", "Single stock"), "AVGO": ("Broadcom", "Single stock"),
    "META": ("Meta Platforms", "Single stock"), "SPX": ("S&P 500", "Index"),
    "SX5E": ("Euro Stoxx 50", "Index"), "NKY": ("Nikkei 225", "Index"),
    "AIR": ("Airbus", "Single stock"), "HNR1": ("Hannover Re", "Single stock"),
    "LIN": ("Linde", "Single stock"), "UBER": ("Uber", "Single stock"),
    "JPM": ("JPMorgan Chase", "Single stock"), "BKR": ("Baker Hughes", "Single stock"),
    "NVDA": ("Nvidia", "Single stock"), "ROG": ("Roche", "Single stock"),
    "AM": ("Dassault Aviation", "Single stock"), "SAF": ("Safran", "Single stock"),
    "AZN": ("AstraZeneca", "Single stock"), "JNJ": ("Johnson & Johnson", "Single stock"),
    "MCK": ("McKesson", "Single stock"), "RHM": ("Rheinmetall", "Single stock"),
    "RTX": ("RTX", "Single stock"), "HO": ("Thales", "Single stock"),
    "GOOGL": ("Alphabet", "Single stock"), "AI": ("Air Liquide", "Single stock"),
    "MC": ("LVMH", "Single stock"), "DE": ("Deere", "Single stock"),
    "COST": ("Costco", "Single stock"), "KO": ("Coca-Cola", "Single stock"),
    "TSM": ("TSMC", "Single stock"), "LLY": ("Eli Lilly", "Single stock"),
    "MRK": ("Merck & Co", "Single stock"), "GDX": ("VanEck Gold Miners", "ETF"),
    "COPX": ("Global X Copper Miners", "ETF"), "URA": ("Global X Uranium", "ETF"),
    "SU": ("Schneider Electric", "Single stock"), "SIE": ("Siemens", "Single stock"),
    "ENR": ("Siemens Energy", "Single stock"), "RWE": ("RWE", "Single stock"),
    "TTE": ("TotalEnergies", "Single stock"), "CAC": ("CAC 40", "Index"),
    "UKX": ("FTSE 100", "Index"), "NDX": ("Nasdaq 100", "Index"),
    "SMI": ("Swiss Market Index", "Index"), "PG": ("Procter & Gamble", "Single stock"),
    "ZURN": ("Zurich Insurance", "Single stock"), "V": ("Visa", "Single stock"),
    "AMD": ("AMD", "Single stock"), "TXN": ("Texas Instruments", "Single stock"),
    "BNP": ("BNP Paribas", "Single stock"), "GS": ("Goldman Sachs", "Single stock"),
    "MS": ("Morgan Stanley", "Single stock"), "RTY": ("Russell 2000", "Index"),
    "OMX": ("OMX Stockholm 30", "Index"),
}


def basket(description):
    m = re.search(r"%\s+(\S+)\s+\d{2}\.\d{2}\.\d{4}", description)
    return [ALIASES.get(t, t) for t in m.group(1).split("-")]


df = pd.read_csv(SRC)
df.columns = [c.strip() for c in df.columns]
df = df[["Description", "ISIN code", "Currency", "Weight (%)",
         "Valuation + accr. interest (EUR)", "New weight"]].dropna(subset=["Description"])
df = df.rename(columns={"Weight (%)": "orig_w", "Valuation + accr. interest (EUR)": "val"})
df["new_w"] = df["val"] / NEW_TOTAL * 100
df["basket"] = df["Description"].map(basket)
df["n"] = df["basket"].map(len)
orig_total = (df["val"] / df["orig_w"] * 100).median()

rows = df.explode("basket")
agg = rows.assign(
    orig_eq=rows["orig_w"] / rows["n"], new_eq=rows["new_w"] / rows["n"],
    val_eq=rows["val"] / rows["n"],
).groupby("basket").agg(
    notes=("ISIN code", "count"), val_eq=("val_eq", "sum"),
    orig_eq=("orig_eq", "sum"), new_eq=("new_eq", "sum"),
    orig_gross=("orig_w", "sum"), new_gross=("new_w", "sum"),
    in_notes=("Description", lambda s: "; ".join(s)),
)
agg.insert(0, "Name", [NAMES.get(t, (t, "?"))[0] for t in agg.index])
agg.insert(1, "Type", [NAMES.get(t, (t, "?"))[1] for t in agg.index])
agg["chg_eq"] = agg["new_eq"] - agg["orig_eq"]
agg["chg_rel"] = agg["chg_eq"] / agg["orig_eq"] * 100
avg = agg["new_eq"].mean()
agg["vs_avg"] = agg["new_eq"] - avg
agg["position"] = pd.cut(agg["new_eq"] / avg, [0, 0.75, 1.25, float("inf")],
                         labels=["Underweight", "Neutral", "Overweight"])
agg = agg.sort_values("new_eq", ascending=False)
agg.index.name = "Ticker"

out = agg[["Name", "Type", "notes", "val_eq", "orig_eq", "new_eq", "chg_eq",
           "chg_rel", "vs_avg", "position", "orig_gross", "new_gross", "in_notes"]]
out.columns = ["Name", "Type", "# notes", "Look-through EUR", "Original weight %",
               "New weight %", "Change (pp)", "Change (rel %)", "New vs average (pp)",
               "Positioning", "Original gross %", "New gross %", "Held via"]

by_type = out.groupby("Type")[["Look-through EUR", "Original weight %", "New weight %"]].sum()
by_type["Change (pp)"] = by_type["New weight %"] - by_type["Original weight %"]

notes = df.assign(basket=df["basket"].map("-".join))[
    ["Description", "ISIN code", "Currency", "basket", "n", "val", "orig_w", "new_w"]]
notes["chg"] = notes["new_w"] - notes["orig_w"]
notes.columns = ["Description", "ISIN", "Ccy", "Basket", "# underlyings", "Valuation EUR",
                 "Original weight %", "New weight %", "Change (pp)"]

summary = pd.DataFrame({"Metric": [
    "Original portfolio total (EUR, implied)", "New portfolio total (EUR)",
    "Structured products valuation (EUR)", "SP sleeve - original weight %",
    "SP sleeve - new weight %", "Number of notes", "Distinct underlyings",
    "Average new weight per underlying %", "Scaling factor new/original",
    "Top 10 underlyings - new weight %",
], "Value": [
    round(orig_total, 0), NEW_TOTAL, round(df["val"].sum(), 2),
    round(df["orig_w"].sum(), 2), round(df["new_w"].sum(), 2), len(df), len(agg),
    round(avg, 4), round(orig_total / NEW_TOTAL, 4),
    round(agg["new_eq"].head(10).sum(), 2),
]})

with pd.ExcelWriter(OUT, engine="openpyxl") as xw:
    summary.to_excel(xw, sheet_name="Summary", index=False)
    out.round(4).to_excel(xw, sheet_name="Underlying exposure")
    by_type.round(4).to_excel(xw, sheet_name="By type")
    notes.round(4).to_excel(xw, sheet_name="Notes", index=False)
    for ws in xw.book.worksheets:
        for col in ws.columns:
            width = max(len(str(c.value or "")) for c in col)
            ws.column_dimensions[col[0].column_letter].width = min(width + 2, 60)

pd.set_option("display.width", 200)
print(summary.to_string(index=False))
print(by_type.round(3).to_string())
print(out.drop(columns=["Held via", "Type"]).round(3).to_string())
