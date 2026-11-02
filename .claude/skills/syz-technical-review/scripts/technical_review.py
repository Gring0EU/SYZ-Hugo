"""P02 -- Technical review: a one-page SYZ PDF per stock, in the layout of the G01 1y/3y proposal PDFs.

For each ticker: two years of daily prices, eight plain-English signals (direction, trend
structure, momentum, buying/selling pressure, strength vs the market, conviction), a verdict
(exit / reduce, neutral / hold within the range, positive / buy on pullbacks), the levels that
matter (exit or buy-on-dip zone, stop level, resistances, supports), a one-year chart and the
performance against a benchmark, with a FinSA-style disclaimer. The aim is to spot opportunities,
including exiting a position to avoid further losses.

    .\\.venv\\Scripts\\python apps\\P02\\P02_run.py AAPL BKNG ORCL --open
    .\\.venv\\Scripts\\python apps\\P02\\P02_run.py NESN.SW --bench ^SSMI "SMI"

Also shipped in the syz-technical-review skill (P02_package_skill.py) as scripts/technical_review.py.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKAGED = (HERE / "syz_advisory").is_dir()          # inside the skill: the modules sit beside this file
if PACKAGED:
    os.environ.setdefault("SYZ_DATA", str(Path(tempfile.gettempdir()) / "syz-technical-review"))
    os.environ.setdefault("SYZ_FONTS", str(HERE / "fonts"))
    sys.path.insert(0, str(HERE))
    LOGO = HERE.parent / "assets" / "syz_logo.png"
else:
    sys.path.insert(0, str(HERE.parents[1] / "src"))
    LOGO = HERE.parents[1] / "apps" / "S00" / "S00_logo.png"

from syz_advisory import brand, config, pdflayout, pdfwriter, technicals  # noqa: E402
from syz_advisory.marketdata import YahooClient  # noqa: E402

log = config.get_logger("P02")
P, INK = brand.PALETTE, brand.INK
MUTED, GRID, AXIS = pdflayout.MUTED, pdflayout.GRID, pdflayout.AXIS
ORANGE, BEAR, BULL, GOLD = P["tiger_orange"], P["mulberry_pink"], P["mint_green"], P["gold_yellow"]
TONE = {"Positive": BULL, "Neutral": GOLD, "Negative": BEAR}
VIEW = {"bear": ("exit / reduce", BEAR, "Verdict: exit or reduce, preferably into a rebound", ORANGE),
        "neutral": ("neutral / hold within the range", ORANGE, "Verdict: no clear trend, hold within the range", GOLD),
        "bull": ("positive / buy on pullbacks", BULL, "Verdict: positive trend, hold and buy on pullbacks", BULL)}
SUFFIXES = (" Inc.", " Inc", " Corporation", " Corp.", " Holdings", " plc", " PLC", " N.V.", " S.A.", " SE", " AG", " Ltd")
M = 40                                                 # page margin, as the G01 proposal PDFs
DISCLAIMER = ("For information purposes only. This technical analysis is based on past prices; it is not investment "
              "advice, a recommendation, an offer or financial research within the meaning of FinSA, and does not take "
              "any individual situation into account. Past performance is not a reliable indicator of future results; "
              "capital may be lost. Accuracy not guaranteed. Not to be distributed without the consent of SYZ.")


def fonts() -> tuple[Path, Path]:
    found = (pdfwriter.find_fonts([("OpenSans-Regular.ttf", "OpenSans-Bold.ttf")])
             or pdfwriter.find_fonts(pdfwriter.NUNITO_SANS) or pdfwriter.find_fonts())
    if not found:
        raise SystemExit("No TrueType font found: set SYZ_FONTS to a folder with NunitoSans-Regular/Bold.ttf")
    return found


def short_name(name: str) -> str:
    for s in SUFFIXES:
        name = name.replace(s, "")
    return name.strip(" ,")


def nice_step(span: float, ticks: int = 5) -> float:
    """1, 2, 2.5 or 5 times a power of ten, giving about `ticks` gridlines; works for FX rates too."""
    raw = span / ticks
    e = 10 ** math.floor(math.log10(raw))
    return next(f * e for f in (1, 2, 2.5, 5, 10) if raw <= f * e)


def dmy(iso: str) -> str:
    return f"{iso[8:10]}.{iso[5:7]}.{iso[:4]}"


def num(x: float, dp: int = 2) -> str:
    return f"{x:,.{dp}f}"


def pc(x: float, dp: int = 1) -> str:
    return f"{x:+.{dp}f}%"


def fetch(client: YahooClient, symbol: str, bench: str) -> tuple[dict, dict]:
    bars = client.chart(symbol, "2y", "1d", max_age=None if client.offline else 0)
    bench_bars = client.chart(bench, "2y", "1d", max_age=None if client.offline else 0)
    info = client.info(symbol, max_age=None if client.offline else 0) or {}
    quote = client.quotes([symbol], max_age=None if client.offline else 0).get(symbol) or {}
    fx = (quote.get("type") or info.get("quoteType")) == "CURRENCY"
    # plain closes (not dividend-adjusted), as on a trader's chart: levels match the quoted prices
    rows = [{"date": b["date"], "close": b["close"], "high": b["high"], "low": b["low"], "volume": b["volume"]} for b in bars]
    m = technicals.measures(rows, [] if fx else [{"date": b["date"], "close": b["close"]} for b in bench_bars],
                            quote.get("earnings"))
    name = info.get("longName") or quote.get("name") or symbol
    meta = {"name": name, "ccy": info.get("currency") or quote.get("currency") or "USD",
            "forwardPE": info.get("forwardPE"), "targetMeanPrice": info.get("targetMeanPrice"),
            "kind": "fx" if fx else "equity", "pair": tuple(name.split("/"))[:2] if fx and "/" in name else None}
    return m, meta


def render(symbol: str, name: str, ccy: str, bench_name: str, m: dict, rv: dict, chart_h: float, path: Path | None):
    """Draw the page; returns (end of content, top of the disclaimer)."""
    reg, bold = fonts()
    doc = pdfwriter.Document(f"{name} - technical review", reg, bold)
    pw, ph = pdfwriter.A4
    cw = pw - 2 * M
    pg = doc.page()
    view = rv["view"]
    signal_txt, sig_col, verdict_title, zone_col = VIEW[view]
    last, asof, close, dates = m["last"], m["asof"], m["close"], m["dates"]
    ma20, ma50, ma200 = m["ma20"][-1], m["ma50"][-1], m["ma200"][-1]
    stop, zone, zone_label = rv["stop"], rv["zone"], rv["zone_label"]
    dist = lambda lv: 100 * (lv / last - 1)                                   # noqa: E731
    fx = rv.get("kind") == "fx"
    N = lambda x: num(x, 4 if fx else 2)                                      # noqa: E731  exact level
    N0 = lambda x: num(x, 4 if fx else 0)                                     # noqa: E731  rounded level
    nsig = len(rv["signals"])
    if fx:
        signal_txt ={"bear": f"{name.split('/')[0]} weakening / hedge", "neutral": "neutral / range",
                      "bull": f"{name.split('/')[0]} strengthening"}[view]
        verdict_title = {"bear": f"Verdict: {name.split('/')[0]} in a downtrend, hedge into rebounds",
                         "neutral": "Verdict: no clear trend, trade the range",
                         "bull": f"Verdict: {name.split('/')[0]} in an uptrend, add on pullbacks"}[view]
    title = f"{name}: technical review" if fx else f"{name} ({symbol}): technical review"

    def para(y, text, size=7.8):
        for line in pg.wrap(text, size, cw):
            y += size * 1.4
            pg.text(M, y, line, size, False, MUTED)
        return y

    def section(y, title):
        pg.line(M, y, M + cw, y, INK, 1.2)
        pg.text(M, y + 18, title, 12, True, INK)
        return y + 18

    # title block, as the proposal PDFs, with the logo
    logo = LOGO.read_bytes()
    lw, lh = pdfwriter.decode_png(logo)[:2]
    pg.image(logo, pw - M - 40 * lw / lh, 34, 40 * lw / lh, 40)
    pg.text(M, 66, pg.fit(title, 20, cw - 60, True), 20, True, INK)
    pg.text(M, 84, f"Technical signal: {signal_txt}  ·  {'rates' if fx else 'prices'} as of {dmy(asof)}", 10, True, sig_col)
    y = 114
    hi_gap = 100 * (last / m["hi52"] - 1)
    p1y = m["perf"]["1Y"]
    kpis = [(f"{ccy} {N(last)}", f"Last close ({pc(100 * (last / m['prev'] - 1), 2 if fx else 1)} on the day)", INK),
            (pc(hi_gap, 1 if fx else 0) if hi_gap < -0.5 else "at the high",
             f"From the 52-week high ({ccy} {N0(m['hi52'])}, {technicals.mon(m['hi52_date'])})", BEAR if hi_gap < -15 else INK),
            (pc(p1y[0], 1 if fx else 0), "1-year change" if fx else f"1-year return; {bench_name} {pc(p1y[1] or 0, 0)}",
             BEAR if p1y[0] < 0 else BULL),
            (f"{rv['positive']} of {nsig}", f"Technical signals positive ({rv['negative']} negative, {rv['neutral']} neutral)", sig_col),
            (pc(dist(stop)), f"To the stop level, {ccy} {N(stop)} (last swing low)", INK)]
    for i, (v, label, col) in enumerate(kpis):
        kx = M + i * cw / 5
        pg.text(kx, y, v, 13, True, col)
        for k, line in enumerate(pg.wrap(label, 7, cw / 5 - 8)):
            pg.text(kx, y + 11 + 8.5 * k, line, 7, colour=MUTED)
    y += 36

    # verdict box
    y = section(y, verdict_title)
    top, lab_w = y + 8, 92
    blocks = [(k, pg.wrap(v, 7.8, cw - lab_w - 20)) for k, v in rv["plan"]]
    box_h = 8 + sum(11 * len(ls) + 5 for _, ls in blocks)
    pg.rect(M, top, cw, box_h, fill=brand.flatten(sig_col, 0.10))
    pg.rect(M, top, 3, box_h, fill=sig_col)
    yy = top + 4
    for k, ls in blocks:
        pg.text(M + 12, yy + 10, k, 7.8, True, INK)
        for ln in ls:
            yy += 11
            pg.text(M + 12 + lab_w, yy - 1, ln, 7.8, colour=INK)
        yy += 5
    y = top + box_h + 14

    # chart
    y = section(y, "One year of the rate, with the levels that matter" if fx else "One year of price, with the levels that matter")
    unit = f"{ccy} per {name.split('/')[0]}" if fx else ccy
    y = para(y, f"Daily closes, {unit}. Shaded band: {zone_label.lower()}. Pink line: the stop level (last swing low).", 7.5)
    y += 14
    lx = M
    for col, dash, lab in ((INK, None, name), (ORANGE, None, "50-day"), (INK, [3, 2], "200-day")):
        pg.line(lx, y - 2.5, lx + 12, y - 2.5, col, 2 if not dash else 1.2, dash)
        lx += 16 + pg.text(lx + 16, y, lab, 7.5, colour=INK) + 14
    y += 14
    left, right, bottom = M + 30, M + cw - 104, y + chart_h - 14
    vals = close + [v for v in m["ma200"] + m["ma50"] if v] + [stop, zone[0], zone[1]]
    step = nice_step(max(vals) - min(vals))
    lo, hi = step * int(min(vals) * 0.98 / step), step * (int(max(vals) * 1.02 / step) + 1)
    n = len(close)
    X = lambda i: left + (right - left) * i / (n - 1)                         # noqa: E731
    Y = lambda v: y + (bottom - y) * (hi - v) / (hi - lo)                     # noqa: E731
    pg.rect(left, Y(zone[1]), right - left, Y(zone[0]) - Y(zone[1]), fill=brand.flatten(zone_col, 0.16))
    adp = max(0, -math.floor(math.log10(step) + 1e-9))                     # axis decimals from the tick step
    v = lo
    while v <= hi + 1e-9:
        pg.line(left, Y(v), right, Y(v), GRID, 0.5)
        pg.text(left - 4, Y(v) + 2.5, f"{v:,.{adp}f}", 6.5, colour=MUTED, anchor="end")
        v += step
    first = {}
    for i, d_ in enumerate(dates):
        first.setdefault(d_[:7], i)
    for ym, i in list(first.items())[1::2]:
        pg.text(X(i), y + chart_h - 3, technicals.mon(ym + "-01"), 6.5, colour=MUTED, anchor="middle")
    pg.line(left, bottom, right, bottom, AXIS, 0.6)
    p200 = [(X(i), Y(v)) for i, v in enumerate(m["ma200"]) if v is not None]
    for a, b in zip(p200[::2], p200[1::2]):
        pg.line(a[0], a[1], b[0], b[1], INK, 1.0)
    pg.polyline([(X(i), Y(v)) for i, v in enumerate(m["ma50"]) if v is not None], ORANGE, 1.1)
    pg.polyline([(X(i), Y(v)) for i, v in enumerate(close)], INK, 1.4)
    pg.line(left, Y(stop), right + 4, Y(stop), BEAR, 1.1, [4, 3])
    pg.circle(X(n - 1), Y(last), 2.8, fill=INK if view == "neutral" else sig_col)
    zone_tag = f"{zone_label} {N0(zone[0])}–{N0(zone[1])}" if not fx else f"{zone_label}"
    tags = [(zone[1], zone_tag, sig_col if view != "neutral" else ORANGE),
            (ma200, f"200-day {N0(ma200)}", INK), (last, f"Last {N(last)}", INK), (stop, f"Stop {N(stop)}", BEAR)]
    used: list[float] = []
    for val, lab, col in sorted(tags, key=lambda z: -z[0]):
        ty = Y(val) + 2.5
        while any(abs(ty - u) < 9 for u in used):
            ty += 9
        used.append(ty)
        pg.text(right + 7, ty, lab, 7, True, col)
    il, ih = close.index(min(close)), close.index(max(close))
    pg.text(X(il), Y(close[il]) + 11, f"low {technicals.mon(dates[il])}", 6.5, True, MUTED, "middle")
    if ih < n - 8:
        pg.text(X(ih), Y(close[ih]) - 5, f"high {technicals.mon(dates[ih])}", 6.5, True, MUTED, "middle")
    y += chart_h + 22

    # signals and levels
    y = section(y, "Signals and levels") + 8
    half = (cw - 16) / 2
    sig_w, st_w = 128, 40
    cols = [("Signal", sig_w, "start"), ("Reading", half - sig_w - st_w, "start"), ("", st_w, "end")]
    end_l = pdflayout.table(pg, M, y, cols, [[a, r, (s, TONE[s], True)] for a, _, r, s in rv["signals"]], size=7.0, row_h=12)
    for k, (a, tech, _, _) in enumerate(rv["signals"]):           # technical name, small and grey, after the plain name
        x0 = M + 3 + pg.width(a, 7.0) + 3
        pg.text(x0, y + 23 + 12 * k, pg.fit(f"({tech})", 5.8, M + sig_w - 3 - x0), 5.8, colour=MUTED)
    role_r = lambda v: (zone_label if view == "bear" and zone[0] - 1e-6 <= v <= zone[1] + 1e-6 else   # noqa: E731
                        "Trend reversal" if view == "bear" and abs(v - ma200) < 1e-6 else
                        "Breakout level" if view == "neutral" and abs(v - zone[1]) < 1e-6 else "Resistance")
    role_s = lambda v: ("Exit regardless" if view == "bear" and abs(v - stop) < 1e-6 else             # noqa: E731
                        "Stop level" if abs(v - stop) < 1e-6 else
                        "Buy-on-dip zone" if view == "bull" and zone[0] - 1e-6 <= v <= zone[1] + 1e-6 else "Support")
    rows = [] if rv["resistances"] else [["No resistance", "at the 52-week high", "", ""]]
    for v, what in reversed(rv["resistances"]):
        rows.append([role_r(v), what, N(v), (pc(dist(v)), INK, True)])
    rows.append([("Last close", None, True), dmy(asof), (N(last), None, True), ""])
    for v, what in rv["supports"]:
        if abs(v - m["lo2y"]) / v < (0.002 if fx else 0.01):
            what = what.replace("swing low", "2-year low")
        rows.append([role_s(v), what, N(v), (pc(dist(v)), BEAR if abs(v - stop) < 1e-6 else INK, True)])
    rows.append(["Daily range", "ATR 14 days", N(m["atr"]), f"±{100 * m['atr'] / last:.{2 if fx else 1}f}%"])
    rows.append(["Realised vol", "3 months, annualised", f"{m['rv3m']:.1f}%", ""])
    if not fx:
        e = rv["earnings"]
        rows.append(["Next results", "estimated", dmy(e) if e else "n/a", f"in {rv['earnings_in']} days" if e else ""])
    lcols = [("Level", 76, "start"), ("What", half - 76 - 54 - 42, "start"), (ccy, 54, "end"), ("vs last", 42, "end")]
    end_r = pdflayout.table(pg, M + half + 16, y, lcols, rows, size=7.0, row_h=12)
    y = max(end_l, end_r) + 18

    # performance
    y = section(y, "Performance" if fx else f"Performance against the {bench_name}") + 8
    perf = m["perf"]
    pcols = [("", 110, "start")] + [(k, (cw - 110) / 5, "end") for k in perf]
    prow = [[(name, None, True)] + [(pc(a, 2 if fx else 1), BEAR if a < 0 else BULL, True) for a, _ in perf.values()]]
    if not fx:
        prow += [[bench_name] + [pc(b) if b is not None else "–" for _, b in perf.values()],
                 ["Difference (pts)"] + [(f"{a - (b or 0):+.1f}", BEAR if a < (b or 0) else BULL, False) for a, b in perf.values()]]
    y = pdflayout.table(pg, M, y, pcols, prow, size=7.2, row_h=12)

    # important information + footer
    text = ((f"Daily closing rates to {dmy(asof)}. " if fx else
             f"Daily closing prices to {dmy(asof)}; consensus data from market data providers; results date estimated. ")
            + DISCLAIMER)
    lines = pg.wrap(text, 6.0, cw)
    dy = ph - 32 - 7.6 * len(lines) - 12
    pg.line(M, dy - 6, M + cw, dy - 6, GRID, 0.6)
    pg.text(M, dy + 3, "Important information", 6.8, True, INK)
    for i, line in enumerate(lines):
        pg.text(M, dy + 12 + 7.6 * i, line, 6.0, colour=MUTED)
    pg.text(M, ph - 22, f"SYZ  ·  Technical review  ·  {name if fx else f'{name} ({symbol})'}  ·  {dmy(asof)}", 6.5, colour=MUTED)
    pg.text(pw - M, ph - 22, "1 / 1", 6.5, colour=MUTED, anchor="end")
    if path:
        doc.save(path)
    return y, dy


def build(symbol: str, client: YahooClient, out_dir: Path, bench: str, bench_name: str, name: str | None = None,
          story: str | None = None) -> Path:
    m, meta = fetch(client, symbol, bench)
    rv = technicals.review(m, meta, meta["ccy"], bench_name, meta["kind"], meta["pair"])
    rv["kind"] = meta["kind"]
    if story:                                       # the catalysts, written from the news, lead the verdict box
        rv["plan"] = [("What's driving it", story.strip())] + [p for p in rv["plan"] if p[0] != "Why"]
    name = name or short_name(meta["name"])
    for h in range(175, 115, -5):                  # tallest chart that leaves room above the disclaimer
        end, dy = render(symbol, name, meta["ccy"], bench_name, m, rv, h, None)
        if end < dy - 10:
            break
    out = out_dir / f"P02_technical_{symbol.replace('=X', '').replace('^', '').replace('.', '_')}_{m['asof']}.pdf"
    render(symbol, name, meta["ccy"], bench_name, m, rv, h, out)
    print(f"Wrote {out}")
    d = 4 if meta["kind"] == "fx" else 2
    print(f"  {name} ({symbol}): {VIEW[rv['view']][0] if d == 2 else rv['view']} ({rv['positive']} positive, "
          f"{rv['negative']} negative, {rv['neutral']} neutral); last {meta['ccy']} {num(m['last'], d)}; "
          f"{rv['zone_label'].lower()} {num(rv['zone'][0], d)}–{num(rv['zone'][1], d)}; stop {num(rv['stop'], d)}"
          + (f"; results {dmy(rv['earnings'])} (estimated)" if rv["earnings"] else ""))
    for k, v in rv["plan"]:
        print(f"    {k}: {v}")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("tickers", nargs="+", help="Yahoo symbols, e.g. AAPL ORCL NESN.SW")
    parser.add_argument("--bench", nargs=2, metavar=("SYMBOL", "NAME"), default=["^GSPC", "S&P 500"],
                        help="benchmark for relative strength (default ^GSPC 'S&P 500')")
    parser.add_argument("--name", help="display name (one ticker only)")
    parser.add_argument("--out-dir", type=Path, help="default data/P02/out, or /mnt/user-data/outputs on claude.ai")
    parser.add_argument("--story", type=Path, help="JSON {TICKER: 'two or three sentences on the catalysts'}: "
                                                   "shown as 'What\\'s driving it' in the verdict box")
    parser.add_argument("--news", action="store_true", help="print the latest headlines per ticker and stop")
    parser.add_argument("--offline", action="store_true", help="cached prices only")
    parser.add_argument("--open", action="store_true", help="open the PDFs (Windows)")
    args = parser.parse_args()
    client = YahooClient(cache_path=config.DATA / "P02" / "cache" / "marketdata.json", offline=args.offline)
    if args.news:
        for t in args.tickers:
            print(f"===== {t.upper()}")
            for n in client.news(t.upper(), 20):
                print(f"{n['date']} | {n['publisher']} | {n['title']}")
        return
    stories = {k.upper(): v for k, v in json.loads(args.story.read_text(encoding="utf-8")).items()} if args.story else {}
    out_dir = args.out_dir or (Path("/mnt/user-data/outputs") if PACKAGED and Path("/mnt/user-data/outputs").is_dir()
                               else config.outputs("P02"))
    out_dir.mkdir(parents=True, exist_ok=True)
    done = []
    for t in args.tickers:
        try:
            done.append(build(t.upper(), client, out_dir, args.bench[0], args.bench[1],
                              args.name if len(args.tickers) == 1 else None, stories.get(t.upper())))
        except Exception as exc:                    # one bad ticker must not stop the others
            print(f"WARNING {t}: {exc}")
    client.save()
    if args.open and hasattr(os, "startfile"):
        for f in done:
            os.startfile(f)  # noqa: S606 -- Windows only


if __name__ == "__main__":
    main()
