"""Free market data as a Claude connector (MCP server). No account, no API key.

Sources and the domains they need:
  Yahoo Finance   query1/query2.finance.yahoo.com, finance.yahoo.com, fc.yahoo.com, guce.yahoo.com
  Stooq           stooq.com, stooq.pl
  ECB             data-api.ecb.europa.eu, www.ecb.europa.eu
  Frankfurter     api.frankfurter.app, api.frankfurter.dev (the .app address now forwards there)
  SNB             data.snb.ch

Run it from Claude Code (the repository's .mcp.json starts it) or by hand:
  pip install mcp yfinance
  python3 market-data/mcp_server.py
"""

import csv
import io
import math

import requests
import yfinance as yf
try:
    from mcp.server.mcpserver import MCPServer  # mcp 2.x
except ImportError:
    from mcp.server.fastmcp import FastMCP as MCPServer  # mcp 1.x

mcp = MCPServer("syz-market-data")
HTTP = requests.Session()
HTTP.headers["User-Agent"] = "Mozilla/5.0 (syz-market-data)"


def get(url, **params):
    r = HTTP.get(url, params=params, timeout=30)
    r.raise_for_status()
    r.encoding = r.encoding or "utf-8-sig"  # SNB sends no charset; guessing it on a large file is slow
    return r


def clean(x):
    """JSON-safe number: NaN and infinities become None."""
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(x) or math.isinf(x) else round(x, 6)


# Yahoo Finance

@mcp.tool()
def yahoo_quote(symbols: list[str]) -> list[dict]:
    """Last price, previous close, change, currency and exchange for Yahoo symbols
    (e.g. NESN.SW, ASML.AS, MSFT, EURCHF=X, ^SSMI, GC=F)."""
    out = []
    for s in symbols:
        try:
            fi = yf.Ticker(s).fast_info
            last, prev = clean(fi.last_price), clean(fi.previous_close)
            out.append({"symbol": s, "last": last, "previous_close": prev,
                        "change_pct": clean((last / prev - 1) * 100) if last and prev else None,
                        "currency": fi.currency, "exchange": fi.exchange})
        except Exception as e:
            out.append({"symbol": s, "error": str(e)})
    return out


@mcp.tool()
def yahoo_history(symbol: str, period: str = "1y", interval: str = "1d") -> list[dict]:
    """Daily (or other interval) OHLCV bars, dividend- and split-adjusted closes.
    period: 1mo 3mo 6mo 1y 2y 5y 10y max. interval: 1d 1wk 1mo (or 1h, 15m for short periods)."""
    df = yf.Ticker(symbol).history(period=period, interval=interval, auto_adjust=True)
    return [{"date": str(i.date() if interval[-1] in "dko" else i), "open": clean(r.Open), "high": clean(r.High),
             "low": clean(r.Low), "close": clean(r.Close), "volume": clean(r.Volume)} for i, r in df.iterrows()]


@mcp.tool()
def yahoo_profile(symbol: str) -> dict:
    """Company profile and fundamentals: name, sector, market cap, P/E, dividend yield, beta,
    52-week range, average volume, next earnings date."""
    info = yf.Ticker(symbol).info
    keys = ["longName", "sector", "industry", "country", "currency", "marketCap", "trailingPE", "forwardPE",
            "dividendYield", "trailingAnnualDividendYield", "beta", "fiftyTwoWeekLow", "fiftyTwoWeekHigh",
            "averageDailyVolume3Month", "earningsTimestampStart", "longBusinessSummary"]
    return {k: info.get(k) for k in keys}


@mcp.tool()
def yahoo_option_expiries(symbol: str) -> list[str]:
    """Listed option expiry dates for a US-listed symbol."""
    return list(yf.Ticker(symbol).options)


@mcp.tool()
def yahoo_option_chain(symbol: str, expiry: str, kind: str = "calls",
                       min_strike: float | None = None, max_strike: float | None = None) -> list[dict]:
    """Option chain for one expiry (YYYY-MM-DD): strike, bid, ask, last, volume, open interest,
    Yahoo implied volatility. kind: calls or puts. Bid and ask are 0 outside US hours."""
    chain = yf.Ticker(symbol).option_chain(expiry)
    df = chain.calls if kind == "calls" else chain.puts
    if min_strike is not None:
        df = df[df.strike >= min_strike]
    if max_strike is not None:
        df = df[df.strike <= max_strike]
    return [{"contract": r.contractSymbol, "strike": clean(r.strike), "bid": clean(r.bid), "ask": clean(r.ask),
             "last": clean(r.lastPrice), "last_trade": str(r.lastTradeDate), "volume": clean(r.volume),
             "open_interest": clean(r.openInterest), "implied_vol": clean(r.impliedVolatility)}
            for r in df.itertuples()]


@mcp.tool()
def yahoo_search(query: str) -> list[dict]:
    """Find Yahoo symbols from a company name or ISIN."""
    r = get("https://query2.finance.yahoo.com/v1/finance/search", q=query, quotesCount=10, newsCount=0)
    return [{"symbol": q.get("symbol"), "name": q.get("longname") or q.get("shortname"),
             "type": q.get("quoteType"), "exchange": q.get("exchDisp")} for q in r.json().get("quotes", [])]


# Stooq

@mcp.tool()
def stooq_history(symbol: str, interval: str = "d") -> list[dict]:
    """Full daily history from Stooq, a backup for Yahoo. Symbols: nesn.ch, asml.nl, msft.us,
    eurchf, ^spx, xauusd. interval: d (daily), w (weekly), m (monthly)."""
    text = get("https://stooq.com/q/d/l/", s=symbol.lower(), i=interval).text
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows or "Close" not in rows[0]:
        raise ValueError(f"Stooq has no data for {symbol}")
    return [{"date": r["Date"], "open": clean(r["Open"]), "high": clean(r["High"]), "low": clean(r["Low"]),
             "close": clean(r["Close"]), "volume": clean(r.get("Volume"))} for r in rows]


# ECB

@mcp.tool()
def ecb_fx(currencies: list[str], start: str | None = None, end: str | None = None) -> list[dict]:
    """ECB euro reference rates (one unit of EUR in each currency), daily, published around 16:00 CET.
    currencies: e.g. ["USD", "CHF", "GBP"]. start, end: YYYY-MM-DD (default: last 30 observations)."""
    params = {"format": "csvdata"}
    if start:
        params["startPeriod"] = start
    if end:
        params["endPeriod"] = end
    if not start and not end:
        params["lastNObservations"] = 30
    text = get(f"https://data-api.ecb.europa.eu/service/data/EXR/D.{'+'.join(currencies)}.EUR.SP00.A",
               **params).text
    return [{"date": r["TIME_PERIOD"], "currency": r["CURRENCY"], "eur_rate": clean(r["OBS_VALUE"])}
            for r in csv.DictReader(io.StringIO(text))]


@mcp.tool()
def ecb_series(key: str, last: int = 30) -> list[dict]:
    """Any ECB Data Portal series by key, e.g. FM.D.U2.EUR.4F.KR.DFR.LEV (deposit facility rate),
    EST.B.EU000A2X2A25.WT (€STR), ICP.M.U2.N.000000.4.ANR (euro-area inflation)."""
    flow, rest = key.split(".", 1)
    text = get(f"https://data-api.ecb.europa.eu/service/data/{flow}/{rest}",
               format="csvdata", lastNObservations=last).text
    return [{"date": r["TIME_PERIOD"], "value": clean(r["OBS_VALUE"])} for r in csv.DictReader(io.StringIO(text))]


# Frankfurter

@mcp.tool()
def frankfurter_fx(base: str = "EUR", symbols: list[str] | None = None,
                   date: str = "latest", end: str | None = None) -> dict:
    """ECB reference rates through Frankfurter, with any base currency.
    date: latest or YYYY-MM-DD; give end (YYYY-MM-DD) for a time series from date to end."""
    path = f"{date}..{end}" if end else date
    params = {"from": base}
    if symbols:
        params["to"] = ",".join(symbols)
    return get(f"https://api.frankfurter.dev/v1/{path}", **params).json()


# SNB

@mcp.tool()
def snb_rates(months: int = 24) -> list[dict]:
    """Monthly money-market rates from the Swiss National Bank: SARON, SNB policy rate, CHF, EUR (€STR),
    USD (SOFR), GBP (SONIA) and JPY (TONA) overnight rates, in percent."""
    text = get("https://data.snb.ch/api/cube/zimoma/data/csv/en").text
    lines = text.splitlines()
    head = next(i for i, l in enumerate(lines) if l.startswith('"Date"'))
    rows = list(csv.DictReader(io.StringIO("\n".join(lines[head:])), delimiter=";"))
    since = _months_ago(rows, months)
    return [{"month": r["Date"], "series": r["D0"], "rate_pct": clean(r["Value"])}
            for r in rows if r["Date"] >= since]


@mcp.tool()
def snb_cube(cube: str, months: int = 24) -> list[dict]:
    """Any SNB data cube by id (see data.snb.ch), e.g. devkum (monthly FX rates), snbbipo (SNB balance sheet),
    plkopr (Swiss CPI)."""
    text = get(f"https://data.snb.ch/api/cube/{cube}/data/csv/en").text
    lines = text.splitlines()
    head = next(i for i, l in enumerate(lines) if l.startswith('"Date"'))
    rows = list(csv.DictReader(io.StringIO("\n".join(lines[head:])), delimiter=";"))
    since = _months_ago(rows, months)
    return [{k: (clean(v) if k == "Value" else v) for k, v in r.items()}
            for r in rows if r["Date"] >= since]


def _months_ago(rows, months):
    dates = sorted({r["Date"] for r in rows})
    return dates[-months] if len(dates) >= months else dates[0]


if __name__ == "__main__":
    mcp.run()
