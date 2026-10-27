"""Lifecycle events: how the case is decided at the final fixing (applied by build_from_workbench.py).

The workbench decided between case 2 (100% back) and case 3 (delivery) on the strike alone,
and read a LYNQS event that says "Share to Deliver: -" / "Number of Shares: -" as a delivery.
A barrier reverse convertible is only delivered when the barrier was hit AND the worst
underlying ends below its strike, so a product whose barrier held is repaid at 100% even
below the strike. These cuts put that rule in one place, outcome(), and use it for the
product page, the pasted Performance table, the strike panel and the email wording. What the
page states (Cash Redemption, or shares to deliver) still wins; the prices cross-check it.
"""


def apply(event, cut):
    # --- the levels: barrier price and distance beside the strike's ----------------------------
    event = cut(event, """    u.below = u.dist != null ? u.dist < 0 : null;
    return u;
  }""", """    u.below = u.dist != null ? u.dist < 0 : null;
    if (u.bdist == null && u.price != null && u.barrier) u.bdist = +(100 * (u.price / u.barrier - 1)).toFixed(2);
    u.belowBarrier = u.bdist != null ? u.bdist < 0 : null;
    return u;
  }
  // A field the page leaves at "-" or "N/A" says nothing.
  function given(v) { return v != null && !/^\\s*(?:[-–]|n\\/?a)?\\s*$/i.test(String(v)); }
  // The barrier, from the page: its level and type, and whether it was hit ("Barrier Hit: Not Hit").
  // A European barrier is observed at the final fixing only, so the final prices settle it when the
  // page does not; an American one is watched every day, which only the page's flag can tell.
  function barrierFacts(f, event, unders, head) {
    var flag = given(event["barrier hit"]) ? event["barrier hit"] : given(f["barrier hit"]) ? f["barrier hit"] : "";
    var hit = /^\\s*(?:yes|hit|touched|breached)\\b/i.test(flag) ? true : /^\\s*(?:no|not)\\b/i.test(flag) ? false : null;
    var fromHead = /Barrier\\s*\\(\\s*([\\d.]+)\\s*%\\s*\\)/i.exec(head || "");
    var level = num(f["barrier level"]) != null ? num(f["barrier level"]) : fromHead ? parseFloat(fromHead[1]) : null;
    var priced = unders.filter(function (u) { return u.barrier != null && u.price != null; });
    var type = f["barrier type"] || "", source = flag ? "the page: Barrier Hit " + flag : "", conflict = "";
    var under = priced.filter(function (u) { return u.belowBarrier; }).map(function (u) { return u.name; });
    // a price below the barrier is a hit, European (observed at the final fixing) or American (any close)
    if (under.length) {
      if (hit === false) conflict = "the page says the barrier was not hit, but " + under.join(", ") + " closed below it";
      hit = true; source = under.join(", ") + " below the barrier";
    } else if (hit == null && /europ/i.test(type) && priced.length === unders.length && priced.length) {
      hit = false; source = "the final prices, all above the European barrier";
    }
    return { product: level != null || priced.length > 0 || /barrier/i.test(f["product type"] || ""), level: level, type: type, hit: hit, source: source, conflict: conflict };
  }
  // At the final fixing: 100% back in cash, unless the worst underlying ends below its strike AND,
  // on a barrier product, the barrier was hit. -> { case: "expiry" | "delivery" | null (cannot tell), why }
  function outcome(unders, b, finalBelow) {
    var below = unders.filter(function (u) { return u.below; }).map(function (u) { return u.name; });
    var belowStrike = finalBelow != null ? finalBelow : below.length > 0;
    var bl = b.level != null ? " (" + pct(b.level, 0) + (b.type ? ", " + b.type.toLowerCase() : "") + ")" : "";
    if (!belowStrike) return { case: "expiry", why: "all underlyings at or above the strike" };
    var who = below.length ? below.join(", ") : "the final fixing";
    if (!b.product) return { case: "delivery", why: who + " below the strike, and no barrier" };
    if (b.hit === false) return { case: "expiry", why: who + " below the strike, but the barrier" + bl + " was not hit" };
    if (b.hit === true) return { case: "delivery", why: who + " below the strike and the barrier" + bl + " was hit" };
    return { case: null, why: who + " below the strike: the barrier" + bl + " decides, and the page does not say whether it was hit" };
  }""", "vsStrike barrier")

    # --- the pasted table: the barrier column too -----------------------------------------------
    event = cut(event, """    var at = Math.max(0, cols.findIndex(function (c) { return /^strike/.test(c); })), n = Math.max(cols.length, 1);""",
                """    var at = Math.max(0, cols.findIndex(function (c) { return /^strike/.test(c); })), n = Math.max(cols.length, 1);
    var bat = cols.findIndex(function (c) { return /^barrier/.test(c); });
    var blevel = /Barrier\\s*\\(\\s*([\\d.]+)\\s*%\\s*\\)/i.exec(text);""", "pasted barrier column")
    event = cut(event, """                          perf: pcts[0] ? num(pcts[0]) : null, dist: pcts[1 + at] ? num(pcts[1 + at]) : null }));
    }
    return { level: level ? parseFloat(level[1]) : null, underlyings: out };""",
                """                          perf: pcts[0] ? num(pcts[0]) : null, dist: pcts[1 + at] ? num(pcts[1 + at]) : null,
                          barrier: bat >= 0 && monies[2 + bat] ? num(monies[2 + bat]) : null, bdist: bat >= 0 && pcts[1 + bat] ? num(pcts[1 + bat]) : null }));
    }
    return { level: level ? parseFloat(level[1]) : null, barrier_level: blevel ? parseFloat(blevel[1]) : null, underlyings: out };""",
                "pasted barrier values")

    # --- the product page: barrier column, then one decision ------------------------------------
    event = cut(event, """    var cPrice = col(/market price/i, 1), cInit = col(/initial/i, 2), cStrike = col(/strike/i, 3);""",
                """    var cPrice = col(/market price/i, 1), cInit = col(/initial/i, 2), cStrike = col(/strike/i, 3), cBarrier = col(/barrier/i, -1);""",
                "barrier column index")
    event = cut(event, """      var td = tr.querySelectorAll("td"), first = td[0] ? td[0].querySelectorAll("div") : [], sk = td[cStrike] ? td[cStrike].querySelectorAll("div") : [];""",
                """      var td = tr.querySelectorAll("td"), first = td[0] ? td[0].querySelectorAll("div") : [], sk = td[cStrike] ? td[cStrike].querySelectorAll("div") : [];
      var bk = cBarrier >= 0 && td[cBarrier] ? td[cBarrier].querySelectorAll("div") : [];""", "barrier cells")
    event = cut(event, """               strike: num(txt(sk[0])), dist: sk[1] ? num(txt(sk[1])) : null, ccy: (/[A-Z]{3}/.exec(txt(td[cInit])) || [""])[0] });""",
                """               strike: num(txt(sk[0])), dist: sk[1] ? num(txt(sk[1])) : null, ccy: (/[A-Z]{3}/.exec(txt(td[cInit])) || [""])[0],
               barrier: bk[0] ? num(txt(bk[0])) : null, bdist: bk[1] ? num(txt(bk[1])) : null });""", "barrier values")
    event = cut(event, """    var shareKeys = !!(event["share to deliver"] || event["number of shares"]);
    var physical = /physical|deliver/i.test(redType) || shareKeys;
    // no redemption event on the page yet (or not readable): the case follows the underlyings against their strike
    var inferred = !/redemption/i.test(type) && unders.length > 0;
    if (inferred) physical = unders.some(function (u) { return u.below; });
    // a final redemption whose type does not say how: below the strike at the final fixing means delivery,
    // read from the event's fixings when given, else from the underlyings against their strike
    var level = num(f["strike level"]) != null ? num(f["strike level"]) : levelHead ? parseFloat(levelHead[1]) : null;
    var fixed = num(event["final fixing observed"]), init = num(event["initial fixing"]);
    var finalBelow = fixed != null && init && level != null ? 100 * fixed / init < level - 1e-9 : null;
    if (!inferred && !early && !physical && !/cash/i.test(redType))
      physical = finalBelow != null ? finalBelow : unders.some(function (u) { return u.below; });""",
                """    // shares to deliver only when the page names them: "Share to Deliver: -" is no delivery
    var shareKeys = (num(given(event["number of shares"]) ? event["number of shares"] : "") || 0) > 0 || given(event["share to deliver"]);
    // no redemption event on the page yet (or not readable): the case follows the latest prices
    var inferred = !/redemption/i.test(type) && unders.length > 0;
    var level = num(f["strike level"]) != null ? num(f["strike level"]) : levelHead ? parseFloat(levelHead[1]) : null;
    var fixed = num(given(event["final fixing observed"]) ? event["final fixing observed"] : ""), init = num(given(event["initial fixing"]) ? event["initial fixing"] : "");
    var finalBelow = fixed != null && init && level != null ? 100 * fixed / init < level - 1e-9 : null;
    var barrier = barrierFacts(f, event, unders, txt(doc.querySelector(".underlying-table thead")));
    var computed = outcome(unders, barrier, finalBelow);
    // what the page says happened, when it says it: shares to deliver, or a cash redemption
    var stated = inferred || early ? null : shareKeys || /physical|deliver/i.test(redType) ? "delivery" : /cash/i.test(redType) ? "expiry" : null;
    var physical = !early && (stated ? stated === "delivery" : computed.case ? computed.case === "delivery" : true);""",
                "case decision")
    event = cut(event, """    if (ev.strike_level == null) ev.strike_level = level;
    // a case 2 the page contradicts (an underlying below its strike, or the event's final fixing below it)
    if (ev.case === "expiry" && (ev.below.length || finalBelow))
      ev.warn = (finalBelow ? "The final fixing is below the strike" : ev.below.join(", ") + " below the strike on the page") +
        " but the redemption reads as cash at 100%: check the case before sending.";""",
                """    if (ev.strike_level == null) ev.strike_level = level;
    ev.barrier = barrier; ev.why = early ? "" : stated ? "the page: " + (stated === "delivery" ? "shares to deliver" : redType) + " · " + computed.why : computed.why;
    // the page and the prices disagree, or the prices cannot tell: say so before anything is sent
    if (!early && barrier.conflict) ev.warn = "Check the barrier: " + barrier.conflict + ".";
    if (!early && stated && computed.case && stated !== computed.case)
      ev.warn = (ev.warn ? ev.warn + " " : "") + "The page states " + (stated === "delivery" ? "a delivery" : "a cash redemption at 100%") + " but the prices say " + computed.why + ": check the case before sending.";
    else if (!early && !stated && computed.case == null && !ev.warn)
      ev.warn = computed.why + (inferred ? "" : " (no redemption type on the page)") + ": shown as a delivery until you check it.";""",
                "case cross-check")

    event = cut(event, """      ev.delivery.underlying = worst || null;
    }
    return ev;
  }""", """      ev.delivery.underlying = worst || null;
    }
    // after the final fixing the table's prices are the final ones: a delivery read from them is not an estimate
    if (ev.delivery && ev.delivery.indicative && !inferred) ev.delivery.indicative = false;
    return ev;
  }""", "final delivery wording")

    # --- a pasted table re-reads a product with no redemption event yet, with the same rule ------
    event = cut(event, """      if (ev.inferred) {
        ev.below = ev.underlyings.filter(function (u) { return u.below; }).map(function (u) { return u.name; });
        ev.case = ev.below.length ? "delivery" : "expiry";
        ev.delivery = ev.case === "delivery" ? estimatedDelivery(ev) : null;
      }""", """      E.table.underlyings.forEach(function (t) {
        var u = ev.underlyings.filter(function (x) { return x.ticker === t.ticker || x.name === t.name; })[0];
        if (u && t.barrier != null) Object.assign(u, { barrier: t.barrier, bdist: t.bdist, belowBarrier: t.belowBarrier });
      });
      if (ev.inferred) {
        ev.below = ev.underlyings.filter(function (u) { return u.below; }).map(function (u) { return u.name; });
        var o = outcome(ev.underlyings, ev.barrier, null);
        ev.case = o.case || "delivery"; ev.why = o.why;
        ev.warn = o.case == null ? o.why + ": shown as a delivery until you check it." : "";
        ev.delivery = ev.case === "delivery" ? estimatedDelivery(ev) : null;
      }""", "pasted table re-read")

    # --- the strike panel: the barrier beside the strike, and the case the two give --------------
    event = cut(event, """    var below = list.filter(function (u) { return u.below; });
    $("#ev-strikes").innerHTML = '<p class="' + (below.length ? "warning" : "hint") + '">' + (below.length
        ? "<b>" + below.length + " underlying" + (below.length > 1 ? "s" : "") + " below the strike" + (level ? " (" + pct(level, 0) + ")" : "") + ":</b> " +
          below.map(function (u) { return esc(u.name) + " " + pct(u.dist); }).join(", ") + ". At expiry this means a delivery of the worst one (case 3)."
        : "All underlyings are above their strike" + (level ? " (" + pct(level, 0) + ")" : "") + ": at expiry, redemption at 100% (case 2).") + "</p>" +
      '<div class="table-wrap"><table class="table"><thead><tr><th>Underlying</th><th>Price</th><th>Initial fixing</th><th>Performance</th><th>Strike price</th><th>Distance to strike</th><th></th></tr></thead><tbody>' +
      list.map(function (u) {
        return "<tr" + (u.below ? ' class="ev-below"' : "") + "><td><b>" + esc(u.name) + "</b> <small class=\\"muted\\">" + esc(u.ticker) + "</small></td><td>" + esc(u.ccy) + " " + money(u.price) +
          "</td><td>" + esc(u.ccy) + " " + money(u.initial) + "</td><td>" + (u.perf > 0 ? "+" : "") + pct(u.perf) + "</td><td>" + esc(u.ccy) + " " + money(u.strike) +
          "</td><td>" + (u.dist > 0 ? "+" : "") + pct(u.dist) + "</td><td>" + (u.below ? '<span class="ev-flag">Below strike</span>' : "Above") + "</td></tr>";
      }).join("") + "</tbody></table></div>";""",
                """    var below = list.filter(function (u) { return u.below; });
    // the barrier: the product page's facts, else the pasted table's own barrier column (its type unknown)
    var b = E.ev && E.ev.barrier ? E.ev.barrier : { product: list.some(function (u) { return u.barrier != null; }), level: E.table && E.table.barrier_level, type: "", hit: null };
    var o = outcome(list, b, null), hasB = list.some(function (u) { return u.barrier != null; });
    var sl = level ? " (" + pct(level, 0) + ")" : "", bl = b.level != null ? " (" + pct(b.level, 0) + (b.type ? ", " + esc(b.type.toLowerCase()) : "") + ")" : "";
    var head = !below.length ? "All underlyings are at or above their strike" + sl + ": at expiry, redemption at 100% (case 2)."
      : "<b>" + below.length + " underlying" + (below.length > 1 ? "s" : "") + " below the strike" + sl + ":</b> " +
        below.map(function (u) { return esc(u.name) + " " + pct(u.dist); }).join(", ") + ". " +
        (o.case === "expiry" ? "But the barrier" + bl + " was not hit (" + esc(b.source || "") + "): at expiry, redemption at 100% in cash (case 2)."
         : o.case === "delivery" ? (b.product ? "The barrier" + bl + " was hit" + (b.source ? " (" + esc(b.source) + ")" : "") + ": " : "No barrier: ") + "at expiry, delivery of the worst one (case 3)."
         : "Delivery of the worst one (case 3) only if the barrier" + bl + " was hit" + (/amer/i.test(b.type) ? ": an American barrier, check every close during the life." : ": check it on the page or the term sheet.") +
           (hasB ? " Today all are " + (list.some(function (u) { return u.belowBarrier; }) ? "<b>not</b> " : "") + "above the barrier." : ""));
    $("#ev-strikes").innerHTML = '<p class="' + (o.case === "expiry" && !below.length ? "hint" : "warning") + '">' + head + "</p>" +
      '<div class="table-wrap"><table class="table"><thead><tr><th>Underlying</th><th>Price</th><th>Initial fixing</th><th>Performance</th>' +
      (hasB ? "<th>Barrier price</th><th>Distance to barrier</th>" : "") + "<th>Strike price</th><th>Distance to strike</th><th></th></tr></thead><tbody>" +
      list.map(function (u) {
        var flag = u.belowBarrier ? '<span class="ev-flag">Below barrier</span>' : u.below ? '<span class="ev-flag">Below strike</span>' + (hasB ? ", above barrier" : "") : "Above";
        return "<tr" + (u.below ? ' class="ev-below"' : "") + "><td><b>" + esc(u.name) + "</b> <small class=\\"muted\\">" + esc(u.ticker) + "</small></td><td>" + esc(u.ccy) + " " + money(u.price) +
          "</td><td>" + esc(u.ccy) + " " + money(u.initial) + "</td><td>" + (u.perf > 0 ? "+" : "") + pct(u.perf) +
          (hasB ? "</td><td>" + (u.barrier != null ? esc(u.ccy) + " " + money(u.barrier) : "–") + "</td><td>" + (u.bdist != null ? (u.bdist > 0 ? "+" : "") + pct(u.bdist) : "–") : "") +
          "</td><td>" + esc(u.ccy) + " " + money(u.strike) + "</td><td>" + (u.dist > 0 ? "+" : "") + pct(u.dist) + "</td><td>" + flag + "</td></tr>";
      }).join("") + "</tbody></table></div>";""", "strike panel")

    # --- the summary and the case names say why --------------------------------------------------
    event = cut(event, """  var CASES = { autocall: "Case 1 · Autocalled", expiry: "Case 2 · Expired at or above the strike", delivery: "Case 3 · Expired below the strike (delivery)" };""",
                """  var CASES = { autocall: "Case 1 · Autocalled", expiry: "Case 2 · Expired, redeemed at 100%", delivery: "Case 3 · Expired, redeemed by delivery" };""",
                "case names")
    event = cut(event, """    $("#ev-summary").innerHTML = "<b>" + esc(CASES[ev.case]) + "</b>" +""",
                """    $("#ev-summary").innerHTML = "<b>" + esc(CASES[ev.case]) + "</b>" + (ev.why ? " <small>(" + esc(ev.why) + ")</small>" : "") +""",
                "summary reason")

    # --- the email's reason for a case 2: the strike held, or the barrier did ---------------------
    event = cut(event, """      : p("All underlyings closed at or above their strike" + level + " at the final fixing.");""",
                """      : ev.below && ev.below.length && ev.barrier && ev.barrier.hit === false
        ? p(esc(ev.below.join(", ")) + " closed below the strike" + level + " at the final fixing, but the barrier" +
            (ev.barrier.level != null ? " (" + pct(ev.barrier.level, 0) + " of the initial level)" : "") + " was never hit: the capital is repaid in full.")
      : ev.below && ev.below.length ? p("The issuer redeems the product in cash at 100%.")
      : p("All underlyings closed at or above their strike" + level + " at the final fixing.");""", "email reason")
    event = cut(event, """      : ev.inferred ? p("At the latest prices, all underlyings are above their strike" + level + ": if this holds at the final fixing, the product is redeemed in cash.")""",
                """      : ev.inferred && ev.below && ev.below.length ? p("At the latest prices, " + esc(ev.below.join(", ")) + (ev.below.length > 1 ? " are" : " is") + " below the strike" + level + " but the barrier has not been hit: if this holds at the final fixing, the product is redeemed in cash.")
      : ev.inferred ? p("At the latest prices, all underlyings are above their strike" + level + ": if this holds at the final fixing, the product is redeemed in cash.")""",
                "email reason, before the fixing")
    return event
