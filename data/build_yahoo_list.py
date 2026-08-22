#!/usr/bin/env python3
"""Curate the Yahoo (source='extra') sleeve of the fund panel.

Steps: (1) resolve blank names, (2) fill missing AUM, (3) apply the
UCITS + accumulating + European-listing screen, (4) collapse duplicate and
near-duplicate funds keeping the largest, (5) rank by AUM.

The 'thematic' and 'ucits' (Selection) sleeves are passed through untouched.
"""
import csv, os

SRC = os.path.join(os.path.dirname(__file__), "panel_355_funds.csv")
OUT = os.path.dirname(__file__)

EURUSD, GBPUSD = 1.17, 1.34

# ---------------------------------------------------------------- names
# Yahoo returned the bare ticker as the name for these; resolved manually.
NAMES = {
    "ROBG.L":   "Global X Robotics & Artificial Intelligence UCITS ETF USD Acc",
    "ERNA.L":   "iShares $ Ultrashort Bond UCITS ETF USD (Acc)",
    "CSBGU7.SW":"iShares $ Treasury Bond 3-7yr UCITS ETF USD (Acc)",
    "EUNA.DE":  "iShares Core Global Aggregate Bond UCITS ETF EUR Hedged (Acc)",
    "BATT.L":   "WisdomTree Battery Solutions UCITS ETF USD Acc",
    "HTWO.L":   "L&G Hydrogen Economy UCITS ETF USD Acc",
    "ESPO.L":   "VanEck Video Gaming and eSports UCITS ETF USD Acc",
    "DAPP.L":   "VanEck Crypto & Blockchain Innovators UCITS ETF USD Acc",
    "ZPRS.DE":  "State Street SPDR MSCI World Small Cap UCITS ETF USD Acc",
    "CSNDX.SW": "iShares NASDAQ 100 UCITS ETF USD (Acc)",
    "XCS6.DE":  "Xtrackers MSCI China UCITS ETF 1C",
    "XMAS.DE":  "Xtrackers MSCI EM Asia Screened Swap UCITS ETF 1C",
    "NUKL.DE":  "VanEck Uranium and Nuclear Technologies UCITS ETF A USD Acc",
    "URNM.L":   "Sprott Uranium Miners UCITS ETF USD Acc",
    "SJPA.L":   "iShares Core MSCI Japan IMI UCITS ETF USD (Acc)",
    "SMEA.L":   "iShares Core MSCI Europe UCITS ETF EUR (Acc)",
    "XMEU.DE":  "Xtrackers MSCI Europe UCITS ETF 1C",
    "XMUS.DE":  "Xtrackers MSCI USA UCITS ETF 1C",
    "XNAS.DE":  "Xtrackers Nasdaq 100 UCITS ETF 1C",
    "IS3S.DE":  "iShares Edge MSCI World Value Factor UCITS ETF USD (Acc)",
    "IWFQ.L":   "iShares Edge MSCI World Quality Factor UCITS ETF USD (Acc)",
    "XDEB.DE":  "Xtrackers MSCI World Minimum Volatility UCITS ETF 1C",
    "XDEM.DE":  "Xtrackers MSCI World Momentum UCITS ETF 1C",
    "XDEQ.DE":  "Xtrackers MSCI World Quality UCITS ETF 1C",
    "XDEV.DE":  "Xtrackers MSCI World Value UCITS ETF 1C",
    "XDWC.DE":  "Xtrackers MSCI World Consumer Discretionary UCITS ETF 1C",
    "XDWS.DE":  "Xtrackers MSCI World Consumer Staples UCITS ETF 1C",
    "XDWI.DE":  "Xtrackers MSCI World Industrials UCITS ETF 1C",
    "XDWM.DE":  "Xtrackers MSCI World Materials UCITS ETF 1C",
    "XDWT.DE":  "Xtrackers MSCI World Information Technology UCITS ETF 1C",
    "XDWU.DE":  "Xtrackers MSCI World Utilities UCITS ETF 1C",
    "DGTL.L":   "iShares Digitalisation UCITS ETF USD (Acc)",
    "GDIG.L":   "VanEck S&P Global Mining UCITS ETF USD Acc",
    "SMGB.L":   "VanEck Semiconductor UCITS ETF USD Acc",
    "WCBR.L":   "WisdomTree Cybersecurity UCITS ETF USD Acc",
    "4GLD.DE":  "Xetra-Gold ETC",
    "EGLN.L":   "iShares Physical Gold ETC",
    "SGLN.L":   "iShares Physical Gold ETC (USD)",
    "SSLN.L":   "iShares Physical Silver ETC",
    "XGDU.DE":  "Xtrackers Physical Gold ETC",
}

# ------------------------------------------------------------------ AUM
# Yahoo returned no netAssets; sourced from issuer/justETF (Aug 2026),
# converted to USD m. Flagged 'estimated' in the output.
AUM_FILL = {
    "CNDX.L":   22150.0,           "XDWD.L":   22490.0,
    "MEUD.PA":  21036.0 * EURUSD,  "XD9U.DE":  11601.0 * EURUSD,
    "SPPW.DE":  17500.0,           "FWRA.L":    3746.0,
    "SJPA.L":    8341.0,           "DTLA.L":    2220.0,
    "XMEU.DE":   7833.0 * EURUSD,  "EUNA.DE":   2512.0 * EURUSD,
    "ERNA.L":    2657.0,           "VAGF.DE":   2290.0 * EURUSD,
    "ZPRR.DE":   5333.0,           "CW8.PA":    6581.0 * EURUSD,
    "CSBGU7.SW": 7773.0,           "CSNDX.SW": 22150.0,
    "XMUS.DE":  11601.0 * EURUSD,
}

# ------------------------------------------------------------- exclusions
# Physically-backed ETCs are debt securities, not UCITS funds: they fail the
# UCITS screen (no diversification rules, no share-class Acc/Dist split).
NON_UCITS = {t: "Physically-backed ETC (debt security), not a UCITS fund"
             for t in ["SGLD.SW","SGLE.MI","SGLN.L","EGLN.L","SSLN.L",
                       "4GLD.DE","XGDU.DE","XAD6.MI"]}

# ---------------------------------------------------- duplicate collapsing
# ticker -> (kept ticker, reason). Same fund = different listing/currency
# line. Same exposure = different fund, materially the same bet.
DROP = {
 # --- same fund, second listing or currency line ---
 "BOTZ.SW": ("ROBG.L","same fund, smaller listing"),
 "HTWO.L":  ("HTWG.L","same fund, smaller listing"),
 "BCHN.L":  ("BCHS.L","same fund, smaller listing"),
 "DAPP.L":  ("DAGB.L","same fund, smaller listing"),
 "CSNDX.SW":("CNDX.L","same fund, smaller listing"),
 "XMUS.DE": ("XD9U.DE","same fund, smaller listing"),
 "XMAS.DE": ("XMAD.L","same fund, duplicate line"),
 "QDVA.DE": ("IUMF.L","same fund, smaller listing"),
 "MVED.L":  ("IMV.L","same fund, smaller listing"),
 "XDEB.DE": ("XDEB.L","same fund, smaller listing"),
 "XDWT.DE": ("XDWT.SW","same fund, smaller listing"),
 "XDWU.DE": ("XDWU.SW","same fund, smaller listing"),
 "XDWC.DE": ("XWDS.L","same fund, smaller listing"),
 "XDWS.DE": ("XWCS.L","same fund, smaller listing"),
 "XDWI.DE": ("XWIS.L","same fund, smaller listing"),
 "XDWM.DE": ("XSMW.L","same fund, smaller listing"),
 "4COP.DE": ("COPG.L","same fund, smaller listing"),
 "REMX.L":  ("REGB.L","same fund, smaller listing"),
 "GDIG.L":  ("GIGB.L","same fund, smaller listing (also miscategorised)"),
 "SMGB.L":  ("SMHV.SW","same fund, smaller listing"),
 "HNSC.L":  ("HNSS.L","same fund, smaller listing"),
 "FSKY.L":  ("FSKY.MI","same fund, smaller listing"),
 "DGTL.L":  ("DGIT.L","same fund, smaller listing"),
 "2B79.DE": ("DGIT.L","same fund, smaller listing"),
 # --- same exposure, different fund ---
 "GLGG.L":  ("H2OA.AS","same exposure: global water equity"),
 "WATC.SW": ("H2OA.AS","same exposure: global water equity"),
 "ANRJ.L":  ("HTWG.L","same exposure: hydrogen economy"),
 "XAAG.DE": ("COMG.L","same exposure: commodity ex-agriculture"),
 "DAGB.L":  ("BCHS.L","same exposure: blockchain/crypto equity"),
 "FWRA.L":  ("VWCE.DE","same exposure: FTSE All-World"),
 "SPYI.DE": ("VWCE.DE","same exposure: global all-cap ACWI IMI"),
 "VHVE.L":  ("XDWD.L","same exposure: developed world large/mid"),
 "SPPW.DE": ("XDWD.L","same exposure: developed world large/mid"),
 "CW8.PA":  ("XDWD.L","same exposure: developed world large/mid"),
 "LGGG.L":  ("XDWD.L","same exposure: developed world large/mid"),
 "ZPRS.DE": ("WLDS.L","same exposure: world small cap"),
 "VALW.L":  ("IS3S.DE","same exposure: world value factor"),
 "XDEV.DE": ("IS3S.DE","same exposure: world value factor"),
 "XDEM.DE": ("IWMO.L","same exposure: world momentum factor"),
 "XDEQ.DE": ("IWFQ.L","same exposure: world quality factor"),
 "XD9U.DE": ("VUAA.L","same exposure: US large cap core"),
 "LGUG.L":  ("VUAA.L","same exposure: US large cap core"),
 "XNAS.DE": ("CNDX.L","same exposure: Nasdaq 100"),
 "UVAL.L":  ("IUVF.L","same exposure: US value factor"),
 "SMEA.L":  ("MEUD.PA","same exposure: broad European equity"),
 "XMEU.DE": ("MEUD.PA","same exposure: broad European equity"),
 "MEUG.L":  ("MEUD.PA","same exposure: broad European equity"),
 "RIEG.L":  ("MEUD.PA","same exposure: broad European equity"),
 "XZEU.SW": ("CEUR.L","same exposure: European ESG equity"),
 "SMCX.SW": ("XXSC.L","same exposure: European small cap"),
 "CV9.PA":  ("IEFV.L","same exposure: European value factor"),
 "AMEQ.DE": ("IEFQ.L","same exposure: European quality factor"),
 "EEIP.L":  ("CD9.PA","same exposure: European high dividend"),
 "S7XP.L":  ("BNKE.L","same exposure: euro-area banks"),
 "ESIE.L":  ("ENGE.L","same exposure: European energy sector"),
 "STKX.SW": ("ESIT.L","same exposure: European technology sector"),
 "XMME.DE": ("XMMS.L","same exposure: broad emerging markets"),
 "HEMC.L":  ("XMMS.L","same exposure: broad emerging markets"),
 "VFEA.L":  ("XMMS.L","same exposure: broad emerging markets"),
 "SPYM.DE": ("XMMS.L","same exposure: broad emerging markets"),
 "APEX.MI": ("SPYA.DE","same exposure: EM / Asia ex-Japan equity"),
 "XMAD.L":  ("SPYA.DE","same exposure: EM Asia equity"),
 "LGAG.L":  ("AEJL.L","same exposure: Asia Pacific ex-Japan"),
 "HCHS.L":  ("XCS6.DE","same exposure: MSCI China"),
 "LCCN.SW": ("XCS6.DE","same exposure: MSCI China"),
 "XCS5.DE": ("FLXI.DE","same exposure: India equity"),
 "CSJP.MI": ("SJPA.L","same exposure: Japan equity"),
 "LGJG.L":  ("SJPA.L","same exposure: Japan equity"),
 "HMJS.PA": ("SJPA.L","same exposure: Japan equity"),
 "VAGF.DE": ("EUNA.DE","same exposure: global aggregate, EUR hedged"),
 "AUCP.L":  ("GDGB.L","same exposure: gold miners"),
 "URNM.L":  ("NUKL.DE","same exposure: uranium / nuclear"),
 "SEMI.L":  ("SMHV.SW","same exposure: semiconductors"),
 "SEMG.L":  ("SMHV.SW","same exposure: semiconductors"),
 "HNSS.L":  ("SMHV.SW","same exposure: semiconductors"),
}

# Currency-hedged classes kept deliberately: a different risk profile, not a
# duplicate. Flagged so the hedged/unhedged pairing stays visible.
HEDGED = {"C099.DE":"COMG.L", "PSPH.PA":"VUAA.L", "XSXE.DE":"MEUD.PA",
          "EUNA.DE":"(unhedged equivalent not in list)"}

rows = list(csv.DictReader(open(SRC)))
for r in rows:
    if r["ticker"] in NAMES:
        r["name"] = NAMES[r["ticker"]]

yahoo = [r for r in rows if r["source"] == "extra"]
other = [r for r in rows if r["source"] != "extra"]

def aum(r):
    t = r["ticker"]
    if r["aum_usd_m"]:
        return float(r["aum_usd_m"]), "yahoo"
    if t in AUM_FILL:
        return AUM_FILL[t], "estimated"
    return None, "unknown"

keep, dropped = [], []
for r in yahoo:
    t, a = r["ticker"], aum(r)
    if t in NON_UCITS:
        dropped.append((t, r["name"], "non-UCITS", NON_UCITS[t], "", a[0])); continue
    if t in DROP:
        k, why = DROP[t]
        dropped.append((t, r["name"], "duplicate", why, k, a[0])); continue
    keep.append((r, a))

keep.sort(key=lambda x: -(x[1][0] or 0))

os.makedirs(OUT, exist_ok=True)
with open(f"{OUT}/yahoo_list.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["rank","ticker","name","category","venue","aum_usd_m",
                "aum_source","currency_hedged_of","first_price","coverage"])
    for i, (r, (a, src)) in enumerate(keep, 1):
        w.writerow([i, r["ticker"], r["name"], r["category"], r["venue"],
                    round(a,1) if a else "", src, HEDGED.get(r["ticker"],""),
                    r["first_price"], r["coverage"]])

with open(f"{OUT}/yahoo_list_removed.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["ticker","name","removed_because","detail","kept_instead","aum_usd_m"])
    for d in sorted(dropped, key=lambda x: (x[2], x[0])):
        w.writerow([d[0], d[1], d[2], d[3], d[4], round(d[5],1) if d[5] else ""])

# Full panel: curated Yahoo sleeve + untouched Thematic and Selection sleeves.
with open(f"{OUT}/panel_curated.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    kept_t = {r["ticker"] for r, _ in keep}
    for r in rows:
        if r["source"] != "extra" or r["ticker"] in kept_t:
            w.writerow(r)

print(f"Yahoo list: {len(yahoo)} -> {len(keep)} kept, {len(dropped)} removed")
print(f"  non-UCITS : {sum(1 for d in dropped if d[2]=='non-UCITS')}")
print(f"  duplicates: {sum(1 for d in dropped if d[2]=='duplicate')}")
print(f"Untouched  : {len(other)} rows (thematic + ucits/Selection)")
print(f"Panel      : {len(other)+len(keep)} rows")
miss = [r['ticker'] for r,(a,s) in keep if a is None]
print(f"Still missing AUM: {miss or 'none'}")
