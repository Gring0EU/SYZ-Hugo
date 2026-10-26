"""Build Term Sheet Studio from the Advisory Workbench single-file build.

    python3 -I termsheet-studio/build_from_workbench.py path/to/G01_workbench_YYYY-MM-DD.html

Writes termsheet-studio/T01_termsheet_studio.html next to this script: the
workbench's Term Sheet module (Term sheet, Fact sheet, SP Event) as a
standalone page. Everything else -- Portfolio Screener, Structured Product
Screener, basket lab and optimiser, Excel export, simulator -- is left out.

What is kept from the workbench, unchanged unless a cut below says otherwise:
  * the house style sheet, minus the rules of the removed screens
  * the three screens' HTML and their four scripts (families, termsheet,
    factsheet, SP Event)
  * for the Fact sheet only: the market-data snapshot and the engine pieces it
    reads (util, data, universe, analytics, and the market functions match /
    basket / factsheet), answered in the page as the workbench does
The shared helpers (window.W) are rewritten here with only what the three
screens call. Every cut is an exact text replacement that must match once,
so a workbench change that moves the code fails the build loudly instead of
producing a half-working page.
"""
import base64
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "T01_termsheet_studio.html")
LOGO = os.path.join(HERE, "syz_logo.png")   # the orange Syz signature, transparent, 96 px high


def cut(text, old, new, what):
    """Replace `old` by `new` exactly once, or stop the build."""
    n = text.count(old)
    if n != 1:
        sys.exit(f"build: '{what}' matched {n} times, expected 1; the workbench changed, update this script")
    return text.replace(old, new)


def between(text, start, end, what, include_end=False):
    """The text from `start` up to (not including) `end`."""
    a = text.find(start)
    b = text.find(end, a + len(start)) if a >= 0 else -1
    if a < 0 or b < 0:
        sys.exit(f"build: could not find '{what}' in the workbench")
    return text[a:b + (len(end) if include_end else 0)]


def script(src, marker):
    """The body of the one <script> whose text contains `marker`."""
    hits = [s for s in re.findall(r"<script>(.*?)</script>", src, re.S) if marker in s]
    if len(hits) != 1:
        sys.exit(f"build: script '{marker}' found {len(hits)} times, expected 1")
    return hits[0]


def prune_css(css, used_text):
    """Drop the selectors whose classes nothing in the page uses (rules emptied that way go too)."""
    def unused(selector):
        return any(not re.search(r"(?<![\w-])" + re.escape(c) + r"(?![\w-])", used_text)
                   for c in re.findall(r"\.([a-zA-Z][\w-]*)", selector))

    def walk(text):
        out, i = [], 0
        while i < len(text):
            brace = text.find("{", i)
            if brace < 0:
                out.append(text[i:])
                break
            # the selector starts after the last rule end or comment before the brace
            head_start = max(text.rfind("}", i, brace), text.rfind("*/", i, brace) + 1, i - 1) + 1
            out.append(text[i:head_start])
            head = text[head_start:brace]
            depth, j = 1, brace + 1
            while depth and j < len(text):
                depth += {"{": 1, "}": -1}.get(text[j], 0)
                j += 1
            body = text[brace + 1:j - 1]
            if head.strip().startswith("@"):
                inner = walk(body)
                if inner.strip():
                    out.append(head + "{" + inner + "}")
            else:
                parts = [p for p in head.split(",") if not unused(p)]
                if parts:
                    out.append(",".join(parts) + "{" + body + "}")
            i = j
        return "".join(out)

    return re.sub(r"\n{3,}", "\n\n", walk(css))


def main(path):
    src = open(path, encoding="utf-8").read()

    # --- style: the house style minus the removed screens' rules -----------------------------
    css = between(src, "<style>", "</style>", "style sheet")[len("<style>"):]
    css = css.replace(between(css, "/* --- KPIs", "/* --- tables", "KPI styles"), "")
    css = css.replace(between(css, "/* --- bars (", "/* --- banner & busy", "bar chart styles"), "")
    css = css.replace(between(css, "/* --- basket ideas view", "/* --- term sheet card", "basket and saved-basket styles"), "")
    css = re.sub(r"\.subtabs? ?\{[^}]*\}\n|\.subtab[.:][^{]*\{[^}]*\}\n|\.idea-filters[^{]*\{[^}]*\}\n|\.kpis? [^{]*\{[^}]*\}\n|\.kpi b \{[^}]*\}\n", "", css)
    css += """
/* --- Term Sheet Studio ------------------------------------------------------ */
.module-btn small { display: block; font-size: 11px; font-weight: 300; color: #C9CCD6; }
.module-btn.is-active small { color: #FFF; }
.brand { display: flex; align-items: center; gap: 12px; padding: 10px 0; }
.brand img { height: 34px; width: auto; display: block; }
/* the 300px box was for pasting portfolio extracts: here a text box is as tall as its rows */
textarea { min-height: 0; }
/* a label whose text holds bold words reads as one line, with its box below */
.ev-strike-card .field { display: block; }
.ev-strike-card .field textarea { display: block; margin-top: 4px; }
"""

    # --- the three screens ------------------------------------------------------------------
    screens = between(src, '<section class="screen" data-screen="t-term">', '<div id="busy"', "Term Sheet screens")
    screens = screens.rstrip()
    screens = cut(screens, "</main>", "", "end of main")
    screens = cut(screens, '<section class="screen" data-screen="t-term">',
                  '<section class="screen is-active" data-screen="t-term">', "term sheet screen")
    screens = cut(screens, """      <button type="button" id="ts-to-lab" class="btn" title="Match the pricer's names and analyse them in the Basket lab">Open in basket lab</button>
      <button type="button" id="ts-from-lab" class="btn">Use basket lab names</button>
""", "", "basket lab buttons")
    screens = cut(screens, '<h2>SP Event</h2>', '<h2>Lifecycle events</h2>', "SP Event heading")
    # first use: no sample basket or coupon, the form waits for a pricer page or typed terms
    screens = cut(screens, """<textarea id="ts-names" rows="4">NVIDIA CORP
ASML HOLDING NV
TAIWAN SEMICONDUCTOR MANUFACTURING CO LTD</textarea>""",
                  """<textarea id="ts-names" rows="4" placeholder="e.g.&#10;NVIDIA CORP&#10;ASML HOLDING NV"></textarea>""", "sample names")
    screens = cut(screens, '<input type="number" id="ts-coupon" value="13.33" step="0.01">',
                  '<input type="number" id="ts-coupon" step="0.01" placeholder="from the pricer">', "sample coupon")

    # --- engine: only what the Fact sheet reads --------------------------------------------
    data_blob = between(src, '<script id="sp-data"', "</script>", "market-data snapshot", include_end=True)
    util = script(src, "Offline engine -- shared helpers")
    data = script(src, "Offline engine -- the market-data snapshot")
    universe = script(src, "port of syz_advisory/screener/universe.py")
    analytics = script(src, "port of syz_advisory/screener/analytics.py")
    market = script(src, "port of syz_advisory/structuring/market.py")
    simulate = script(src, "port of syz_advisory/structuring/simulate.py")

    # market: drop the theme screen and the lab's search; basket() keeps its common-dates helper
    market = market.replace(between(market, "  function names(u, lists)", "  function underlyingRow(", "theme screen helpers"), "")
    market = market.replace(between(market, "  function screen(lists, volNames)", "  function basket(symbols)", "theme screen"), "")
    market = market.replace(between(market, "  function search(q)", "  // Port of market.factsheet", "underlying search"), "")
    align = between(simulate, "  function align(histories, symbols)", "\n  }\n", "simulate.align", include_end=True)
    market = cut(market, "  function basket(symbols)",
                 "  // The dates every symbol has a close for, and the closes on them (from simulate.py).\n" + align + "\n  function basket(symbols)",
                 "basket")
    market = market.replace("SP.simulate.align(", "align(")
    market = cut(market, "SP.market = { screen: screen, basket: basket, search: search, match: match, matchOne: matchOne, factsheet: factsheet };",
                 "SP.market = { basket: basket, match: match, matchOne: matchOne, factsheet: factsheet };", "market exports")
    market = cut(market, "/* Offline engine -- port of syz_advisory/structuring/market.py: theme\n   scorecard, underlying screen and basket lab, on the frozen snapshot. */",
                 "/* Offline engine -- port of syz_advisory/structuring/market.py, the part the Fact sheet reads:\n   matching pricer names to symbols, and the basket's histories, correlation and volatility. */",
                 "market header")

    local = """
/* The in-page answer to the two requests the Fact sheet makes (the workbench's G01_run.py routes). */
(function () {
  "use strict";
  var SP = window.SP;
  var ROUTES = {
    "/products/match": function (b) { return SP.market.match(b.names); },
    "/products/factsheet": function (b) { return SP.market.factsheet(b.symbols); }
  };
  SP.local = {
    post: function (url, body) {
      var fn = ROUTES[url];
      if (!fn) return Promise.reject(new Error("Not available in Term Sheet Studio: " + url));
      return SP.data.ready().then(function () {
        return new Promise(function (resolve) { setTimeout(resolve, 30); });   // let the busy overlay paint
      }).then(function () { return fn(JSON.parse(JSON.stringify(body || {}))); });
    }
  };
})();
"""

    helpers = """
/* Term Sheet Studio -- shared helpers (window.W): the part of the workbench's helpers the three
   screens use: DOM, escaping, the in-page requests, the banner and busy overlay, file drops,
   selects and the tabs. */
(function () {
  "use strict";

  function $(sel) { return document.querySelector(sel); }
  function $all(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
  function esc(v) {
    return String(v == null ? "" : v).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  function post(url, body) { return window.SP.local.post(url, body); }

  function banner(text, ok) {
    var el = $("#banner");
    el.textContent = text || "";
    el.className = "banner" + (ok ? " ok" : "");
    el.hidden = !text;
    if (ok && text) setTimeout(function () { if (el.textContent === text) el.hidden = true; }, 7000);
  }
  var busyCount = 0;
  function busy(on, label) {
    busyCount = Math.max(0, busyCount + (on ? 1 : -1));
    $("#busy").hidden = busyCount === 0;
    if (on && label) $("#busy-label").textContent = label;
  }
  function run(label, promise) {
    busy(true, label);
    return promise.catch(function (e) { banner(e.message); throw e; })
      .then(function (x) { busy(false); return x; }, function (e) { busy(false); throw e; });
  }

  // multi: onFile gets every file dropped or picked (an array), else the first one only
  function wireDrop(zone, input, onFile, multi) {
    function give(list) { if (list.length) onFile(multi ? Array.prototype.slice.call(list) : list[0]); }
    ["dragenter", "dragover"].forEach(function (ev) {
      zone.addEventListener(ev, function (e) { e.preventDefault(); zone.classList.add("is-over"); });
    });
    ["dragleave", "drop"].forEach(function (ev) {
      zone.addEventListener(ev, function () { zone.classList.remove("is-over"); });
    });
    zone.addEventListener("drop", function (e) {
      e.preventDefault();
      give(e.dataTransfer.files);
    });
    input.addEventListener("change", function () { give(input.files); input.value = ""; });
  }
  // A file dropped outside a drop zone must not replace the page.
  ["dragover", "drop"].forEach(function (ev) { window.addEventListener(ev, function (e) { e.preventDefault(); }); });

  function fillSelect(el, values, allLabel) {
    var keep = el.value;
    el.innerHTML = (allLabel != null ? '<option value="">' + esc(allLabel) + "</option>" : "") +
      values.map(function (v) {
        var val = typeof v === "object" ? v.value : v, lab = typeof v === "object" ? v.label : v;
        return '<option value="' + esc(val) + '">' + esc(lab) + "</option>";
      }).join("");
    if (keep && $all("option", el).some(function (o) { return o.value === keep; })) el.value = keep;
  }

  // --- tabs: one per screen ----------------------------------------------------------------
  var hooks = {};
  function show(screen) {
    $all(".module-btn").forEach(function (b) {
      var on = b.dataset.screen === screen;
      b.classList.toggle("is-active", on);
      b.setAttribute("aria-selected", on ? "true" : "false");
    });
    $all(".screen").forEach(function (s) { s.classList.toggle("is-active", s.dataset.screen === screen); });
    window.scrollTo(0, 0);
    if (hooks[screen]) hooks[screen]();
  }
  function onShow(screen, fn) { hooks[screen] = fn; }
  $all(".module-btn").forEach(function (b) { b.addEventListener("click", function () { show(b.dataset.screen); }); });
  try { localStorage.removeItem("ts-studio.screen"); } catch (e) { /* earlier builds remembered the tab */ }

  // The date of the market data in the page (Yahoo Finance, refreshed by refresh_market_data.py).
  window.SP.data.ready().then(function (raw) {
    var d = /^(\\d{4})-(\\d{2})-(\\d{2})(?: (\\d{2}:\\d{2}))?/.exec(raw.asof || "");
    if (!d) return;
    var month = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][+d[2] - 1];
    $("#asof").textContent = "Market data " + +d[3] + " " + month + " " + d[1] + (d[4] ? " " + d[4] : "");
    $("#asof").title = "Yahoo Finance quotes and daily closes, as of " + raw.asof;
  }).catch(function () { /* no data: the Fact sheet says so when it is built */ });

  window.W = { $: $, $all: $all, esc: esc, post: post, banner: banner, busy: busy, run: run,
               wireDrop: wireDrop, fillSelect: fillSelect, show: show, onShow: onShow };
})();
"""

    families = script(src, "The LYNQS product families, shared by the Term sheet and the Fact sheet")
    termsheet = script(src, "Term sheet: the LYNQS pricer's parameters")
    factsheet = script(src, "Fact sheet: a client-ready product proposal")
    event = script(src, "SP Event: the client communication when a structured product ends")

    # term sheet: no basket lab here; the name matching stays, it feeds the Fact sheet's market data
    termsheet = cut(termsheet, """  // The pricer's names to Yahoo symbols in one call (/products/match: Bloomberg ticker, Core List name,
  // index code, then a Yahoo search), shown under the underlyings and reused by "Open in basket lab".""",
                    """  // The pricer's names to symbols in one call (/products/match: Bloomberg ticker, Core List name,
  // index code, then the snapshot's quote names), shown under the underlyings and used by the Fact sheet.""",
                    "name matching comment")
    termsheet = cut(termsheet, """'<b>not found</b> <small class="muted">add it in the lab with its search</small>'""",
                    """'<b>not found</b> <small class="muted">not in the market data: the fact sheet shows its terms only</small>'""",
                    "not-found hint")
    termsheet = termsheet.replace(between(termsheet, '  $("#ts-to-lab").addEventListener("click"', '  $("#ts-reset-title")', "basket lab handlers"), "")
    clean = ("  // Every visit starts clean: the last session's quote is not brought back.\n"
             "  try { localStorage.removeItem(STORE); } catch (e) { /* storage blocked: nothing to clear */ }\n")
    termsheet = cut(termsheet, "  restore();\n  render();\n", clean + "  render();\n", "term sheet restore")
    factsheet = cut(factsheet, "\n  restore();\n", "\n" + clean.replace("quote", "fact sheet settings"), "fact sheet restore")
    if "labBasket" in termsheet or "openLab" in termsheet or "ts-to-lab" in termsheet:
        sys.exit("build: basket lab code left in the term sheet")

    head = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Term Sheet Studio</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Nunito:wght@300;400;700&display=swap">
<!-- Built by build_from_workbench.py from %s: the workbench's Term Sheet module on its own. -->
<style>%s</style>
</head>
<body>

<header class="topbar">
  <div class="brand"><img src="data:image/png;base64,%s" alt="SYZ"><span>Term Sheet Studio</span></div>
  <nav class="modules" role="tablist" aria-label="Tools">
    <button type="button" class="module-btn is-active" role="tab" aria-selected="true" data-screen="t-term">Term sheet <small>Format the card and table</small></button>
    <button type="button" class="module-btn" role="tab" aria-selected="false" data-screen="t-fact">Fact sheet <small>Client proposal</small></button>
    <button type="button" class="module-btn" role="tab" aria-selected="false" data-screen="t-event">Lifecycle events <small>Autocall, expiry, delivery emails</small></button>
  </nav>
  <div class="actions"><span id="asof" class="asof"></span></div>
</header>
<div id="banner" class="banner" hidden></div>

<main>

""" % (os.path.basename(path), css, base64.b64encode(open(LOGO, "rb").read()).decode("ascii"))

    scripts = (util, data, universe, analytics, market, local, helpers, families, termsheet, factsheet, event)
    head = head.replace(css, prune_css(css, screens + "".join(scripts) + head.replace(css, "")))

    page = (head + screens + "\n\n</main>\n\n" +
            '<div id="busy" class="busy" hidden><div class="busy-box" id="busy-label">Working…</div></div>\n\n' +
            data_blob + "\n" +
            "".join(f"<script>{s}</script>\n" for s in
                    scripts) +
            "</body>\n</html>\n")
    for gone in ("Portfolio Screener", "Basket lab", "basket-lab", "SP.engine", "SP.workbook", "SP.simulate"):
        if gone in page.replace("basket lab", ""):
            print(f"build: note, '{gone}' still appears in the page")
    open(OUT, "w", encoding="utf-8").write(page)
    print(f"wrote {OUT} ({len(page) / 1e6:.1f} MB)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
