"""Download the free data the Data Lab page is built from, into the folder given (default: showcase/data).

    pip install yfinance numpy
    python3 showcase/fetch_data.py && python3 showcase/compute.py && python3 showcase/render.py

Yahoo Finance (yfinance): 7 years of daily closes, profiles, the Microsoft option chain nearest one year.
ECB data API: daily CHF and USD reference rates against the euro.
SNB data portal: the money-market cube (SARON, €STR, SOFR...).
"""
import datetime as dt, json, os, sys, urllib.request
import yfinance as yf

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(OUT, exist_ok=True)
SYMS = ["NESN.SW", "ASML.AS", "MSFT", "EURCHF=X", "USDCHF=X"]

def get(url, name):
    with urllib.request.urlopen(url, timeout=60) as r:
        open(os.path.join(OUT, name), "wb").write(r.read())

start = (dt.date.today() - dt.timedelta(days=2 * 365)).replace(day=1).isoformat()
get(f"https://data-api.ecb.europa.eu/service/data/EXR/D.USD+CHF.EUR.SP00.A?startPeriod={start}&format=csvdata", "ecb_fx.csv")
get("https://data.snb.ch/api/cube/zimoma/data/csv/en", "snb_zimoma.csv")

f = yf.download(SYMS, period="7y", auto_adjust=False, group_by="ticker", progress=False, threads=True)
hist = {}
for s in SYMS:
    b = f[s].dropna(subset=["Close"])
    hist[s] = {"dates": [d.strftime("%Y-%m-%d") for d in b.index], "close": [round(float(x), 4) for x in b["Close"]],
               "adj": [round(float(x), 4) for x in b["Adj Close"]]}
json.dump(hist, open(os.path.join(OUT, "yahoo_hist.json"), "w"))

info = {}
for s in SYMS[:3]:
    i = yf.Ticker(s).info
    info[s] = {k: i.get(k) for k in ["longName", "currency", "trailingAnnualDividendYield", "dividendYield", "trailingPE", "forwardPE",
                                     "marketCap", "earningsTimestampStart", "fiftyTwoWeekHigh", "fiftyTwoWeekLow", "sector", "beta"]}
json.dump(info, open(os.path.join(OUT, "yahoo_info.json"), "w"))

t = yf.Ticker("MSFT")
target = dt.date.today() + dt.timedelta(days=365)
expiry = min(t.options, key=lambda x: abs((dt.date.fromisoformat(x) - target).days))
chain = t.option_chain(expiry)
rows = [{"type": kind, "strike": float(r.strike), "iv": float(r.impliedVolatility), "bid": float(r.bid), "ask": float(r.ask)}
        for kind, df in (("call", chain.calls), ("put", chain.puts)) for _, r in df.iterrows()]
json.dump({"MSFT": {"expiry": expiry, "spot": float(t.history(period="5d")["Close"].iloc[-1]), "rows": rows}},
          open(os.path.join(OUT, "yahoo_options.json"), "w"))
print("data saved in", OUT)
