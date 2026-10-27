"""Worst-of BRC showcase: every number of the page, from the data fetch_data.py saved in showcase/data."""
import csv, datetime as dt, json, math, os
import numpy as np

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"))

TODAY = dt.date.fromisoformat(json.load(open("yahoo_hist.json"))["NESN.SW"]["dates"][-1])   # the last close
NAMES = {"NESN.SW": ("Nestlé", "CHF"), "ASML.AS": ("ASML", "EUR"), "MSFT": ("Microsoft", "USD")}
SYMS = list(NAMES)
NOTIONAL, TENOR, BARRIER, STRIKE, FREQ = 1000.0, 1.0, 0.60, 1.0, 4

yh = json.load(open("yahoo_hist.json"))
info = json.load(open("yahoo_info.json"))
opts = json.load(open("yahoo_options.json"))

# --- SNB: monthly money-market rates -------------------------------------------------------------
snb = {}
rows = list(csv.reader(open("snb_zimoma.csv", encoding="utf-8-sig"), delimiter=";"))
for r in rows[4:]:
    if len(r) == 3 and r[2]:
        snb.setdefault(r[1], []).append((r[0], float(r[2])))
rates = {k: snb[k][-1] for k in ("SARON", "ESTR", "SOFR", "EG3M", "EURIBOR", "SONIA", "TONA")}
r_ccy = {"CHF": rates["SARON"][1] / 100, "EUR": rates["ESTR"][1] / 100, "USD": rates["SOFR"][1] / 100}
rate_hist = {k: snb[k][-36:] for k in ("SARON", "ESTR", "SOFR")}

# --- ECB: daily reference rates, CHF per EUR and per USD ------------------------------------------
ecb = {}
for r in csv.DictReader(open("ecb_fx.csv")):
    ecb.setdefault(r["CURRENCY"], {})[r["TIME_PERIOD"]] = float(r["OBS_VALUE"])
fx_dates = sorted(set(ecb["CHF"]) & set(ecb["USD"]))
chf_per = {"EUR": {d: ecb["CHF"][d] for d in fx_dates}, "USD": {d: ecb["CHF"][d] / ecb["USD"][d] for d in fx_dates}}

# --- reconciliation: ECB fixing vs Yahoo EURCHF=X / USDCHF=X on the same days ----------------------
def yahoo_series(s, key="close"):
    return dict(zip(yh[s]["dates"], yh[s][key]))
recon = {}
for ccy, ysym in (("EUR", "EURCHF=X"), ("USD", "USDCHF=X")):
    y = yahoo_series(ysym)
    common = [d for d in fx_dates if d in y][-250:]
    diffs = [abs(chf_per[ccy][d] / y[d] - 1) * 1e4 for d in common]
    top = max(common, key=lambda d: abs(chf_per[ccy][d] / y[d] - 1))
    recon[ccy] = {"max_day": top, "days": len(common), "median_bp": round(float(np.median(diffs)), 1), "max_bp": round(max(diffs), 1),
                  "last": [common[-1], round(chf_per[ccy][common[-1]], 5), round(y[common[-1]], 5)]}

# --- Yahoo: aligned weekly returns for vol and correlation ----------------------------------------
def weekly(series):  # Friday-ish sampling: last obs of each ISO week
    out = {}
    for d, v in series.items():
        y, w, _ = dt.date.fromisoformat(d).isocalendar()
        out[(y, w)] = (d, v)
    return out
def logret(vals):
    v = np.log(np.array(vals)); return np.diff(v)

px = {s: yahoo_series(s, "adj") for s in SYMS}
close = {s: yahoo_series(s, "close") for s in SYMS}
start_1y = (TODAY - dt.timedelta(days=365)).isoformat()
start_2y = (TODAY - dt.timedelta(days=730)).isoformat()
wk = {s: weekly({d: v for d, v in px[s].items() if d >= start_2y}) for s in SYMS}
fxwk = {c: weekly({d: v for d, v in chf_per[c].items() if d >= start_2y}) for c in ("EUR", "USD")}
keys = sorted(set.intersection(*(set(wk[s]) for s in SYMS), *(set(fxwk[c]) for c in fxwk)))
R = np.array([logret([wk[s][k][1] for k in keys]) for s in SYMS])
FXR = {c: logret([fxwk[c][k][1] for k in keys]) for c in fxwk}
corr_2y = np.corrcoef(R)
# pricing correlation: 5 years of weekly returns (more stable than the last two years alone)
start_5y = (TODAY - dt.timedelta(days=5 * 365)).isoformat()
wk5 = {s: weekly({d: v for d, v in px[s].items() if d >= start_5y}) for s in SYMS}
k5 = sorted(set.intersection(*(set(wk5[s]) for s in SYMS)))
corr = np.corrcoef(np.array([logret([wk5[s][k][1] for k in k5]) for s in SYMS]))
corr_periods = []
for a, b in (("2019-10-28", "2020-12-31"), ("2021-01-01", "2022-12-31"), ("2023-01-01", "2024-06-30"), ("2024-07-01", TODAY.isoformat())):
    wkp = {s: weekly({d: v for d, v in px[s].items() if a <= d <= b}) for s in SYMS}
    kp = sorted(set.intersection(*(set(wkp[s]) for s in SYMS)))
    c = np.corrcoef(np.array([logret([wkp[s][k][1] for k in kp]) for s in SYMS]))
    corr_periods.append({"from": a, "to": b, "weeks": len(kp) - 1, "pairs": [round(c[0, 1], 2), round(c[0, 2], 2), round(c[1, 2], 2)]})
corr_periods.append({"from": start_5y, "to": TODAY.isoformat(), "weeks": len(k5) - 1, "pairs": [round(corr[0, 1], 2), round(corr[0, 2], 2), round(corr[1, 2], 2)], "used": True})
vol_w = R.std(axis=1, ddof=1) * math.sqrt(52)

def daily_vol(s, start, lam=None):
    d = sorted(x for x in px[s] if x >= start); r = logret([px[s][x] for x in d])
    if lam:  # EWMA (RiskMetrics)
        v = r[0] ** 2
        for x in r[1:]: v = lam * v + (1 - lam) * x * x
        return math.sqrt(v * 252)
    return float(r.std(ddof=1) * math.sqrt(252))
fx_vol = {c: float(FXR[c].std(ddof=1) * math.sqrt(52)) for c in FXR}
rho_fx = {s: (0.0 if NAMES[s][1] == "CHF" else float(np.corrcoef(R[i], FXR[NAMES[s][1]])[0, 1])) for i, s in enumerate(SYMS)}

# --- Yahoo options: own implied vols for MSFT (Black-Scholes on mid prices, SOFR, Yahoo dividend) ---
def ncdf(x): return 0.5 * (1 + math.erf(x / math.sqrt(2)))
def bs(S, K, T, r, q, v, call):
    d1 = (math.log(S / K) + (r - q + v * v / 2) * T) / (v * math.sqrt(T)); d2 = d1 - v * math.sqrt(T)
    return S * math.exp(-q * T) * ncdf(d1) - K * math.exp(-r * T) * ncdf(d2) if call else K * math.exp(-r * T) * ncdf(-d2) - S * math.exp(-q * T) * ncdf(-d1)
def implied(price, S, K, T, r, q, call):
    lo, hi = 0.01, 3.0
    if not (bs(S, K, T, r, q, lo, call) < price < bs(S, K, T, r, q, hi, call)): return None
    for _ in range(80):
        mid = (lo + hi) / 2
        if bs(S, K, T, r, q, mid, call) < price: lo = mid
        else: hi = mid
    return (lo + hi) / 2
o = opts["MSFT"]; S0 = o["spot"]; T_opt = (dt.date.fromisoformat(o["expiry"]) - TODAY).days / 365
q_msft = info["MSFT"]["trailingAnnualDividendYield"]
smile = []
for row in o["rows"]:
    K = row["strike"]; m = K / S0
    if row["bid"] <= 0 or not (0.5 <= m <= 1.3): continue
    if (row["type"] == "put") != (K < S0): continue           # out-of-the-money side only
    v = implied((row["bid"] + row["ask"]) / 2, S0, K, T_opt, r_ccy["USD"], q_msft, row["type"] == "call")
    if v: smile.append({"m": round(m, 4), "iv": round(v, 4), "type": row["type"]})
smile.sort(key=lambda x: x["m"])
def smile_at(m):
    pts = sorted(smile, key=lambda x: abs(x["m"] - m))[:2]
    return sum(p["iv"] for p in pts) / len(pts)
iv_atm, iv_60 = smile_at(1.0), smile_at(0.6) if smile and smile[0]["m"] <= 0.65 else None
rv_1y = {s: daily_vol(s, start_1y) for s in SYMS}
iv_ratio = iv_atm / rv_1y["MSFT"]

# --- Monte Carlo: quanto CHF worst-of, daily steps ------------------------------------------------
def simulate(vols, C, n=40000, steps=252, seed=7):
    rng = np.random.default_rng(seed)
    L = np.linalg.cholesky(C)
    dt_ = TENOR / steps
    mu = np.array([r_ccy[NAMES[s][1]] - info[s]["trailingAnnualDividendYield"] -
                   rho_fx[s] * vols[i] * fx_vol.get(NAMES[s][1], 0) for i, s in enumerate(SYMS)])
    logS = np.zeros((n, 3)); running_min = np.zeros(n)
    half = n // 2
    for _ in range(steps):
        z = rng.standard_normal((half, 3)); z = np.vstack([z, -z]) @ L.T      # antithetic
        logS += (mu - vols ** 2 / 2) * dt_ + vols * math.sqrt(dt_) * z
        running_min = np.minimum(running_min, logS.min(axis=1))
    return np.exp(logS.min(axis=1)), np.exp(running_min), mu
def price(worst, worst_path, barrier=BARRIER, american=False):
    hit = (worst_path if american else worst) < barrier
    red = np.where(hit & (worst < STRIKE), worst, 1.0) * NOTIONAL
    df_T = math.exp(-r_ccy["CHF"] * TENOR)
    annuity = sum(math.exp(-r_ccy["CHF"] * k / FREQ) for k in range(1, FREQ + 1)) / FREQ
    pv_red = df_T * red.mean()
    fair = (NOTIONAL - pv_red) / (annuity * NOTIONAL)       # coupon p.a. making the note worth par
    loss = red < NOTIONAL
    return {"fair_coupon": fair, "p_hit": float(hit.mean()), "p_loss": float(loss.mean()),
            "exp_red": float(red.mean() / NOTIONAL), "cond_loss": float(1 - red[loss].mean() / NOTIONAL) if loss.any() else 0.0,
            "pv_red": pv_red / NOTIONAL, "annuity": annuity}

vols_real = np.array([rv_1y[s] for s in SYMS])
vols_impl = vols_real * np.array([1.0 if s != "MSFT" else 1.0 for s in SYMS])
vols_impl = np.array([iv_atm if s == "MSFT" else rv_1y[s] * iv_ratio for s in SYMS])
worst, wpath, mu = simulate(vols_impl, corr)
base = price(worst, wpath); amer = price(worst, wpath, american=True)
worst_r, wpath_r, _ = simulate(vols_real, corr)
real = price(worst_r, wpath_r)
skew_ratio = iv_60 / iv_atm if iv_60 else 1.0
vols_skew = vols_impl * skew_ratio
worst_s, wpath_s, _ = simulate(vols_skew, corr)
skew = price(worst_s, wpath_s)

grid_b = [0.50, 0.55, 0.60, 0.65, 0.70]
grid = {"barriers": grid_b, "european": [round(price(worst, wpath, b)["fair_coupon"] * 100, 2) for b in grid_b],
        "american": [round(price(worst, wpath, b, True)["fair_coupon"] * 100, 2) for b in grid_b]}
corr_shift = []
for dc in (-0.2, -0.1, 0.0, 0.1, 0.2):
    C = corr + dc * (1 - np.eye(3)); C = np.clip(C, -0.95, 0.99); np.fill_diagonal(C, 1)
    w, wp, _ = simulate(vols_impl, C)
    corr_shift.append({"shift": dc, "coupon": round(price(w, wp)["fair_coupon"] * 100, 2)})
vol_shift = []
for dv in (-0.05, 0.0, 0.05):
    w, wp, _ = simulate(vols_impl + dv, corr)
    vol_shift.append({"shift": dv, "coupon": round(price(w, wp)["fair_coupon"] * 100, 2)})
hist_bins = np.linspace(0.2, 1.8, 41)
h, _ = np.histogram(np.clip(worst, 0.2, 1.7999), bins=hist_bins)

# --- backtest: every 1-year window of the last 7 years, local-currency closes (quanto) -------------
dates = sorted(set.intersection(*(set(close[s]) for s in SYMS)))
bt = []
for i, d0 in enumerate(dates):
    d1t = (dt.date.fromisoformat(d0) + dt.timedelta(days=365)).isoformat()
    j = next((k for k in range(i, len(dates)) if dates[k] >= d1t), None)
    if j is None: break
    perf = min(close[s][dates[j]] / close[s][d0] for s in SYMS)
    pmin = min(min(close[s][dates[k]] for k in range(i, j + 1)) / close[s][d0] for s in SYMS) if i % 5 == 0 else None
    bt.append({"start": d0, "end": dates[j], "worst": round(perf, 4), "path_min": round(pmin, 4) if pmin else None})
bt_w = np.array([b["worst"] for b in bt]); bt_pm = np.array([b["path_min"] for b in bt if b["path_min"] is not None])
backtest = {"windows": len(bt), "first": bt[0]["start"], "last": bt[-1]["start"],
            "p_below_strike": float((bt_w < 1).mean()), "p_below_barrier": float((bt_w < BARRIER).mean()),
            "p_touch_barrier": float((bt_pm < BARRIER).mean()), "worst": float(bt_w.min()),
            "worst_window": min(bt, key=lambda b: b["worst"]), "median": float(np.median(bt_w)),
            "series": [[b["start"], b["worst"]] for b in bt[::3]]}

# --- rebased chart, 1 year, and underlying table ---------------------------------------------------
d1 = [d for d in dates if d >= start_1y]
rebased = {s: [[d, round(close[s][d] / close[s][d1[0]] * 100, 2)] for d in d1[::2] + [d1[-1]]] for s in SYMS}
unders = []
for i, s in enumerate(SYMS):
    last = close[s][dates[-1]]
    unders.append({"sym": s, "name": NAMES[s][0], "ccy": NAMES[s][1], "price": last, "date": dates[-1],
                   "strike": last * STRIKE, "barrier": last * BARRIER, "rv1y": rv_1y[s], "rv2y": float(vol_w[i]),
                   "ewma": daily_vol(s, start_2y, 0.94), "pricing_vol": float(vols_impl[i]),
                   "div": info[s]["trailingAnnualDividendYield"], "pe": info[s]["trailingPE"], "fpe": info[s]["forwardPE"],
                   "mcap_bn": info[s]["marketCap"] / 1e9, "beta": info[s]["beta"], "sector": info[s]["sector"],
                   "hi52": info[s]["fiftyTwoWeekHigh"], "lo52": info[s]["fiftyTwoWeekLow"],
                   "earnings": dt.datetime.fromtimestamp(info[s]["earningsTimestampStart"], dt.timezone.utc).date().isoformat() if info[s]["earningsTimestampStart"] else None,
                   "rho_fx": rho_fx[s], "fx_vol": fx_vol.get(NAMES[s][1], 0.0), "r": r_ccy[NAMES[s][1]], "drift": float(mu[i])})

out = {"today": TODAY.isoformat(), "product": {"notional": NOTIONAL, "tenor": TENOR, "barrier": BARRIER, "strike": STRIKE, "freq": FREQ, "ccy": "CHF"},
       "rates": {k: {"month": v[0], "value": v[1]} for k, v in rates.items()}, "rate_hist": rate_hist,
       "fx": {"EURCHF": [fx_dates[-1], chf_per["EUR"][fx_dates[-1]]], "USDCHF": [fx_dates[-1], chf_per["USD"][fx_dates[-1]]],
              "points": len(fx_dates), "first": fx_dates[0]}, "recon": recon,
       "corr": corr.round(3).tolist(), "corr_2y": corr_2y.round(3).tolist(), "corr_periods": corr_periods, "weeks": len(keys), "weeks_5y": len(k5) - 1, "unders": unders,
       "smile": smile, "iv": {"expiry": o["expiry"], "atm": iv_atm, "at60": iv_60, "ratio": iv_ratio, "spot": S0, "n": len(smile)},
       "mc": {"paths": 40000, "steps": 252, "implied": base, "american": amer, "realised": real, "skew": skew, "skew_ratio": skew_ratio,
              "hist": {"edges": hist_bins.round(3).tolist(), "counts": h.tolist()}},
       "grid": grid, "corr_shift": corr_shift, "vol_shift": vol_shift, "backtest": backtest, "rebased": rebased,
       "sources": {"yahoo_points": {s: len(yh[s]["dates"]) for s in yh}, "ecb_points": len(fx_dates),
                   "snb_series": len(snb), "option_quotes": len(o["rows"])}}
json.dump(out, open("showcase.json", "w"), default=float)
print(json.dumps({k: out[k] for k in ("rates", "fx", "recon", "iv", "corr")}, default=float, indent=0)[:1500])
print("periods", corr_periods); print("skew", skew_ratio, skew); print("implied", base); print("american", amer); print("realised", real); print(grid, corr_shift, vol_shift)
print({k: v for k, v in backtest.items() if k != "series"})
for u in unders: print(u["sym"], round(u["rv1y"], 3), round(u["pricing_vol"], 3), round(u["rho_fx"], 3), round(u["drift"], 4))
