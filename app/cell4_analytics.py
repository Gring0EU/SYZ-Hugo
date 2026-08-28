# ══════════════════════════════════════════════════════════════════════
# CELL 4 — ANALYTICS LAYER
# Pure aggregation over the Step 2 event table: no BQL, no plotting, no
# widgets. Every number shown by the dashboard is produced here, which keeps
# the presentation layer thin and the statistics independently testable.
# ══════════════════════════════════════════════════════════════════════
import numpy as np
import pandas as pd

CAT_ORDER = ['Major +', 'Moderate +', 'In Line', 'Moderate −', 'Major −']

TF_OPTIONS = [
    ('Last Earnings Only', 'LAST'),
    ('1 Year',  '1Y'),
    ('2 Years', '2Y'),
    ('3 Years', '3Y'),
    ('5 Years (Full)', '5Y'),
]
TF_LABELS = {'LAST': 'Most recent print', '1Y': 'Trailing 1 Year',
             '2Y': 'Trailing 2 Years', '3Y': 'Trailing 3 Years',
             '5Y': 'Full 5-Year History'}
TF_YEARS = {'1Y': 1, '2Y': 2, '3Y': 3, '5Y': 5}


# ─────────────────────────────────────────────────────────────
# WINDOWING
# ─────────────────────────────────────────────────────────────
def prepare(ev: pd.DataFrame) -> pd.DataFrame:
    """Normalise an event table for analysis, whatever produced it.

    Tolerates a table written by an older run (missing CATEGORY, string DATE,
    absent forward returns, no band columns) so a stale parquet still renders
    instead of raising.
    """
    if ev is None or ev.empty:
        return pd.DataFrame()
    out = ev.copy()
    out['DATE'] = pd.to_datetime(out['DATE'], errors='coerce')
    out = out.dropna(subset=['DATE'])
    if 'CATEGORY' not in out.columns:
        sign = np.where(out['DIR'] == 'POS', '+', '−')
        tier = np.where(out['STATUS'] == STATUS_MAJOR, 'Major', 'Moderate')
        out['CATEGORY'] = np.where(
            out['STATUS'].isin(SURPRISE_STATUS),
            pd.Series(tier, index=out.index) + ' ' + pd.Series(sign, index=out.index),
            out['STATUS'])
    if 'QUARTER' not in out.columns:
        out['QUARTER'] = out['DATE'].dt.to_period('Q').astype(str)
    if 'ABN_RET(%)' not in out.columns:
        out['ABN_RET(%)'] = np.nan
    # Band columns predate no event table built by the current engine, but a
    # file written before the band signal existed must still analyse cleanly.
    if 'BB_CROSS' not in out.columns:
        out['BB_CROSS'] = CROSS_NA
    if 'SIGNAL' not in out.columns:
        out['SIGNAL'] = SIGNAL_NONE
    if 'SUE_AGREES' not in out.columns:
        out['SUE_AGREES'] = AGREE_NA
    for col in ('BB_MID', 'BB_UPPER', 'BB_LOWER'):
        if col not in out.columns:
            out[col] = np.nan
    return out


def ensure_forward_returns(ev: pd.DataFrame, prices_wide: pd.DataFrame,
                           cfg: Config = CFG) -> pd.DataFrame:
    """Backfill drift columns only if they are genuinely absent.

    Step 2 computes these once, at build time; recomputing them on every
    dropdown change would be the single most expensive thing the dashboard
    does. This is a compatibility path, not the normal one.
    """
    missing = [h for h in cfg.horizons if f'FWD_{h}D' not in ev.columns]
    if not missing or ev.empty:
        return ev
    return pd.concat([ev, event_returns(ev, prices_wide, None, cfg)
                      [[f'FWD_{h}D' for h in missing]]], axis=1)


def filter_window(ev: pd.DataFrame, tf: str):
    """Trim to the selected trailing window.

    Anchored on the most recent print in the data rather than wall-clock today,
    so a pull taken a few days ago does not silently empty the short windows.
    """
    if ev.empty:
        return ev, None, None
    anchor = ev['DATE'].max()
    if tf == 'LAST':
        out = (ev.sort_values('DATE').groupby('TICKER', as_index=False,
                                              group_keys=False).tail(1))
        return out, (out['DATE'].min() if not out.empty else None), anchor
    cutoff = anchor - pd.DateOffset(years=TF_YEARS[tf])
    return ev[ev['DATE'] >= cutoff], cutoff, anchor


def rated(ev: pd.DataFrame) -> pd.DataFrame:
    """Events carrying a usable SUE. Unrated prints are real earnings but have
    no signal, so they are excluded from every statistic and counted separately
    rather than being quietly folded into 'In Line'."""
    return ev[ev['STATUS'] != STATUS_UNRATED] if not ev.empty else ev


def surprises(ev: pd.DataFrame) -> pd.DataFrame:
    return ev[ev['STATUS'].isin(SURPRISE_STATUS)] if not ev.empty else ev


def signalled(ev: pd.DataFrame) -> pd.DataFrame:
    """Prints that closed through a band — the surprises, by definition."""
    if ev.empty or 'SIGNAL' not in ev.columns:
        return ev.iloc[0:0] if not ev.empty else ev
    return ev[ev['SIGNAL'].isin(ACTIVE_SIGNALS)]


# ─────────────────────────────────────────────────────────────
# HEADLINE STATISTICS
# ─────────────────────────────────────────────────────────────
def _hit_rate(df: pd.DataFrame) -> float:
    """Share of surprises whose market reaction agreed with the SUE sign.

    Meaningful precisely because SIGMA/DIR come from fundamentals while
    RET(%) comes from price -- the two are independent measurements.
    """
    if df.empty:
        return np.nan
    # A print still awaiting its reaction window has no verdict; comparing NaN
    # would silently score it as a miss and drag the rate down.
    scored = df[df['RET(%)'].notna()]
    if scored.empty:
        return np.nan
    agree = np.where(scored['DIR'] == 'POS', scored['RET(%)'] > 0,
                     scored['RET(%)'] < 0)
    return float(np.nanmean(agree))


def kpis(ev: pd.DataFrame, cfg: Config = CFG) -> dict:
    """Everything the dashboard shows, measured on band crossings.

    EPS never enters: a report either moved price out of its own volatility
    range or it did not, and the numbers below describe the two populations
    that follow from that.
    """
    sig = signalled(ev)
    up, down = sig[sig.SIGNAL == SIGNAL_LONG], sig[sig.SIGNAL == SIGNAL_SHORT]
    quiet = ev[ev['SIGNAL'] == SIGNAL_NONE] if not ev.empty else ev
    drift = f'FWD_{cfg.horizons[1]}D' if len(cfg.horizons) > 1 else None

    def mean(frame, col):
        return frame[col].mean() if col and col in frame.columns and len(frame) \
            else np.nan

    return dict(
        prints=len(ev),
        signals=len(sig), n_long=len(up), n_short=len(down),
        cross_rate=(len(sig) / len(ev) if len(ev) else np.nan),
        avg_ret_long=mean(up, 'RET(%)'), avg_ret_short=mean(down, 'RET(%)'),
        avg_abn_long=mean(up, 'ABN_RET(%)'), avg_abn_short=mean(down, 'ABN_RET(%)'),
        drift_long=mean(up, drift), drift_short=mean(down, drift),
        drift_quiet=mean(quiet, drift), drift_horizon=cfg.horizons[1]
        if len(cfg.horizons) > 1 else cfg.horizons[0],
        pending=int(ev['RET(%)'].isna().sum()) if len(ev) else 0,
        names=int(ev['TICKER'].nunique()) if len(ev) else 0,
    )


# ─────────────────────────────────────────────────────────────
# BREAKDOWNS
# ─────────────────────────────────────────────────────────────
def signal_dir(ev: pd.DataFrame) -> pd.Series:
    """POS / NEG for a band crossing, so every breakdown speaks one language.

    The dashboard is about what price did after a report: a print that closed
    through the upper band is positive, through the lower band negative, and
    everything else is not an event at all.
    """
    return pd.Series(np.where(ev['SIGNAL'] == SIGNAL_LONG, 'POS',
                              np.where(ev['SIGNAL'] == SIGNAL_SHORT, 'NEG', '')),
                     index=ev.index)


def dim_breakdown(ev: pd.DataFrame, sectors: pd.DataFrame, dim: str,
                  top_n: int | None = None) -> pd.DataFrame:
    """Upper/lower band crossings by classification dimension, sorted ascending
    so the biggest group lands at the top of a horizontal bar chart."""
    default = 'Unknown' if dim == 'COUNTRY' else 'Unclassified'
    sig = signalled(ev)
    if sig.empty:
        return pd.DataFrame(columns=['POS', 'NEG', 'TOT'])
    sig = sig.assign(_DIR=signal_dir(sig))
    if sectors is not None and not sectors.empty and dim in sectors.columns:
        sig = sig.merge(sectors[['TICKER', dim]].drop_duplicates('TICKER'),
                        on='TICKER', how='left')
    else:
        sig = sig.assign(**{dim: default})
    sig[dim] = sig[dim].fillna(default)

    g = sig.groupby([dim, '_DIR']).size().unstack(fill_value=0)
    for col in ('POS', 'NEG'):
        if col not in g:
            g[col] = 0
    g['TOT'] = g['POS'] + g['NEG']
    g = g.sort_values('TOT', ascending=True)
    return g.tail(top_n) if top_n else g


def period_breakdown(ev: pd.DataFrame) -> pd.DataFrame:
    sig = signalled(ev)
    if sig.empty:
        return pd.DataFrame(columns=['POS', 'NEG'])
    g = (sig.assign(_DIR=signal_dir(sig)).groupby(['QUARTER', '_DIR'])
            .size().unstack(fill_value=0))
    for col in ('POS', 'NEG'):
        if col not in g:
            g[col] = 0
    return g.sort_index()


def category_table(ev: pd.DataFrame, cfg: Config = CFG) -> pd.DataFrame:
    """Reaction and post-event drift per severity bucket -- the PEAD lens."""
    rat = rated(ev)
    if rat.empty:
        return pd.DataFrame()
    fwd = [f'FWD_{h}D' for h in cfg.horizons]
    rows = []
    for cat in CAT_ORDER:
        g = rat[rat.CATEGORY == cat]
        if g.empty:
            continue
        row = dict(Category=cat, N=len(g),
                   AvgSigma=g.SIGMA.mean(),
                   React=g['RET(%)'].mean(),
                   Abn=g['ABN_RET(%)'].mean(),
                   Signals=len(signalled(g)),
                   HitRate=(_hit_rate(g) if cat != STATUS_INLINE else np.nan))
        for col in fwd:
            row[col] = g[col].mean() if col in g.columns else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


SIGNAL_GROUP_UP = 'Positive — closed through the upper band'
SIGNAL_GROUP_DOWN = 'Negative — closed through the lower band'
SIGNAL_GROUP_NONE = 'No band cross'


def signal_table(ev: pd.DataFrame, cfg: Config = CFG) -> pd.DataFrame:
    """What each kind of print paid, split by what the band did.

    The first two rows are the surprises — the prints that left the range. The
    last row is every print that stayed inside it, and is the comparison that
    matters: if a print that never crossed the band drifts as far as one that
    did, the band is not telling you anything.
    """
    if ev.empty or 'SIGNAL' not in ev.columns:
        return pd.DataFrame()
    fwd = [f'FWD_{h}D' for h in cfg.horizons]
    groups = [
        (SIGNAL_GROUP_UP, ev[ev.SIGNAL == SIGNAL_LONG]),
        (SIGNAL_GROUP_DOWN, ev[ev.SIGNAL == SIGNAL_SHORT]),
        (SIGNAL_GROUP_NONE, ev[ev.SIGNAL == SIGNAL_NONE]),
    ]
    rows = []
    for name, g in groups:
        if g.empty:
            continue
        agrees = ((g['SUE_AGREES'] == AGREE_YES).sum()
                  / max((g['SUE_AGREES'] != AGREE_NA).sum(), 1)
                  if 'SUE_AGREES' in g.columns else np.nan)
        row = dict(Group=name, N=len(g), AvgSigma=g.SIGMA.mean(),
                   React=g['RET(%)'].mean(), Abn=g['ABN_RET(%)'].mean(),
                   SueAgrees=agrees)
        for col in fwd:
            row[col] = g[col].mean() if col in g.columns else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def drift_summary(tbl: pd.DataFrame, cfg: Config = CFG) -> str:
    """One-line read on whether leaving the range paid, in this window."""
    if tbl is None or tbl.empty:
        return ''
    col = f'FWD_{cfg.horizons[1]}D' if len(cfg.horizons) > 1 else f'FWD_{cfg.horizons[0]}D'
    if col not in tbl.columns:
        return ''
    idx = tbl.set_index('Group')
    horizon = col.replace('FWD_', '').replace('D', 'D')
    parts = []
    for group, tag in ((SIGNAL_GROUP_UP, 'Upper break'),
                       (SIGNAL_GROUP_DOWN, 'Lower break'),
                       (SIGNAL_GROUP_NONE, 'No cross')):
        if group in idx.index and np.isfinite(idx.loc[group, col]):
            parts.append(f"{tag} <b>{idx.loc[group, col]:+.2f}%</b>")
    if not parts:
        return ''
    return (f"Mean {horizon} drift after the reaction window — "
            + " &nbsp;·&nbsp; ".join(parts) +
            " &nbsp;(a break that keeps going is the tradeable case; compare "
            "each against the prints that stayed inside the band).")


def radar_table(ev: pd.DataFrame, sectors: pd.DataFrame,
                next_earnings: pd.DataFrame, n: int = 15,
                cfg: Config = CFG) -> pd.DataFrame:
    """Soonest upcoming reporters, each carrying its own band history over the
    selected window — how often this name's reports have left its range, which
    way, and what happened after."""
    next_earnings = _with_ticker(next_earnings)
    if next_earnings is None or 'NEXT_EARNINGS_DATE' not in next_earnings.columns:
        return pd.DataFrame()
    today = pd.Timestamp.now().normalize()
    nx = next_earnings.copy()
    nx['NEXT_EARNINGS_DATE'] = pd.to_datetime(nx['NEXT_EARNINGS_DATE'], errors='coerce')
    upcoming = (nx.dropna(subset=['NEXT_EARNINGS_DATE'])
                  .loc[lambda d: d.NEXT_EARNINGS_DATE >= today]
                  .sort_values('NEXT_EARNINGS_DATE')
                  .drop_duplicates('TICKER')
                  .head(n).copy())
    if upcoming.empty:
        return upcoming

    drift = f'FWD_{cfg.horizons[1]}D' if len(cfg.horizons) > 1 else f'FWD_{cfg.horizons[0]}D'
    stats = ev.groupby('TICKER').agg(
        Prints=('SIGNAL', 'size'),
        Crossings=('SIGNAL', lambda s: int(s.isin(ACTIVE_SIGNALS).sum())),
        Upper=('SIGNAL', lambda s: int((s == SIGNAL_LONG).sum())),
        Lower=('SIGNAL', lambda s: int((s == SIGNAL_SHORT).sum())),
    ).reset_index()
    sig = signalled(ev)
    if not sig.empty:
        paid = sig.groupby('TICKER').agg(
            AvgReact=('RET(%)', 'mean'),
            AvgDrift=(drift, 'mean') if drift in sig.columns else ('RET(%)', 'mean'),
        ).reset_index()
        stats = stats.merge(paid, on='TICKER', how='left')
    stats['CrossRate'] = np.where(stats['Prints'] > 0,
                                  stats['Crossings'] / stats['Prints'], np.nan)
    stats['Tendency'] = np.where(stats.Crossings == 0, '—',
                                 np.where(stats.Upper == stats.Lower, 'MIXED',
                                          np.where(stats.Upper > stats.Lower,
                                                   'POS', 'NEG')))

    out = upcoming.merge(stats, on='TICKER', how='left')
    if sectors is not None and not sectors.empty:
        cols = ['TICKER'] + [c for c in ('SECTOR', 'MKT_CAP_USD') if c in sectors.columns]
        out = out.merge(sectors[cols].drop_duplicates('TICKER'), on='TICKER', how='left')
    for col, default in (('SECTOR', 'Unclassified'), ('Tendency', '—')):
        out[col] = out[col].fillna(default) if col in out.columns else default
    out['DISPLAY_NAME'] = out['NAME'] if 'NAME' in out.columns else out['TICKER']
    out['DAYS_AWAY'] = (out['NEXT_EARNINGS_DATE'] - today).dt.days
    return out


# ══════════════════════════════════════════════════════════════════════
# ASSET CATALOG + SEARCH
# One searchable row per constituent per loaded index. Built from the store,
# so it spans every index the session has data for and a search can cross
# index boundaries -- typing "SAP" finds it in the DAX even while the gallery
# is showing the S&P.
# ══════════════════════════════════════════════════════════════════════
CATALOG_COLUMNS = [
    'CODE', 'INDEX', 'TICKER', 'ID', 'EXCHANGE', 'NAME', 'SECTOR', 'COUNTRY',
    'MKT_CAP_USD', 'N_PRINTS', 'N_SURPRISES', 'SURPRISE_RATE', 'N_SIGNALS',
    'LAST_DATE', 'LAST_CATEGORY', 'LAST_STATUS', 'LAST_DIR', 'LAST_SIGMA',
    'LAST_RET', 'LAST_SIGNAL', 'LAST_CROSS', 'NEXT_DATE', 'DAYS_SINCE',
    'DAYS_TO_NEXT',
]
_SEARCH_COLUMNS = ['_TICKER_F', '_NAME_F', '_NUM', '_KEY']


def _with_ticker(df):
    """Guarantee a TICKER column, deriving it from the Bloomberg ID when a
    frame predates it. Returns None for anything unusable."""
    if df is None or df.empty:
        return None
    if 'TICKER' in df.columns:
        return df
    if 'ID' not in df.columns:
        return None
    out = df.copy()
    out['TICKER'] = out['ID'].map(short_ticker)
    return out


def _catalog_for(store, code: str, cfg: Config = CFG) -> pd.DataFrame:
    events = store.get(code, 'events')
    if events is None or events.empty:
        return pd.DataFrame(columns=CATALOG_COLUMNS)
    ev = prepare(events)
    rat = rated(ev)

    per_name = ev.sort_values('DATE').groupby('TICKER')
    latest = per_name.tail(1).set_index('TICKER')
    counts = rat.groupby('TICKER').agg(
        N_PRINTS=('STATUS', 'size'),
        N_SURPRISES=('STATUS', lambda s: int(s.isin(SURPRISE_STATUS).sum())))
    # Band crossings are counted over every print: an unrated print can still
    # leave its range, and that is the event.
    counts = counts.join(ev.groupby('TICKER')['SIGNAL'].apply(
        lambda s: int(s.isin(ACTIVE_SIGNALS).sum())).rename('N_SIGNALS'))

    base = pd.DataFrame({'TICKER': sorted(ev['TICKER'].unique())})
    base['CODE'] = code
    base['INDEX'] = cfg.label(code)
    base = base.join(counts, on='TICKER')
    for col in ('N_PRINTS', 'N_SURPRISES', 'N_SIGNALS'):
        base[col] = base[col].fillna(0).astype(int)
    base['SURPRISE_RATE'] = np.where(base['N_PRINTS'] > 0,
                                     base['N_SURPRISES'] / base['N_PRINTS'], np.nan)

    for col, src in (('LAST_DATE', 'DATE'), ('LAST_CATEGORY', 'CATEGORY'),
                     ('LAST_STATUS', 'STATUS'), ('LAST_DIR', 'DIR'),
                     ('LAST_SIGMA', 'SIGMA'), ('LAST_RET', 'RET(%)'),
                     ('LAST_SIGNAL', 'SIGNAL'), ('LAST_CROSS', 'BB_CROSS'),
                     ('NAME', 'NAME'), ('ID', 'ID')):
        base[col] = base['TICKER'].map(latest[src]) if src in latest.columns else np.nan

    sectors = store.get(code, 'sectors')
    if sectors is not None and not sectors.empty:
        keep = ['TICKER'] + [c for c in ('SECTOR', 'COUNTRY', 'MKT_CAP_USD', 'ID', 'NAME')
                             if c in sectors.columns]
        meta = sectors[keep].drop_duplicates('TICKER')
        base = base.merge(meta, on='TICKER', how='left', suffixes=('', '_S'))
        for col in ('ID', 'NAME'):                     # sectors is the better source
            if f'{col}_S' in base.columns:
                base[col] = base[f'{col}_S'].fillna(base[col])
                base = base.drop(columns=[f'{col}_S'])

    nxt = _with_ticker(store.get(code, 'next_earnings'))
    if nxt is not None and 'NEXT_EARNINGS_DATE' in nxt.columns:
        nx = nxt.drop_duplicates('TICKER').set_index('TICKER')['NEXT_EARNINGS_DATE']
        base['NEXT_DATE'] = pd.to_datetime(base['TICKER'].map(nx), errors='coerce')

    for col, default in (('SECTOR', 'Unclassified'), ('COUNTRY', 'Unknown')):
        base[col] = base[col].fillna(default) if col in base.columns else default
    for col in ('MKT_CAP_USD', 'NEXT_DATE', 'ID', 'NAME'):
        if col not in base.columns:
            base[col] = np.nan
    base['NAME'] = base['NAME'].fillna(base['TICKER'])
    base['EXCHANGE'] = base['ID'].map(exchange_code)

    today = pd.Timestamp.now().normalize()
    base['DAYS_SINCE'] = (today - pd.to_datetime(base['LAST_DATE'])).dt.days
    base['DAYS_TO_NEXT'] = (pd.to_datetime(base['NEXT_DATE']) - today).dt.days
    return base[CATALOG_COLUMNS]


def build_catalog(store, cfg: Config = CFG, codes=None) -> pd.DataFrame:
    """Searchable catalog across every index with data in memory or on disk.

    Codes come from universe_options(), not Config.universes, so an index
    registered at runtime is searchable like any built-in one.
    """
    codes = codes or [code for _, code in cfg.universe_options()]
    frames = [_catalog_for(store, code, cfg) for code in codes]
    frames = [f for f in frames if not f.empty]
    if not frames:
        return pd.DataFrame(columns=CATALOG_COLUMNS + _SEARCH_COLUMNS)
    cat = pd.concat(frames, ignore_index=True)

    # Pre-folded keys: search runs on every keystroke, so the normalisation
    # cost is paid once here rather than per query.
    cat['_TICKER_F'] = cat['TICKER'].map(fold_text)
    cat['_NAME_F'] = cat['NAME'].map(fold_text)
    cat['_NUM'] = cat['TICKER'].map(numeric_key)
    cat['_KEY'] = (cat['_TICKER_F'] + ' ' + cat['_NAME_F'] + ' '
                   + cat['SECTOR'].map(fold_text) + ' '
                   + cat['COUNTRY'].map(fold_text) + ' '
                   + cat['INDEX'].map(fold_text) + ' '
                   + cat['CODE'].map(fold_text) + ' '
                   + cat['EXCHANGE'].map(fold_text))
    return cat


def search_catalog(catalog: pd.DataFrame, query: str,
                   limit: int = 200) -> pd.DataFrame:
    """Rank catalog rows against a free-text query.

    Every whitespace-separated token must match somewhere (so "dax sap" and
    "france luxury" both narrow correctly), and each token scores by how
    specific its match was -- an exact ticker beats a name prefix, which beats
    a substring anywhere in the row.
    """
    if catalog.empty:
        return catalog
    tokens = [fold_text(t) for t in str(query).split()]
    tokens = [t for t in tokens if t]
    if not tokens:
        return catalog

    tick, name = catalog['_TICKER_F'], catalog['_NAME_F']
    num, key = catalog['_NUM'], catalog['_KEY']
    score = pd.Series(0.0, index=catalog.index)
    keep = pd.Series(True, index=catalog.index)

    for tok in tokens:
        conds = [tick.eq(tok)]
        vals = [140.0]
        if tok.isdigit():                       # numeric markets: 5930 == 005930
            stripped = tok.lstrip('0') or '0'
            conds += [num.eq(stripped), num.str.startswith(stripped) & num.ne('')]
            vals += [140.0, 95.0]
        conds += [tick.str.startswith(tok),
                  name.str.startswith(tok),
                  name.str.contains(f' {tok}', regex=False),
                  name.str.contains(tok, regex=False),
                  key.str.contains(tok, regex=False)]
        vals += [100.0, 80.0, 70.0, 50.0, 25.0]
        token_score = pd.Series(np.select(conds, vals, default=0.0),
                                index=catalog.index)
        keep &= token_score > 0
        score += token_score

    out = catalog[keep].copy()
    out['_SCORE'] = score[keep]
    return out.sort_values(['_SCORE', 'MKT_CAP_USD'],
                           ascending=[False, False]).head(limit)


# Filters phrased the way a user would ask for them. Each maps to a predicate
# over catalog rows; 'recent' is defined against the data's own calendar via
# DAYS_SINCE / DAYS_TO_NEXT rather than a hard-coded date.
ASSET_FILTERS = [
    ('All constituents',                    'ALL'),
    ('Latest print · surprise',             'LAST_SURPRISE'),
    ('Latest print · positive surprise',    'LAST_POS'),
    ('Latest print · negative surprise',    'LAST_NEG'),
    ('Latest print · major surprise',       'LAST_MAJOR'),
    ('Latest print · band signal',          'LAST_SIGNAL'),
    ('Latest print · long signal',          'LAST_LONG'),
    ('Latest print · short signal',         'LAST_SHORT'),
    ('Reported in last 30 days',            'RECENT_30'),
    ('Reporting in next 30 days',           'UPCOMING_30'),
    ('Frequent surprisers (≥50%)',          'FREQUENT'),
]

# Filters that ask a question about the most recent print. Picking one means
# "show me who just did this", so the chart opens on that print rather than on
# five years of history the question was not about.
LATEST_FILTERS = {'LAST_SURPRISE', 'LAST_POS', 'LAST_NEG', 'LAST_MAJOR',
                  'LAST_SIGNAL', 'LAST_LONG', 'LAST_SHORT'}


def apply_asset_filter(catalog: pd.DataFrame, key: str) -> pd.DataFrame:
    if catalog.empty or key == 'ALL':
        return catalog
    c = catalog
    if key == 'LAST_SURPRISE':
        return c[c.LAST_STATUS.isin(SURPRISE_STATUS)]
    if key == 'LAST_POS':
        return c[c.LAST_STATUS.isin(SURPRISE_STATUS) & (c.LAST_DIR == 'POS')]
    if key == 'LAST_NEG':
        return c[c.LAST_STATUS.isin(SURPRISE_STATUS) & (c.LAST_DIR == 'NEG')]
    if key == 'LAST_MAJOR':
        return c[c.LAST_STATUS == STATUS_MAJOR]
    if key == 'LAST_SIGNAL':
        return c[c.LAST_SIGNAL.isin(ACTIVE_SIGNALS)]
    if key == 'LAST_LONG':
        return c[c.LAST_SIGNAL == SIGNAL_LONG]
    if key == 'LAST_SHORT':
        return c[c.LAST_SIGNAL == SIGNAL_SHORT]
    if key == 'RECENT_30':
        return c[c.DAYS_SINCE.between(0, 30)]
    if key == 'UPCOMING_30':
        return c[c.DAYS_TO_NEXT.between(0, 30)]
    if key == 'FREQUENT':
        return c[(c.SURPRISE_RATE >= 0.5) & (c.N_PRINTS >= 4)]
    return c


ASSET_SORTS = [
    ('Best match',        'REL'),
    ('Ticker A–Z',        'TICKER'),
    ('Company A–Z',       'NAME'),
    ('Market cap',        'CAP'),
    ('Latest surprise |σ|', 'SIGMA'),
    ('Band signals',      'SIGNALS'),
    ('Next report date',  'NEXT'),
]


def sort_catalog(catalog: pd.DataFrame, key: str) -> pd.DataFrame:
    if catalog.empty:
        return catalog
    if key == 'REL':
        # Relevance only exists for a scored (searched) frame; without a query
        # the most useful default ordering is size.
        if '_SCORE' in catalog.columns:
            return catalog
        key = 'CAP'
    specs = {
        'TICKER':  (['_TICKER_F'], [True]),
        'NAME':    (['_NAME_F'], [True]),
        'CAP':     (['MKT_CAP_USD'], [False]),
        'SIGNALS': (['N_SIGNALS', 'MKT_CAP_USD'], [False, False]),
        'NEXT':    (['DAYS_TO_NEXT'], [True]),
    }
    if key == 'SIGMA':
        return catalog.assign(_ABS=catalog['LAST_SIGMA'].abs()).sort_values(
            '_ABS', ascending=False, na_position='last').drop(columns='_ABS')
    cols, asc = specs.get(key, (['_TICKER_F'], [True]))
    return catalog.sort_values(cols, ascending=asc, na_position='last')


print('Analytics layer ready — kpis · breakdowns · category_table · signal_table '
      '· radar_table · catalog + search')
