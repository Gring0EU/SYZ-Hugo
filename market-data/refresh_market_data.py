"""Refresh the market data inside the Syz pages from Yahoo Finance (yfinance).

    pip install yfinance
    python3 market-data/refresh_market_data.py                      # every page in PAGES
    python3 market-data/refresh_market_data.py page.html [page.html ...]
    python3 market-data/refresh_market_data.py --fundamentals       # also P/E, yield, ADV, earnings
    python3 market-data/refresh_market_data.py --only MSFT,NOVN.SW  # a few symbols (testing)
    python3 market-data/refresh_market_data.py --seed DIR           # start from the data in DIR

The pages (the Advisory Workbench, Life Syzcle) carry the same snapshot in
<script id="sp-data">: quotes and daily closes for the Core List, gzipped JSON.
The symbols of all the pages are downloaded once (13 months of daily bars, in
batches) and every page is rewritten in place:

  * history: the last 10 stored days are re-taken from Yahoo and the closes
    after them appended, which fills days the old snapshot missed and
    replaces its last point (taken during the session, an intraday price)
  * quotes: price, 52-week high and low, 1-year change, distance to the
    52-week high and to the 200-day average are recomputed from the bars;
    market cap, P/E and forward P/E move with the price, the dividend yield
    against it. Names, currencies, lists, themes and the rest are kept.
  * --fundamentals: P/E, forward P/E, dividend yield (trailing 12 months),
    average daily traded value (3 months, USD) and the next earnings date are
    read from each symbol's Yahoo profile: one request per symbol, about
    20 minutes for the whole list, so the scheduled job does it once a week.
  * --seed DIR: quotes and history are first taken from DIR/<same path> when
    that copy is more recent (the last refreshed pages), so the weekly
    fundamentals survive the daily runs; the page's own code, lists and
    themes are kept.
  * asof: the time of the refresh, Zurich time

Symbols Yahoo returns nothing for (delisted, renamed) are retried once in a
smaller batch, then keep their old data and are listed at the end.
"""
import argparse
import base64
import datetime as dt
import gzip
import json
import math
import os
import re
import sys
import time
from zoneinfo import ZoneInfo

import yfinance as yf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES = ["workbench/G01_workbench.html", "termsheet-studio/T01_life_syzcle.html"]
TAG = re.compile(r'(<script id="sp-data" type="application/octet-stream">)(.*?)(</script>)', re.S)
BATCH = 150
OVERLAP = 10   # days of stored history re-taken from Yahoo
EPOCH = dt.date(1970, 1, 1)
# quoted in the currency's hundredth: GBp pence, ZAc South African cents, ILA agorot, KWF fils (1/1000)
MINOR = {"GBp": ("GBP", 100), "GBX": ("GBP", 100), "ZAc": ("ZAR", 100), "ILA": ("ILS", 100), "KWF": ("KWD", 1000)}


# --- the page's history encoding: [first day, day gaps, log-price steps x 10000] -----------------
def decode(enc):
    if not enc:
        return []
    day, gaps, steps = enc
    out, logp = [], 0
    for i, step in enumerate(steps):
        if i:
            day += gaps[i - 1]
        logp += step
        out.append((day, logp))
    return out


def encode(points):
    if not points:
        return []
    days = [d for d, _ in points]
    logs = [l for _, l in points]
    return [days[0], [b - a for a, b in zip(days, days[1:])], [logs[0]] + [b - a for a, b in zip(logs, logs[1:])]]


def day_of(ts):
    return (ts.date() - EPOCH).days


# --- pages ------------------------------------------------------------------------------------
class Page:
    def __init__(self, path):
        self.path = path
        self.html = open(path, encoding="utf-8").read()
        self.m = TAG.search(self.html)
        if not self.m:
            sys.exit(f"{path}: no market data (<script id=\"sp-data\">) in this page")
        self.data = json.loads(gzip.decompress(base64.b64decode(self.m.group(2).strip())))

    def symbols(self):
        return set(self.data["hist"]) | set(self.data["quotes"])

    def seed_from(self, other):
        """Take quotes and history from a more recent copy of this page, keep everything else."""
        if (other.data.get("asof") or "") <= (self.data.get("asof") or ""):
            return False
        for key in ("quotes", "hist"):
            mine, theirs = self.data[key], other.data[key]
            for s in mine:
                if s in theirs:
                    if key == "quotes":
                        # the page's own name and type win, the market fields come from the copy
                        mine[s] = dict(theirs[s], **{k: mine[s][k] for k in ("name", "type") if k in mine[s]})
                    else:
                        mine[s] = theirs[s]
        self.data["asof"] = other.data["asof"]
        return True

    def save(self, asof):
        self.data["asof"] = asof
        blob = base64.b64encode(gzip.compress(json.dumps(self.data, separators=(",", ":")).encode("utf-8"), 9)).decode("ascii")
        html = self.html[:self.m.start(2)] + blob + self.html[self.m.end(2):]
        open(self.path, "w", encoding="utf-8").write(html)


# --- prices -----------------------------------------------------------------------------------
def refresh_symbol(symbol, bars, data):
    """Merge one symbol's bars (a DataFrame with Close / Adj Close / High / Low) into a snapshot."""
    bars = bars.dropna(subset=["Close"])
    bars = bars[bars["Close"] > 0]
    if bars.empty:
        return False
    if symbol in data["hist"] or symbol in data["quotes"]:
        points = decode(data["hist"].get(symbol))
        last = points[-1][0] if points else None
        adj = bars["Adj Close"] if "Adj Close" in bars else bars["Close"]
        adj = adj[adj > 0]   # Yahoo sometimes leaves the adjusted close at 0 or blank on a day it has a close for
        new = [(day_of(ts), round(math.log(float(p)) * 10000)) for ts, p in adj.items()]
        if last is not None:
            # Yahoo's bars replace the last OVERLAP days stored: that fills days the old snapshot
            # missed and turns its intraday last point into the close.
            new = [(d, l) for d, l in new if d >= last - OVERLAP]
            points = [p for p in points if p[0] < (new[0][0] if new else last + 1)]
        points += new
        data["hist"][symbol] = encode(points)

    q = data["quotes"].get(symbol)
    if q is None:
        return True
    closes = bars["Close"]
    price = float(closes.iloc[-1])
    year = bars[bars.index >= bars.index[-1] - dt.timedelta(days=365)]
    old = q.get("price")
    q["price"] = round(price, 6)
    q["high_52w"] = round(float(year["High"].max()), 6)
    q["low_52w"] = round(float(year["Low"].min()), 6)
    q["vs_high_52w"] = round(price / q["high_52w"] - 1, 6) if q["high_52w"] else None
    before = closes[closes.index <= closes.index[-1] - dt.timedelta(days=365)]
    if len(before):
        q["change_52w"] = round(price / float(before.iloc[-1]) - 1, 6)
    if len(closes) >= 200:
        q["vs_ma200"] = round(price / float(closes.iloc[-200:].mean()) - 1, 6)
    if old:
        ratio = price / old
        for key in ("mcap_usd_bn", "pe", "forward_pe"):
            if isinstance(q.get(key), (int, float)):
                q[key] = round(q[key] * ratio, 6)
        if isinstance(q.get("dividend_yield"), (int, float)):
            q["dividend_yield"] = round(q["dividend_yield"] / ratio, 6)
    return True


def download(symbols, start):
    """Daily bars per symbol, in batches; symbols with nothing back are retried once, 25 at a time."""
    got = {}

    def run(chunk):
        frame = yf.download(chunk, start=start.isoformat(), auto_adjust=False, group_by="ticker",
                            progress=False, threads=True)
        for s in chunk:
            try:
                bars = frame[s] if len(chunk) > 1 else frame
            except KeyError:
                continue
            if not bars.dropna(subset=["Close"]).empty:
                got[s] = bars

    for i in range(0, len(symbols), BATCH):
        run(symbols[i:i + BATCH])
        print(f"  {min(i + BATCH, len(symbols))}/{len(symbols)}", flush=True)
    retry = [s for s in symbols if s not in got]
    if retry:
        print(f"  retrying {len(retry)} symbols", flush=True)
        time.sleep(20)
        for i in range(0, len(retry), 25):
            run(retry[i:i + 25])
    return got


# --- fundamentals -----------------------------------------------------------------------------
def usd_rates(currencies):
    """USD value of one unit of each currency, from Yahoo's FX quotes (JPY=X is JPY per USD)."""
    rates = {"USD": 1.0}
    need = sorted({MINOR.get(c, (c, 1))[0] for c in currencies if c} - {"USD"})
    if not need:
        return rates
    frame = yf.download([f"{c}=X" for c in need], period="10d", progress=False, group_by="ticker", threads=True)
    for c in need:
        try:
            closes = (frame[f"{c}=X"] if len(need) > 1 else frame)["Close"].dropna()
            if len(closes):
                rates[c] = 1 / float(closes.iloc[-1])
        except KeyError:
            pass
    return rates


def refresh_fundamentals(symbols, quotes, rates):
    """P/E, forward P/E, trailing dividend yield, 3-month ADV in USD m, next earnings date."""
    done, failed = 0, []
    for n, s in enumerate(symbols, 1):
        q = quotes.get(s)
        if not q or q.get("type") == "INDEX":
            continue
        info = None
        for attempt in range(3):
            try:
                info = yf.Ticker(s).info
                break
            except Exception:
                time.sleep(5 * (attempt + 1))
        if not info or not (info.get("regularMarketPrice") or info.get("currentPrice") or info.get("previousClose")):
            failed.append(s)
            if not done and len(failed) >= 20:
                print("  Yahoo refuses the profile requests (20 in a row): fundamentals left as they were", flush=True)
                return done, [x for x in symbols if x in quotes]
            continue
        major, unit = MINOR.get(q.get("currency"), (q.get("currency"), 1))
        fx = rates.get(major)
        for key, field in (("pe", "trailingPE"), ("forward_pe", "forwardPE")):
            v = info.get(field)
            if isinstance(v, (int, float)) and v > 0:
                q[key] = round(float(v), 6)
            else:
                q.pop(key, None)   # a loss-making company has no P/E: an old one would mislead
        dy = info.get("trailingAnnualDividendYield")
        if isinstance(dy, (int, float)):
            # Yahoo divides a dividend in pounds by a price in pence: put the hundredth back
            q["dividend_yield"] = round(float(dy) * unit, 6)
        vol = info.get("averageDailyVolume3Month") or info.get("averageVolume")
        if vol and fx and q.get("price"):
            q["adv_musd"] = round(vol * q["price"] / unit * fx / 1e6, 6)
        ts = info.get("earningsTimestampStart") or info.get("earningsTimestamp")
        if isinstance(ts, (int, float)):
            q["earnings"] = int(ts)
        done += 1
        if n % 100 == 0:
            print(f"  fundamentals {n}/{len(symbols)}", flush=True)
        time.sleep(0.2)
    return done, failed


# --- main -------------------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("pages", nargs="*", help="pages to refresh (default: %s)" % ", ".join(PAGES))
    ap.add_argument("--fundamentals", action="store_true", help="also refresh P/E, yield, ADV and earnings dates")
    ap.add_argument("--seed", help="folder holding more recent copies of the pages, same relative paths")
    ap.add_argument("--only", help="comma-separated symbols to refresh (testing)")
    args = ap.parse_args()

    paths = args.pages or [os.path.join(ROOT, p) for p in PAGES]
    pages = [Page(p) for p in paths]
    if args.seed:
        for p in pages:
            copy = os.path.join(args.seed, os.path.relpath(os.path.abspath(p.path), ROOT))
            if os.path.exists(copy) and p.seed_from(Page(copy)):
                print(f"{os.path.relpath(p.path, ROOT)}: started from the data of {p.data['asof']} in {args.seed}")

    symbols = sorted(set().union(*(p.symbols() for p in pages)))
    if args.only:
        wanted = {s.strip() for s in args.only.split(",")}
        symbols = [s for s in symbols if s in wanted]
    start = dt.date.today() - dt.timedelta(days=400)
    print(f"{len(pages)} page(s), {len(symbols)} symbols, downloading from {start}", flush=True)

    bars = download(symbols, start)
    for p in pages:
        for s, b in bars.items():
            refresh_symbol(s, b, p.data)
    missing = [s for s in symbols if s not in bars]

    if args.fundamentals:
        quotes = {}
        for p in reversed(pages):   # the first page's quote wins; the result is copied to every page
            quotes.update(p.data["quotes"])
        rates = usd_rates({q.get("currency") for q in quotes.values()})
        done, failed = refresh_fundamentals([s for s in symbols if s in quotes], quotes, rates)
        for p in pages:
            for s in symbols:
                if s in p.data["quotes"] and s in quotes and s not in failed:
                    for key in ("pe", "forward_pe", "dividend_yield", "adv_musd", "earnings"):
                        if key in quotes[s]:
                            p.data["quotes"][s][key] = quotes[s][key]
                        else:
                            p.data["quotes"][s].pop(key, None)
        print(f"fundamentals refreshed for {done} symbols" + (f", none from Yahoo for {len(failed)}" if failed else ""))

    asof = dt.datetime.now(ZoneInfo("Europe/Zurich")).strftime("%Y-%m-%d %H:%M")   # Zurich time, wherever it runs
    for p in pages:
        p.save(asof)
        print(f"{os.path.relpath(p.path, ROOT)}: market data as of {asof}")
    print(f"refreshed {len(bars)} of {len(symbols)} symbols")
    if missing:
        print(f"no data from Yahoo for {len(missing)} (kept as they were): {', '.join(missing[:40])}{' …' if len(missing) > 40 else ''}")
    if len(bars) < 0.8 * len(symbols):
        sys.exit("fewer than 80% of the symbols came back: Yahoo is probably blocking, the pages were saved anyway")


if __name__ == "__main__":
    main()
