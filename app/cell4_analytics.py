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


def kpis(ev: pd.DataFrame) -> dict:
    rat = rated(ev)
    sur = surprises(rat)
    pos, neg = sur[sur.DIR == 'POS'], sur[sur.DIR == 'NEG']
    sig = signalled(ev)
    agree = (int((sig['SUE_AGREES'] == AGREE_YES).sum())
             if 'SUE_AGREES' in sig.columns and len(sig) else 0)
    disagree = (int((sig['SUE_AGREES'] == AGREE_NO).sum())
                if 'SUE_AGREES' in sig.columns and len(sig) else 0)
    return dict(
        total=len(rat),
        unrated=int((ev['STATUS'] == STATUS_UNRATED).sum()) if not ev.empty else 0,
        surprises=len(sur),
        rate=(len(sur) / len(rat) if len(rat) else np.nan),
        major=int((rat.STATUS == STATUS_MAJOR).sum()),
        moderate=int((rat.STATUS == STATUS_MODERATE).sum()),
        inline=int((rat.STATUS == STATUS_INLINE).sum()),
        n_pos=len(pos), n_neg=len(neg),
        avg_ret_pos=pos['RET(%)'].mean(), avg_ret_neg=neg['RET(%)'].mean(),
        avg_abn_pos=pos['ABN_RET(%)'].mean(), avg_abn_neg=neg['ABN_RET(%)'].mean(),
        pos_hit=_hit_rate(pos), neg_hit=_hit_rate(neg), hit=_hit_rate(sur),
        signals=len(sig),
        n_long=int((sig['SIGNAL'] == SIGNAL_LONG).sum()) if len(sig) else 0,
        n_short=int((sig['SIGNAL'] == SIGNAL_SHORT).sum()) if len(sig) else 0,
        sue_agrees=agree, sue_disagrees=disagree,
        signal_rate=(len(sig) / len(ev) if len(ev) else np.nan),
        pending=int((rat['RET(%)'].isna()).sum()) if len(rat) else 0,
        analyst_share=((rat.SUE_SOURCE == 'analyst').mean()
                       if 'SUE_SOURCE' in rat.columns and len(rat) else np.nan),
    )


# ─────────────────────────────────────────────────────────────
# BREAKDOWNS
# ─────────────────────────────────────────────────────────────
def dim_breakdown(ev: pd.DataFrame, sectors: pd.DataFrame, dim: str,
                  top_n: int | None = None) -> pd.DataFrame:
    """Positive/negative surprise counts by classification dimension, sorted
    ascending so the biggest group lands at the top of a horizontal bar chart."""
    default = 'Unknown' if dim == 'COUNTRY' else 'Unclassified'
    sur = surprises(rated(ev))
    if sur.empty:
        return pd.DataFrame(columns=['POS', 'NEG', 'TOT'])
    if sectors is not None and not sectors.empty and dim in sectors.columns:
        sur = sur.merge(sectors[['TICKER', dim]].drop_duplicates('TICKER'),
                        on='TICKER', how='left')
    else:
        sur = sur.assign(**{dim: default})
    sur[dim] = sur[dim].fillna(default)

    g = sur.groupby([dim, 'DIR']).size().unstack(fill_value=0)
    for col in ('POS', 'NEG'):
        if col not in g:
            g[col] = 0
    g['TOT'] = g['POS'] + g['NEG']
    g = g.sort_values('TOT', ascending=True)
    return g.tail(top_n) if top_n else g


def period_breakdown(ev: pd.DataFrame) -> pd.DataFrame:
    sur = surprises(rated(ev))
    if sur.empty:
        return pd.DataFrame(columns=['POS', 'NEG'])
    g = sur.groupby(['QUARTER', 'DIR']).size().unstack(fill_value=0)
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
        ('Positive — closed through the upper band', ev[ev.SIGNAL == SIGNAL_LONG]),
        ('Negative — closed through the lower band', ev[ev.SIGNAL == SIGNAL_SHORT]),
        ('No band cross', ev[ev.SIGNAL == SIGNAL_NONE]),
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
    """One-line read on whether the drift is tradeable in this window."""
    if tbl.empty:
        return ''
    col = f'FWD_{cfg.horizons[1]}D' if len(cfg.horizons) > 1 else f'FWD_{cfg.horizons[0]}D'
    if col not in tbl.columns:
        return ''
    idx = tbl.set_index('Category')
    parts = []
    for cat, tag in (('Major +', 'Major&nbsp;+'), ('Major −', 'Major&nbsp;−')):
        if cat in idx.index and np.isfinite(idx.loc[cat, col]):
            parts.append(f"{tag} {col.replace('FWD_','').replace('D','D')} drift "
                         f"<b>{idx.loc[cat, col]:+.2f}%</b>")
    if not parts:
        return ''
    return ("Post-event drift — " + " &nbsp;·&nbsp; ".join(parts) +
            " &nbsp;(continuation in the direction of the surprise is the "
            "tradeable PEAD signature).")


def radar_table(ev: pd.DataFrame, sectors: pd.DataFrame,
                next_earnings: pd.DataFrame, n: int = 15) -> pd.DataFrame:
    """Soonest upcoming reporters, each carrying its own historical tendency
    over the selected window -- the forward-looking half of the dashboard."""
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

    rat = rated(ev)
    stats = rat.groupby('TICKER').agg(
        Prints=('STATUS', 'size'),
        Surprises=('STATUS', lambda s: int(s.isin(SURPRISE_STATUS).sum())),
        AvgSigma=('SIGMA', 'mean'),
        AvgRet=('RET(%)', 'mean'),
    ).reset_index()
    if 'SIGNAL' in ev.columns:
        sig = (ev.assign(_sig=ev['SIGNAL'].isin(ACTIVE_SIGNALS))
                 .groupby('TICKER')['_sig'].sum().astype(int)
                 .rename('Signals').reset_index())
        stats = stats.merge(sig, on='TICKER', how='left')

    sur = surprises(rat)
    if sur.empty:
        tend = pd.DataFrame(columns=['TICKER', 'Tendency', 'HitRate'])
    else:
        counts = sur.groupby(['TICKER', 'DIR']).size().unstack(fill_value=0)
        for col in ('POS', 'NEG'):
            if col not in counts:
                counts[col] = 0
        tend = counts.assign(
            Tendency=np.where(counts.POS == counts.NEG, 'MIXED',
                              np.where(counts.POS > counts.NEG, 'POS', 'NEG'))
        ).reset_index()[['TICKER', 'Tendency']]
        agree = np.where(sur['DIR'] == 'POS', sur['RET(%)'] > 0, sur['RET(%)'] < 0)
        hits = (sur.assign(_agree=agree).groupby('TICKER')['_agree']
                   .mean().rename('HitRate').reset_index())
        tend = tend.merge(hits, on='TICKER', how='left')

    out = (upcoming.merge(stats, on='TICKER', how='left')
                   .merge(tend, on='TICKER', how='left'))
    if sectors is not None and not sectors.empty:
        cols = ['TICKER'] + [c for c in ('SECTOR', 'MKT_CAP_USD') if c in sectors.columns]
        out = out.merge(sectors[cols].drop_duplicates('TICKER'), on='TICKER', how='left')
    for col, default in (('SECTOR', 'Unclassified'), ('Tendency', '—')):
        if col in out.columns:
            out[col] = out[col].fillna(default)
        else:
            out[col] = default
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
