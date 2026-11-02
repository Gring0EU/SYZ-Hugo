"""Technical review of one stock: indicators, eight plain-English signals, a verdict and its levels.

Pure Python (no numpy). `measures()` turns daily bars into indicators; `review()` turns those into
what the P02 one-pager says: signals (Positive / Neutral / Negative), the view (bear / neutral /
bull), the zone and stop level, resistances and supports, and the plan for holders, new money and
structured products. The wording avoids personal recommendations; the page carries the disclaimer.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from math import log, sqrt

MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
PROTECTION = {"bear": 60, "neutral": 65, "bull": 70}        # suggested max strike/barrier for structured products, %


# --- indicators ----------------------------------------------------------------------------------------
def sma(x: list[float], n: int) -> list[float | None]:
    return [None if i + 1 < n else sum(x[i + 1 - n:i + 1]) / n for i in range(len(x))]


def ema(x: list[float], n: int) -> list[float]:
    k, out, e = 2 / (n + 1), [], None
    for v in x:
        e = v if e is None else e + k * (v - e)
        out.append(e)
    return out


def rsi(x: list[float], n: int = 14) -> list[float | None]:
    """Wilder's RSI."""
    out, ag, al = [None] * len(x), 0.0, 0.0
    for i in range(1, len(x)):
        ch = x[i] - x[i - 1]
        g, l_ = max(ch, 0.0), max(-ch, 0.0)
        if i <= n:
            ag += g / n
            al += l_ / n
            if i == n:
                out[i] = 100 - 100 / (1 + ag / al) if al else 100.0
        else:
            ag = (ag * (n - 1) + g) / n
            al = (al * (n - 1) + l_) / n
            out[i] = 100 - 100 / (1 + ag / al) if al else 100.0
    return out


def realised_vol(closes: list[float], n: int) -> float:
    """Annualised stdev of the last n daily log returns, in %."""
    r = [log(b / a) for a, b in zip(closes, closes[1:]) if a > 0 and b > 0][-n:]
    m = sum(r) / len(r)
    return 100 * sqrt(sum((x - m) ** 2 for x in r) / (len(r) - 1) * 252)


def last_cross(a: list, b: list, dates: list[str], back: int) -> str | None:
    """Date of the latest sign change of a - b within `back` sessions."""
    for i in range(len(a) - 1, max(len(a) - back, 1), -1):
        if None in (a[i], b[i], a[i - 1], b[i - 1]):
            break
        if (a[i] - b[i]) * (a[i - 1] - b[i - 1]) < 0:
            return dates[i]
    return None


def measures(bars: list[dict], bench: list[dict], earnings_ts: float | None = None) -> dict:
    """Indicators from daily bars (oldest first, keys date/close/high/low/volume; two years is enough)
    and the benchmark's bars (for relative performance)."""
    d = [b["date"] for b in bars]
    cl = [b["close"] for b in bars]
    hi = [b.get("high") or b["close"] for b in bars]
    lo = [b.get("low") or b["close"] for b in bars]
    vol = [b.get("volume") or 0 for b in bars]
    n = len(cl)
    if n < 260:
        raise ValueError(f"need about a year and a half of prices, got {n} sessions")
    ma20, ma50, ma200 = sma(cl, 20), sma(cl, 50), sma(cl, 200)
    macd = [a - b for a, b in zip(ema(cl, 12), ema(cl, 26))]
    sig = ema(macd, 9)
    tr = [hi[0] - lo[0]] + [max(hi[i] - lo[i], abs(hi[i] - cl[i - 1]), abs(lo[i] - cl[i - 1])) for i in range(1, n)]
    bd = {b["date"]: b["close"] for b in bench}

    def perf(days=None, since=None):
        i0 = next(i for i, x in enumerate(d) if x >= since) if since else n - 1 - days
        b0, b1 = bd.get(d[i0]), bd.get(d[-1])
        return 100 * (cl[-1] / cl[i0] - 1), (100 * (b1 / b0 - 1) if b0 and b1 else None)

    start = n - 126                                   # swing points, last 6 months, 5 sessions each side
    piv_hi = [(d[i], hi[i]) for i in range(max(5, start), n - 5) if hi[i] == max(hi[i - 5:i + 6])]
    piv_lo = [(d[i], lo[i]) for i in range(max(5, start), n - 5) if lo[i] == min(lo[i - 5:i + 6])]
    y1 = slice(n - 252, n)
    i2 = lo.index(min(lo))
    earn = datetime.fromtimestamp(earnings_ts, tz=timezone.utc).date().isoformat() if earnings_ts else None
    return {
        "asof": d[-1], "dates": d[y1], "close": cl[y1], "ma20": ma20[y1], "ma50": ma50[y1], "ma200": ma200[y1],
        "last": cl[-1], "prev": cl[-2], "atr": sma(tr, 14)[-1], "rsi": rsi(cl)[-1],
        "macd": macd[-1], "macd_signal": sig[-1], "rv1m": realised_vol(cl, 21), "rv3m": realised_vol(cl, 63),
        "ma200_slope": ma200[-1] - ma200[-21], "ma50_slope": ma50[-1] - ma50[-11],
        "hi52": max(hi[y1]), "hi52_date": d[y1][hi[y1].index(max(hi[y1]))],
        "lo52": min(lo[y1]), "lo52_date": d[y1][lo[y1].index(min(lo[y1]))],
        "lo2y": lo[i2], "lo2y_date": d[i2],
        "vol_ratio": vol[-1] / (sum(vol[-20:]) / 20) if sum(vol[-20:]) else 1.0, "last_up": cl[-1] >= cl[-2],
        "perf": {"1W": perf(5), "1M": perf(21), "3M": perf(63), "YTD": perf(since=d[-1][:4] + "-01-01"), "1Y": perf(252)},
        "piv_hi": piv_hi, "piv_lo": piv_lo,
        "macd_cross": last_cross(macd, sig, d, 150), "ma_cross": last_cross(ma50, ma200, d, 500),
        "earnings": earn,
    }


# --- the review -------------------------------------------------------------------------------------------
def dm(iso: str) -> str:
    return f"{iso[8:10]}.{iso[5:7]}"


def mon(iso: str) -> str:
    return f"{MON[int(iso[5:7]) - 1]} {iso[2:4]}"


def _num(x: float, dp: int = 2) -> str:
    return f"{x:,.{dp}f}"


def _pc(x: float, dp: int = 1) -> str:
    return f"{x:+.{dp}f}%"


def _cluster(points: list[tuple], reverse: bool, tol: float = 0.015) -> list[tuple[float, str]]:
    """Levels within `tol` (1.5%) of each other count once: the moving average(s) if any, else the latest
    swing. points: (value, "ma" | "swing", days | iso date)."""
    groups: list[list[tuple]] = []
    for p in sorted(points, key=lambda z: z[0], reverse=reverse):
        if groups and abs(p[0] / groups[-1][0][0] - 1) < tol:
            groups[-1].append(p)
        else:
            groups.append([p])
    out = []
    for g in groups:
        mas = sorted((p for p in g if p[1] == "ma"), key=lambda z: z[2])
        if mas:
            out.append((mas[0][0], "/".join(str(p[2]) for p in mas) + "-day average"))
        else:
            s = max(g, key=lambda z: z[2])
            out.append((s[0], f"swing {'low' if reverse else 'high'} {dm(s[2])}"))
    return out


def review(m: dict, info: dict | None = None, ccy: str = "USD", bench: str = "S&P 500", kind: str = "equity",
           pair: tuple[str, str] | None = None) -> dict:
    """Signals, view, levels and the plan text for the page, from `measures()` (+ optional consensus
    data: forwardPE, targetMeanPrice). kind="fx" for a currency pair (pair = (base, quote), e.g.
    ("CHF", "EUR")): six signals (no volume, no benchmark), 4-decimal levels, FX wording."""
    info = info or {}
    fx = kind == "fx"
    base, quote = pair or ("", ccy)
    dp, dp0 = (4, 4) if fx else (2, 0)                  # decimals for exact levels / rounded levels
    gdp = 1 if fx else 0                                # decimals for % gaps
    near = 0.3 if fx else 1.0                           # "at the average" band, %
    last, asof = m["last"], m["asof"]
    ma20, ma50, ma200 = m["ma20"][-1], m["ma50"][-1], m["ma200"][-1]
    perf, r = m["perf"], m["rsi"]
    dist = lambda lv: 100 * (lv / last - 1)                                       # noqa: E731
    days_to = lambda iso: (date.fromisoformat(iso) - date.fromisoformat(asof)).days  # noqa: E731

    def trend(ma, slope):
        gap = 100 * (last / ma - 1)
        text = f"{abs(gap):.{gdp}f}% {'above' if gap >= 0 else 'below'}, {'rising' if slope > 0 else 'falling'}"
        return text, "Positive" if gap > 0 and slope > 0 else "Negative" if gap < 0 and slope < 0 else "Neutral"

    def since(iso, up):
        w = "bullish" if up else "bearish"
        if not iso:
            return f"{w}, long-standing"
        return f"{w} since {dm(iso)}" if days_to(iso) > -60 else f"{w} since {mon(iso)}"

    gap20 = 100 * (last / ma20 - 1)
    short = ("at the average", "Neutral") if abs(gap20) <= near else \
        (f"{abs(gap20):.{gdp}f}% {'above' if gap20 > 0 else 'below'}", "Positive" if gap20 > 0 else "Negative")
    up = m["macd"] > m["macd_signal"]
    rsi_r = ((f"{r:.0f}, oversold", "Neutral") if r < 30 else (f"{r:.0f}, not oversold", "Neutral") if r < 45 else
             (f"{r:.0f}, balanced", "Neutral") if r < 55 else (f"{r:.0f}, firm", "Positive") if r < 70 else
             (f"{r:.0f}, overbought", "Neutral"))
    rel = perf["1M"][0] - (perf["1M"][1] or 0)
    vr = m["vol_ratio"]
    vol_r = (f"{vr:.1f}x normal, {'up' if m['last_up'] else 'down'} day", "Positive" if m["last_up"] else "Negative") \
        if vr >= 1.15 else (f"{vr:.1f}x normal", "Neutral")
    signals = [
        ("Long-term direction", "200-day avg", *trend(ma200, m["ma200_slope"])),
        ("Medium-term direction", "50-day avg", *trend(ma50, m["ma50_slope"])),
        ("Short-term direction", "20-day avg", *short),
        ("Trend structure", "50/200-day cross", since(m["ma_cross"], ma50 > ma200), "Positive" if ma50 > ma200 else "Negative"),
        ("Momentum", "MACD", f"{'up' if up else 'down'} since {dm(m['macd_cross'])}" if m["macd_cross"] else
         ("up" if up else "down"), "Positive" if up else "Negative"),
        ("Buying / selling pressure", "RSI 14", *rsi_r),
        ("Strength vs the market", f"vs {bench}, 1M", f"{rel:+.0f} pts", "Positive" if rel > 2 else "Negative" if rel < -2 else "Neutral"),
        ("Buyers' conviction" if m["last_up"] else "Sellers' conviction", "volume", *vol_r),
    ]
    if fx:                                              # no volume, and no index to compare a currency with
        signals = signals[:6]
    nsig = len(signals)
    npos = sum(s[3] == "Positive" for s in signals)
    nneg = sum(s[3] == "Negative" for s in signals)
    net = npos - nneg
    view = "bear" if net <= -3 else "bull" if net >= 3 else "neutral"

    below = [(d_, v) for d_, v in m["piv_lo"] if v < last]
    stop_d, stop = max(below) if below else (m["lo52_date"], m["lo52"])          # latest swing low under the price
    above = [(d_, v) for d_, v in m["piv_hi"] if v > last]
    swing = max(above)[1] if above else None                                      # latest swing high over the price
    mas = ((ma20, 20), (ma50, 50), (ma200, 200))
    tol = 0.003 if fx else 0.015
    res = _cluster([(v, "swing", d_) for d_, v in above if v < last * 1.3] + [(v, "ma", k) for v, k in mas if v > last],
                   False, tol)[:3]
    sup = _cluster([(v, "swing", d_) for d_, v in below if v > last * 0.75 and abs(v - stop) > 1e-9]
                   + [(v, "ma", k) for v, k in mas if v < last], True, tol)
    sup = [s for s in sup if s[0] > stop][:2] + [(stop, f"swing low {dm(stop_d)}")]
    stop_is_2y_low = abs(stop - m["lo2y"]) / stop < 0.01

    if view == "bear":
        zlo = res[0][0] if res else ma20
        zhi = swing if swing and swing > zlo else (res[1][0] if len(res) > 1 else zlo * 1.05)
        zone, zone_label = (zlo, zhi), "Exit zone"
    elif view == "neutral":
        zone, zone_label = (stop, swing or (res[0][0] if res else last * 1.05)), "Range"
    else:                                               # between the two nearest supports above the stop
        above_stop = [v for v, _ in sup if v > stop]
        zone = (above_stop[1], above_stop[0]) if len(above_stop) >= 2 else \
            (stop, above_stop[0]) if above_stop else (stop, max(ma20, stop * 1.01))
        zone_label = "Buy-on-dip zone"
    earn = m["earnings"] if m["earnings"] and days_to(m["earnings"]) >= 0 else None
    earn_soon = bool(earn and days_to(earn) <= 75)

    stop_txt = f"{ccy} {_num(stop, dp)} ({_pc(dist(stop))}), the last swing low" + (" and 2-year low" if stop_is_2y_low else "")
    if fx:
        return _fx_review(m, signals, npos, nneg, view, zone, zone_label, stop, stop_d, stop_is_2y_low, res, sup,
                          base, quote, stop_txt, dist)
    if view == "bear":
        holders = (f"Reduce into rebounds towards {ccy} {_num(zone[0], 0)}–{_num(zone[1], 0)} ({_pc(dist(zone[0]), 0)} to "
                   f"{_pc(dist(zone[1]), 0)}); exit on a daily close below {stop_txt}.")
        new_money = f"Wait. Re-assess above the 200-day average ({ccy} {_num(ma200, 0)}) or on a higher low with momentum turning up."
    elif view == "neutral":
        holders = (f"Hold while above {stop_txt}; reduce on a daily close below it. A close above {ccy} {_num(zone[1], 0)} "
                   f"({_pc(dist(zone[1]), 0)}) would turn the picture positive.")
        new_money = (f"Wait for a close above {ccy} {_num(zone[1], 0)}, or buy near {ccy} {_num(stop, 0)} with a tight stop"
                     + (f"; results on {dm(earn)} can break the range either way." if earn_soon else "."))
    else:
        holders = f"Hold and trail the stop at {stop_txt}." + (
            " RSI near 70: some profit-taking on strength is reasonable." if r >= 65 else "")
        new_money = (f"Buy on pullbacks into {ccy} {_num(zone[0], 0)}–{_num(zone[1], 0)} ({_pc(dist(zone[0]), 0)} to "
                     f"{_pc(dist(zone[1]), 0)}) rather than at the high" + (f"; results on {dm(earn)}." if earn_soon else "."))
    prot, rv = PROTECTION[view], m["rv3m"]
    coupons = "high coupons" if rv >= 40 else "decent coupons" if rv >= 28 else "low coupons on its own; better in a basket"
    structured = (f"~{rv:.0f}% vol: {coupons}. Protection at {prot}% or lower (~{ccy} {_num(prot / 100 * last, 0)})"
                  + (f", after the {dm(earn)} results." if earn_soon else "."))
    val = f"forward P/E {info['forwardPE']:.1f}x" if info.get("forwardPE") else ""
    tgt = info.get("targetMeanPrice")
    if tgt:
        val += ("; " if val else "") + (f"average analyst target {ccy} {_num(tgt, 0)}, below the price" if tgt < last
                                        else f"average analyst target {ccy} {_num(tgt, 0)} ({_pc(dist(tgt), 0)})")
    rel1y = perf["1Y"][0] - (perf["1Y"][1] or 0)
    why = (f"{npos} positive, {nneg} negative, {nsig - npos - nneg} neutral signals; {rel1y:+.0f} pts vs the {bench} over a "
           f"year" + (f"; {val}." if val else "."))
    return {
        "signals": signals, "positive": npos, "negative": nneg, "neutral": nsig - npos - nneg, "view": view,
        "zone": zone, "zone_label": zone_label, "stop": stop, "stop_date": stop_d, "stop_is_2y_low": stop_is_2y_low,
        "resistances": res, "supports": sup, "earnings": earn, "earnings_in": days_to(earn) if earn else None,
        "plan": [("Holders", holders), ("New money", new_money), ("Structured products", structured), ("Why", why)],
    }


def _fx_review(m, signals, npos, nneg, view, zone, zone_label, stop, stop_d, stop_is_2y_low, res, sup,
               base, quote, stop_txt, dist) -> dict:
    """The plan for a currency pair, from the point of view of the base currency (e.g. CHF in CHF/EUR)."""
    n4 = lambda x: _num(x, 4)                                                    # noqa: E731
    z = f"{quote} {n4(zone[0])}–{n4(zone[1])} ({_pc(dist(zone[0]))} to {_pc(dist(zone[1]))})"
    if view == "bear":
        zone_label = "Hedge zone"
        long_ = f"Hedge or reduce {base} exposure into rebounds towards {z}; fully on a daily close below {stop_txt}."
        buy = f"Wait. Re-assess above the 200-day average ({quote} {n4(m['ma200'][-1])}) or on a higher low."
    elif view == "neutral":
        long_ = (f"Hold while above {stop_txt}; hedge on a daily close below it. A close above {quote} {n4(zone[1])} "
                 f"({_pc(dist(zone[1]))}) would turn the picture positive.")
        buy = f"Wait for a close above {quote} {n4(zone[1])}, or build gradually near {quote} {n4(stop)}."
    else:
        long_ = f"Keep the {base} exposure; trail the stop at {stop_txt}."
        buy = f"Add on pullbacks into {z} rather than at the high."
    rv = m["rv3m"]
    coupons = "decent coupons" if rv >= 10 else "modest coupons" if rv >= 6 else "thin coupons"
    structured = (f"~{rv:.1f}% vol: {coupons} on FX-linked notes (e.g. dual-currency deposits). Set any conversion "
                  f"level beyond the stop ({quote} {n4(stop)}).")
    p1y = m["perf"]["1Y"][0]
    why = (f"{npos} positive, {nneg} negative, {len(signals) - npos - nneg} neutral signals; {base} "
           f"{'up' if p1y >= 0 else 'down'} {abs(p1y):.1f}% against the {quote} over a year.")
    return {
        "signals": signals, "positive": npos, "negative": nneg, "neutral": len(signals) - npos - nneg, "view": view,
        "zone": zone, "zone_label": zone_label, "stop": stop, "stop_date": stop_d, "stop_is_2y_low": stop_is_2y_low,
        "resistances": res, "supports": sup, "earnings": None, "earnings_in": None,
        "plan": [(f"Long {base}", long_), (f"Buying {base}", buy), ("Structured products", structured), ("Why", why)],
    }
