# ══════════════════════════════════════════════════════════════════════
# CELL 3 — STEP 2: SURPRISE-EVENT ENGINE
# Turns Step 1's raw prints into the event table both front-ends consume.
#
# The surprise signal is a Standardised Unexpected Earnings (SUE) score, so it
# is independent of the price reaction. That separation is the whole point:
# SIGMA/DIR describe what the *fundamentals* did, RET(%) describes what the
# *market* did, and comparing the two is what makes hit-rate and post-event
# drift meaningful instead of tautological.
#
#   Primary  (analyst model)      SUE = (EPS_act - EPS_est) / sd(prior surprises)
#   Fallback (Foster-Olsen-Shevlin) SUE = (d - mean(prior d)) / sd(prior d),
#                                   d = EPS_q - EPS_{q-4}
#
# Both denominators use only prints available *before* the event, so the score
# is point-in-time and free of look-ahead bias. Prints without enough history
# to standardise are labelled 'Unrated' rather than silently called 'In Line'.
#
# A rated surprise only becomes a *tradeable signal* once price confirms it by
# crossing the Bollinger band during the reaction window (see band_signals).
# ══════════════════════════════════════════════════════════════════════
import numpy as np
import pandas as pd
from IPython.display import HTML, display

STATUS_MAJOR    = 'Major Surprise'
STATUS_MODERATE = 'Moderate Surprise'
STATUS_INLINE   = 'In Line'
STATUS_UNRATED  = 'Unrated'
SURPRISE_STATUS = (STATUS_MODERATE, STATUS_MAJOR)

# Band-cross outcome of the reaction window, and the signal it produces.
CROSS_UPPER, CROSS_LOWER, CROSS_NONE, CROSS_NA = 'UPPER', 'LOWER', 'NONE', 'NA'
SIGNAL_LONG, SIGNAL_SHORT, SIGNAL_NONE = 'LONG', 'SHORT', 'NONE'
ACTIVE_SIGNALS = (SIGNAL_LONG, SIGNAL_SHORT)
# Whether the fundamentals pointed the same way as the band did. Context, not
# a condition: the band defines the surprise.
AGREE_YES, AGREE_NO, AGREE_NA = 'YES', 'NO', 'NA'

EVENT_COLUMNS = [
    'TICKER', 'ID', 'NAME', 'DATE', 'TRADE_DATE', 'PERIOD_END', 'FISCAL_Q',
    'QUARTER', 'YEAR', 'EPS_ACT', 'EPS_EST', 'SURPRISE', 'SURPRISE_PCT',
    'SIGMA', 'SUE_SOURCE', 'STATUS', 'DIR', 'CATEGORY', 'PRICE_AT_EVENT',
    'RET(%)', 'ABN_RET(%)', 'BB_MID', 'BB_UPPER', 'BB_LOWER', 'BB_CROSS',
    'SIGNAL', 'SUE_AGREES',
]


# ─────────────────────────────────────────────────────────────
# 1. SUE CONSTRUCTION
# ─────────────────────────────────────────────────────────────
def _prior_stat(frame: pd.DataFrame, col: str, stat: str, min_periods: int) -> pd.Series:
    """Expanding statistic over each ticker's *earlier* prints only.

    The shift(1) is what keeps the estimate point-in-time: quarter q is scored
    with dispersion measured up to q-1.
    """
    grouped = frame.groupby('TICKER', sort=False)[col]
    return grouped.transform(
        lambda s: getattr(s.shift(1).expanding(min_periods=min_periods), stat)())


def _floor(scale: pd.Series, cfg: Config) -> pd.Series:
    """Keep a standardising denominator economically meaningful (see
    Config.sigma_floor). NaN stays NaN so 'not enough history' remains
    distinguishable from 'no dispersion'."""
    return scale.where(scale.isna(), scale.clip(lower=cfg.sigma_floor))


def _yoy_actual(frame: pd.DataFrame) -> pd.Series:
    """EPS four fiscal quarters back, matched on fiscal period rather than row
    offset so a gap in the print history cannot masquerade as a YoY change."""
    prev = frame[['TICKER', 'FISCAL_Q', 'EPS_ACT']].dropna(subset=['FISCAL_Q']).copy()
    prev = prev.drop_duplicates(['TICKER', 'FISCAL_Q'], keep='last')
    prev['FISCAL_Q'] = prev['FISCAL_Q'] + 4          # align onto the later row
    prev = prev.rename(columns={'EPS_ACT': 'EPS_ACT_LAG4'})
    merged = frame[['TICKER', 'FISCAL_Q']].merge(prev, on=['TICKER', 'FISCAL_Q'],
                                                 how='left')
    return pd.Series(merged['EPS_ACT_LAG4'].to_numpy(), index=frame.index)


def compute_sue(earnings: pd.DataFrame, cfg: Config = CFG) -> pd.DataFrame:
    """Attach SURPRISE, SIGMA (SUE) and its provenance to each print."""
    df = earnings.copy()
    df['PERIOD_END'] = pd.to_datetime(df['PERIOD_END'], errors='coerce')
    df['ANNOUNCE_DATE'] = pd.to_datetime(df['ANNOUNCE_DATE'], errors='coerce')
    df = df.dropna(subset=['ANNOUNCE_DATE', 'EPS_ACT'])
    if df.empty:
        return df.assign(SURPRISE=np.nan, SIGMA=np.nan, SUE_SOURCE='none')

    df['FISCAL_Q'] = df['PERIOD_END'].dt.to_period('Q')
    df = df.sort_values(['TICKER', 'PERIOD_END', 'ANNOUNCE_DATE']).reset_index(drop=True)

    if 'EPS_EST' not in df.columns:
        df['EPS_EST'] = np.nan

    # -- analyst model -------------------------------------------------
    # Both models are demeaned against the name's own prior surprise history,
    # which is what makes the score answer "surprising *for this name*". A
    # company whose consensus is chronically 2c light is not delivering a
    # surprise every quarter; only its deviation from that habit is news.
    df['SURPRISE'] = df['EPS_ACT'] - df['EPS_EST']
    bias_est = _prior_stat(df, 'SURPRISE', 'mean', cfg.min_sue_history)
    denom_est = _prior_stat(df, 'SURPRISE', 'std', cfg.min_sue_history)
    sue_analyst = (df['SURPRISE'] - bias_est) / _floor(denom_est, cfg)

    # -- time-series (Foster-Olsen-Shevlin) fallback -------------------
    df['EPS_DELTA_YOY'] = df['EPS_ACT'] - _yoy_actual(df)
    drift = _prior_stat(df, 'EPS_DELTA_YOY', 'mean', cfg.min_sue_history)
    denom_ts = _prior_stat(df, 'EPS_DELTA_YOY', 'std', cfg.min_sue_history)
    sue_ts = (df['EPS_DELTA_YOY'] - drift) / _floor(denom_ts, cfg)

    sigma = sue_analyst.where(np.isfinite(sue_analyst), sue_ts)
    source = np.where(np.isfinite(sue_analyst), 'analyst',
                      np.where(np.isfinite(sue_ts), 'time-series', 'none'))

    df['SIGMA'] = np.clip(sigma, -cfg.winsor_sigma, cfg.winsor_sigma)
    df['SUE_SOURCE'] = source
    with np.errstate(divide='ignore', invalid='ignore'):
        df['SURPRISE_PCT'] = np.where(
            df['EPS_EST'].abs() > 0,
            (df['EPS_ACT'] - df['EPS_EST']) / df['EPS_EST'].abs() * 100, np.nan)
    return df


def classify(df: pd.DataFrame, cfg: Config = CFG) -> pd.DataFrame:
    """Map SUE onto the five-way severity scale used by every visual."""
    sigma = df['SIGMA']
    mag = sigma.abs()
    rated = np.isfinite(sigma)

    df['STATUS'] = np.select(
        [~rated, mag >= cfg.major_sigma, mag >= cfg.moderate_sigma],
        [STATUS_UNRATED, STATUS_MAJOR, STATUS_MODERATE],
        default=STATUS_INLINE)
    df['DIR'] = np.select([~rated, sigma > 0, sigma < 0],
                          ['NA', 'POS', 'NEG'], default='FLAT')

    sign = np.where(df['DIR'] == 'POS', '+', '−')
    tier = np.where(df['STATUS'] == STATUS_MAJOR, 'Major', 'Moderate')
    df['CATEGORY'] = np.where(
        df['STATUS'] == STATUS_UNRATED, STATUS_UNRATED,
        np.where(df['STATUS'] == STATUS_INLINE, STATUS_INLINE,
                 np.char.add(np.char.add(tier.astype(str), ' '), sign.astype(str))))
    return df


# ─────────────────────────────────────────────────────────────
# 2. BOLLINGER BANDS
# One definition, used by the event engine and by the gallery chart, so the
# band a user sees is exactly the band the signal was measured against.
# ─────────────────────────────────────────────────────────────
def bollinger_bands(px: pd.Series, cfg: Config = CFG):
    """(mid, upper, lower) over cfg.bb_window sessions of volatility."""
    roll = px.rolling(cfg.bb_window, min_periods=cfg.bb_min_periods)
    mid, sd = roll.mean(), roll.std()
    return mid, mid + cfg.bb_sigma * sd, mid - cfg.bb_sigma * sd


# ─────────────────────────────────────────────────────────────
# 3. EVENT-WINDOW RETURNS + BAND CROSS  (vectorised per ticker)
# ─────────────────────────────────────────────────────────────
def _take(values: np.ndarray, idx: np.ndarray) -> np.ndarray:
    """Positional gather that returns NaN off the ends of the calendar."""
    out = np.full(idx.shape, np.nan)
    ok = (idx >= 0) & (idx < values.shape[0])
    out[ok] = values[idx[ok]]
    return out


def _pct_change(numerator: np.ndarray, denominator: np.ndarray) -> np.ndarray:
    with np.errstate(divide='ignore', invalid='ignore'):
        out = np.where(denominator > 0, numerator / denominator - 1.0, np.nan)
    return out * 100.0


def _cross_code(px_base, px_end, up_base, up_end, lo_base, lo_end) -> np.ndarray:
    """+1 the close broke *out* through the upper band during the window,
    -1 through the lower band, 0 no crossing, NaN when the band is undefined.

    A break is a genuine crossing, not merely a position: the close has to have
    been at or inside the band before the print and outside it after, so a name
    that was already riding above the upper band does not re-fire every quarter.
    """
    above_before, above_after = px_base > up_base, px_end > up_end
    below_before, below_after = px_base < lo_base, px_end < lo_end
    code = np.where(above_after & ~above_before, 1.0,
                    np.where(below_after & ~below_before, -1.0, 0.0))
    known = (np.isfinite(px_base) & np.isfinite(px_end)
             & np.isfinite(up_base) & np.isfinite(up_end)
             & np.isfinite(lo_base) & np.isfinite(lo_end))
    return np.where(known, code, np.nan)


def event_returns(events: pd.DataFrame, prices_wide: pd.DataFrame,
                  benchmark: pd.DataFrame | None = None,
                  cfg: Config = CFG) -> pd.DataFrame:
    """Reaction, post-event drift and Bollinger-band cross on the trading
    calendar.

    Reaction window is (t-1 close -> t+1 close), which brackets the print
    whether it landed before the open or after the close. Drift horizons start
    at the *end* of that window, so FWD_* measures genuine post-event drift
    rather than re-counting the announcement gap. The band cross is measured
    over the same window: it answers whether the print moved the price out of
    its own trading range.
    """
    horizons = list(cfg.horizons)
    cols = (['PRICE_AT_EVENT', 'TRADE_DATE_I', 'RET(%)', 'BENCH_RET(%)',
             'BB_MID', 'BB_UPPER', 'BB_LOWER', 'BB_CROSS_CODE']
            + [f'FWD_{h}D' for h in horizons])
    result = pd.DataFrame(np.nan, index=events.index, columns=cols)
    if prices_wide is None or prices_wide.empty or events.empty:
        return result

    calendar = prices_wide.index
    n = len(calendar)

    bench_vals = None
    if benchmark is not None and not benchmark.empty:
        series = benchmark.iloc[:, 0] if benchmark.shape[1] else None
        if series is not None:
            bench_vals = series.reindex(calendar).ffill().to_numpy(dtype=float)

    for ticker, grp in events.groupby('TICKER', sort=False):
        if ticker not in prices_wide.columns:
            continue
        series = prices_wide[ticker].ffill()
        px = series.to_numpy(dtype=float)
        mid_s, up_s, lo_s = bollinger_bands(series, cfg)
        mid_v = mid_s.to_numpy(dtype=float)
        up_v = up_s.to_numpy(dtype=float)
        lo_v = lo_s.to_numpy(dtype=float)

        dates = pd.to_datetime(grp['DATE']).to_numpy()
        pos = calendar.searchsorted(dates, side='left')
        base = pos - cfg.reaction_pre
        end = pos + cfg.reaction_post

        px_base, px_end = _take(px, base), _take(px, end)
        # A print is plottable when the announcement itself lands on the price
        # calendar -- not when its whole reaction window does. The latest print
        # has no t+1 close yet, and that is precisely the one the chart and the
        # radar exist to show, so it is kept with a NaN reaction rather than
        # dropped. Prints older than the plotted history are excluded here
        # instead: searchsorted would otherwise pin them all to the first
        # session and stack them against the left edge of the chart.
        inside = (pos < n) & (dates >= calendar[0].to_datetime64())
        result.loc[grp.index, 'PRICE_AT_EVENT'] = np.where(inside, _take(px, pos),
                                                           np.nan)
        result.loc[grp.index, 'TRADE_DATE_I'] = np.where(inside, pos, np.nan)
        result.loc[grp.index, 'RET(%)'] = _pct_change(px_end, px_base)

        # Band levels are reported at the close of the reaction window, which
        # is the observation the cross is judged on.
        up_base, up_end = _take(up_v, base), _take(up_v, end)
        lo_base, lo_end = _take(lo_v, base), _take(lo_v, end)
        result.loc[grp.index, 'BB_MID'] = _take(mid_v, end)
        result.loc[grp.index, 'BB_UPPER'] = up_end
        result.loc[grp.index, 'BB_LOWER'] = lo_end
        result.loc[grp.index, 'BB_CROSS_CODE'] = _cross_code(
            px_base, px_end, up_base, up_end, lo_base, lo_end)

        if bench_vals is not None:
            result.loc[grp.index, 'BENCH_RET(%)'] = _pct_change(
                _take(bench_vals, end), _take(bench_vals, base))

        for h in horizons:
            result.loc[grp.index, f'FWD_{h}D'] = _pct_change(
                _take(px, end + h), px_end)

    result['ABN_RET(%)'] = result['RET(%)'] - result['BENCH_RET(%)']
    return result


def band_signals(df: pd.DataFrame) -> pd.DataFrame:
    """Turn the numeric cross code into BB_CROSS and the tradeable SIGNAL.

    The band defines the surprise. A print that closed through the upper band
    is a positive surprise and a print that closed through the lower band is a
    negative one, whatever EPS did and whatever the raw return was: a stock can
    rise on a print and still not leave its own range, and that is not news.
    Volatility is the yardstick, so the crossing is the event.

    SUE is kept alongside as context — SIGMA/CATEGORY still say how surprising
    the fundamentals were, and SUE_AGREES records whether they pointed the same
    way as the band. It is reported, never a condition.
    """
    code = pd.to_numeric(df.get('BB_CROSS_CODE'), errors='coerce')
    df['BB_CROSS'] = np.select([code == 1, code == -1, code == 0],
                               [CROSS_UPPER, CROSS_LOWER, CROSS_NONE],
                               default=CROSS_NA)
    up, down = df['BB_CROSS'] == CROSS_UPPER, df['BB_CROSS'] == CROSS_LOWER
    df['SIGNAL'] = np.select([up, down], [SIGNAL_LONG, SIGNAL_SHORT],
                             default=SIGNAL_NONE)
    # Agreement is only meaningful where EPS actually said something: an In
    # Line print has a SUE sign but no opinion worth agreeing with.
    rated = df['STATUS'].isin(SURPRISE_STATUS) & df['DIR'].isin(('POS', 'NEG'))
    df['SUE_AGREES'] = np.select(
        [(up | down) & rated & ((up & (df['DIR'] == 'POS'))
                                | (down & (df['DIR'] == 'NEG'))),
         (up | down) & rated],
        [AGREE_YES, AGREE_NO], default=AGREE_NA)
    return df


# ─────────────────────────────────────────────────────────────
# 4. ASSEMBLY
# ─────────────────────────────────────────────────────────────
def build_events(earnings: pd.DataFrame, prices_wide: pd.DataFrame,
                 benchmark: pd.DataFrame | None = None,
                 cfg: Config = CFG) -> pd.DataFrame:
    """earnings + prices  ->  the canonical event table."""
    if earnings is None or earnings.empty:
        return pd.DataFrame(columns=EVENT_COLUMNS)

    df = classify(compute_sue(earnings, cfg), cfg)
    if df.empty:
        return pd.DataFrame(columns=EVENT_COLUMNS)

    df['DATE'] = df['ANNOUNCE_DATE']
    if 'NAME' not in df.columns:
        df['NAME'] = df['TICKER']

    rets = event_returns(df, prices_wide, benchmark, cfg)
    df = pd.concat([df, rets], axis=1)
    df = band_signals(df)

    # Snap the announcement onto the trading calendar so the gallery can place
    # a marker exactly on a plotted point instead of between two sessions.
    if prices_wide is not None and not prices_wide.empty:
        idx = prices_wide.index
        take = df['TRADE_DATE_I'].to_numpy()
        snapped = np.where(np.isfinite(take),
                           idx.to_numpy()[np.nan_to_num(take, nan=0).astype(int)],
                           df['DATE'].to_numpy())
        df['TRADE_DATE'] = pd.to_datetime(snapped)
    else:
        df['TRADE_DATE'] = df['DATE']

    df['QUARTER'] = df['DATE'].dt.to_period('Q').astype(str)
    df['YEAR'] = df['DATE'].dt.year
    df['FISCAL_Q'] = df['FISCAL_Q'].astype(str)

    keep = EVENT_COLUMNS + [f'FWD_{h}D' for h in cfg.horizons]
    for col in keep:
        if col not in df.columns:
            df[col] = np.nan
    # Keep every print that falls on the plotted calendar, including one that
    # is too recent to have a completed reaction window: the chart, the signal
    # log and the radar all read the event table, and an announcement missing
    # from it reads as "this name did not report". Its RET(%)/FWD_* stay NaN,
    # which every downstream mean already skips.
    df = df.dropna(subset=['PRICE_AT_EVENT'])
    return (df[keep].sort_values(['TICKER', 'DATE'])
                    .reset_index(drop=True))


def _events_card(code: str, label: str, ev: pd.DataFrame, cfg: Config) -> str:
    rated = ev[ev.STATUS != STATUS_UNRATED]
    sur = rated[rated.STATUS.isin(SURPRISE_STATUS)]
    # Signals are counted over every print, not just the rated ones: the band
    # cross is the event, and a print with too little EPS history to score can
    # still leave its range.
    signals = ev[ev.SIGNAL.isin(ACTIVE_SIGNALS)] if 'SIGNAL' in ev.columns \
        else ev.iloc[0:0]
    analyst = (ev.SUE_SOURCE == 'analyst').mean() if len(ev) else 0
    rows = [
        ('Events built', f"{len(ev):,}"),
        ('Rated / unrated', f"{len(rated):,} / {len(ev) - len(rated):,}"),
        ('Surprises detected', f"{len(sur):,} ({len(sur)/max(len(rated),1):.0%} of rated)"),
        ('Positive / negative', f"{(sur.DIR == 'POS').sum():,} / {(sur.DIR == 'NEG').sum():,}"),
        ('Band crossings',
         f"{len(signals):,} ({len(signals)/max(len(ev),1):.0%} of prints) — "
         f"{(signals.SIGNAL == SIGNAL_LONG).sum():,} upper / "
         f"{(signals.SIGNAL == SIGNAL_SHORT).sum():,} lower"),
        ('SUE from consensus', f"{analyst:.0%} (rest time-series)"),
        ('Definitions', f"surprise = close through the {cfg.bb_window}-day "
                        f"±{cfg.bb_sigma}σ band; |SUE| ≥ {cfg.moderate_sigma} "
                        f"moderate, ≥ {cfg.major_sigma} major (context)"),
    ]
    body = "".join(
        f"<div style='display:flex;justify-content:space-between;padding:5px 0;"
        f"border-bottom:1px solid {THEME.HAIRLINE}'>"
        f"<span style='font-weight:300'>{k}</span>"
        f"<span style='font-weight:700'>{v}</span></div>" for k, v in rows)
    head = (f"<div style='font-weight:800;font-size:16px;color:{THEME.SPACE_BLUE};"
            f"margin-bottom:8px'>Step 2 complete — {label} ({code})</div>")
    return THEME.panel(head + body, max_width='560px')


def run_event_engine(code: str, store=STORE, cfg: Config = CFG,
                     report: Reporter | None = None) -> pd.DataFrame:
    """Read Step 1's output from the store, build events, publish them back.
    No Bloomberg round-trip: everything needed is already in memory."""
    report = report or Reporter()
    earnings = store.get(code, 'earnings')
    prices = store.get(code, 'prices_wide')
    if earnings is None or prices is None:
        raise RuntimeError(f"Step 1 data missing for {code}. Run ingest('{code}') first.")

    report(f"Building surprise events for {code} "
           f"({len(earnings):,} prints x {prices.shape[1]} names)…")
    events = build_events(earnings, prices, store.get(code, 'benchmark'), cfg)
    store.put(code, 'events', events)
    display(HTML(_events_card(code, cfg.label(code), events, cfg)))
    return events


print('Step 2 ready — run_event_engine(code)')
