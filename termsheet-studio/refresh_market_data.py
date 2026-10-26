"""Refresh the market data inside Life Syzcle from Yahoo Finance (yfinance).

    pip install yfinance
    python3 termsheet-studio/refresh_market_data.py [termsheet-studio/T01_life_syzcle.html]

The page carries the workbench's snapshot (<script id="sp-data">: quotes and
daily closes for the Core List, gzipped JSON). This script downloads the last
13 months of daily bars for every symbol in it, in batches, and:

  * history: the last 10 stored days are re-taken from Yahoo and the closes
    after them appended, which fills days the old snapshot missed and
    replaces its last point (taken during the session, an intraday price)
  * quotes: price, 52-week high and low, 1-year change, distance to the
    52-week high and to the 200-day average are recomputed from the bars;
    market cap, P/E and forward P/E move with the price, the dividend yield
    against it. Names, currencies, earnings dates and the rest are kept.
  * asof: the time of the refresh

Symbols Yahoo returns nothing for (delisted, renamed) keep their old data
and are listed at the end. The page is rewritten in place.
"""
import base64
import datetime as dt
import gzip
import json
import math
import os
import re
import sys

import yfinance as yf

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT = os.path.join(HERE, "T01_life_syzcle.html")
TAG = re.compile(r'(<script id="sp-data" type="application/octet-stream">)(.*?)(</script>)', re.S)
BATCH = 150
OVERLAP = 10   # days of stored history re-taken from Yahoo
EPOCH = dt.date(1970, 1, 1)


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


def refresh_symbol(symbol, bars, data, today):
    """Merge one symbol's bars (a DataFrame with Close / Adj Close / High / Low) into the snapshot."""
    bars = bars.dropna(subset=["Close"])
    bars = bars[bars["Close"] > 0]
    if bars.empty:
        return False
    points = decode(data["hist"].get(symbol))
    last = points[-1][0] if points else None
    adj = bars["Adj Close"] if "Adj Close" in bars else bars["Close"]
    adj = adj[adj > 0]   # Yahoo sometimes leaves the adjusted close at 0 or blank on a day it has a close for
    new =[(day_of(ts), round(math.log(float(p)) * 10000)) for ts, p in adj.items()]
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


def main(path):
    page = open(path, encoding="utf-8").read()
    m = TAG.search(page)
    if not m:
        sys.exit(f"{path}: no market data (<script id=\"sp-data\">) in this page")
    data = json.loads(gzip.decompress(base64.b64decode(m.group(2).strip())))
    symbols = sorted(set(data["hist"]) | set(data["quotes"]))
    today = dt.date.today()
    start = today - dt.timedelta(days=400)
    print(f"snapshot of {data.get('asof')}: {len(symbols)} symbols, downloading from {start}")

    done, missing = 0, []
    for i in range(0, len(symbols), BATCH):
        chunk = symbols[i:i + BATCH]
        frame = yf.download(chunk, start=start.isoformat(), auto_adjust=False, group_by="ticker",
                            progress=False, threads=True)
        for s in chunk:
            try:
                bars = frame[s] if len(chunk) > 1 else frame
            except KeyError:
                missing.append(s)
                continue
            if refresh_symbol(s, bars, data, today):
                done += 1
            else:
                missing.append(s)
        print(f"  {min(i + BATCH, len(symbols))}/{len(symbols)}")

    data["asof"] = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    blob = base64.b64encode(gzip.compress(json.dumps(data, separators=(",", ":")).encode("utf-8"), 9)).decode("ascii")
    page = page[:m.start(2)] + blob + page[m.end(2):]
    open(path, "w", encoding="utf-8").write(page)
    print(f"refreshed {done} symbols, market data as of {data['asof']}")
    if missing:
        print(f"no data from Yahoo for {len(missing)} (kept as they were): {', '.join(missing[:40])}{' …' if len(missing) > 40 else ''}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else DEFAULT)
