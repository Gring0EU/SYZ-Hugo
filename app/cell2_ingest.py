# ══════════════════════════════════════════════════════════════════════
# CELL 2 — STEP 1: LIVE INGEST
# Every dataset the rest of the system needs, pulled live from BQL in five
# passes over one resolved universe:
#   1. constituents          4. next scheduled report date
#   2. daily prices + bench  5. GICS sector / industry / country / mkt cap
#   3. quarterly EPS actual + pre-announcement consensus
# Results land in STORE, so nothing downstream ever re-queries Bloomberg.
# ══════════════════════════════════════════════════════════════════════
import numpy as np
import pandas as pd
from IPython.display import HTML, display


# ─────────────────────────────────────────────────────────────
# PRICES
# ─────────────────────────────────────────────────────────────
def _price_field(client=BQ):
    return client.data.px_last(
        dates=client.func.range(client.cfg.lookback, client.cfg.today),
        fill='prev')


def _normalise_prices(raw: pd.DataFrame) -> pd.DataFrame:
    date_col = pick_column(raw, 'DATE', exclude=('AS_OF',)) or 'DATE'
    val_col = pick_column(raw, 'px_last', 'PX_LAST') or raw.columns[-1]
    out = pd.DataFrame({
        'DATE': pd.to_datetime(raw[date_col], errors='coerce'),
        'ID': raw['ID'].astype(str),
        'PX_LAST': pd.to_numeric(raw[val_col], errors='coerce'),
    })
    out['TICKER'] = out['ID'].map(short_ticker)
    return (out.dropna(subset=['DATE'])
               .drop_duplicates(subset=['ID', 'DATE'], keep='last')
               .sort_values(['ID', 'DATE'])
               .reset_index(drop=True))


def canonical_listings(long: pd.DataFrame, report: Reporter) -> pd.DataFrame:
    """One listing per short ticker: the one with the deepest price history.

    Short ticker is the join key across every table in the system, so an index
    carrying two listings of the same code (a dual listing, or a line that
    changed venue) has to be resolved *once*, here. Resolving it only inside
    the price pivot would leave duplicate EPS prints downstream and double-count
    that name in every aggregate.
    """
    coverage = (long.groupby(['TICKER', 'ID'])['PX_LAST'].count()
                    .reset_index()
                    .sort_values(['PX_LAST', 'ID'], ascending=[False, True]))
    keep = coverage.drop_duplicates('TICKER', keep='first')[['TICKER', 'ID']]
    dropped = len(coverage) - len(keep)
    if dropped:
        report(f"-> {dropped} duplicate short ticker(s) collapsed to the "
               f"listing with the deepest history", indent=1)
    return keep.reset_index(drop=True)


def _pivot_prices(long: pd.DataFrame) -> pd.DataFrame:
    """DATE x TICKER close matrix, keyed on the short ticker."""
    wide = long.pivot(index='DATE', columns='TICKER', values='PX_LAST')
    wide.columns.name = None
    return wide.sort_index()


def fetch_prices(tickers, client=BQ, report=None):
    """Returns (long, wide, canonical) -- canonical is the TICKER -> ID map
    every other dataset is filtered through."""
    report = report or client.report
    raw = client.fetch(tickers, {'px_last': _price_field(client)},
                       label='prices', batch_size=client.cfg.price_batch_size)
    if raw.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(columns=['TICKER', 'ID'])
    long = _normalise_prices(raw)
    canonical = canonical_listings(long, report)
    long = long.merge(canonical, on=['TICKER', 'ID'], how='inner')
    return long, _pivot_prices(long), canonical


def fetch_benchmark(index_ticker: str, client=BQ) -> pd.DataFrame:
    """Index level on the same calendar — lets the event engine express the
    announcement reaction as an abnormal (market-adjusted) return."""
    try:
        raw = client.fetch([index_ticker], {'px_last': _price_field(client)},
                           label='benchmark')
        if raw.empty:
            return pd.DataFrame()
        long = _normalise_prices(raw)
        return (long.set_index('DATE')[['PX_LAST']]
                    .rename(columns={'PX_LAST': 'BENCHMARK'})
                    .sort_index())
    except Exception as exc:
        client.report(f"-> benchmark unavailable ({exc}); reactions will be "
                      f"raw rather than market-adjusted", indent=1)
        return pd.DataFrame()


# ─────────────────────────────────────────────────────────────
# QUARTERLY EPS — actuals and pre-announcement consensus
# ─────────────────────────────────────────────────────────────
def _eps_builders(client=BQ):
    """Candidate consensus fields, tried in order. Field availability varies
    by entitlement, so we probe rather than assume."""
    span = client.func.range(f'-{client.cfg.n_quarters}Q', '0Q')
    common = dict(fpt='Q', fpo=span)
    return (
        ('actual', lambda: client.data.is_eps(fa_act_est_data='A', **common)),
        ('estimate', lambda: client.data.is_eps(fa_act_est_data='E', **common)),
        ('estimate_best', lambda: client.data.best_eps(**common)),
    )


def _normalise_eps(raw: pd.DataFrame, value_alias: str, value_name: str) -> pd.DataFrame:
    """Tidy an EPS period-series response.

    Announcement date is resolved by preference; PERIOD_END is kept separately
    because fiscal-period alignment -- not the announcement calendar -- is what
    makes actual-vs-estimate and year-over-year comparisons correct.
    """
    ann_col = pick_column(raw, 'ANNOUNC', 'REPORT', 'REVISION_DATE',
                          exclude=('AS_OF',))
    end_col = pick_column(raw, 'PERIOD_END')
    val_col = value_alias if value_alias in raw.columns else raw.columns[-1]

    out = pd.DataFrame({
        'ID': raw['ID'].astype(str),
        'PERIOD_END': pd.to_datetime(raw[end_col], errors='coerce') if end_col else pd.NaT,
        'ANNOUNCE_DATE': pd.to_datetime(raw[ann_col], errors='coerce') if ann_col else pd.NaT,
        value_name: pd.to_numeric(raw[val_col], errors='coerce'),
    })
    # Fall back to period end where no announcement stamp came back, so a
    # missing metadata column costs precision rather than the whole print.
    out['ANNOUNCE_DATE'] = out['ANNOUNCE_DATE'].fillna(out['PERIOD_END'])
    out['TICKER'] = out['ID'].map(short_ticker)
    return out


def fetch_eps_history(tickers, client=BQ, report=None) -> pd.DataFrame:
    """Quarterly EPS actuals joined to the matching consensus estimate."""
    report = report or client.report
    builders = dict(_eps_builders(client))

    raw_act = client.fetch(tickers, {'eps_act': builders['actual']()},
                           label='EPS actual')
    if raw_act.empty:
        return pd.DataFrame()
    actual = _normalise_eps(raw_act, 'eps_act', 'EPS_ACT')
    actual = (actual.dropna(subset=['ANNOUNCE_DATE'])
                    .sort_values(['ID', 'PERIOD_END', 'ANNOUNCE_DATE'])
                    .drop_duplicates(subset=['ID', 'PERIOD_END'], keep='last'))

    estimate = pd.DataFrame()
    for key in ('estimate', 'estimate_best'):
        try:
            raw_est = client.fetch(tickers, {'eps_est': builders[key]()},
                                   label=f'EPS {key}')
            if raw_est.empty:
                continue
            estimate = _normalise_eps(raw_est, 'eps_est', 'EPS_EST')
            estimate = (estimate.dropna(subset=['PERIOD_END'])
                                .sort_values(['ID', 'PERIOD_END'])
                                .drop_duplicates(subset=['ID', 'PERIOD_END'],
                                                 keep='last'))
            report(f"-> consensus source: {key}", indent=1)
            break
        except Exception as exc:
            report(f"-> {key} unavailable ({exc})", indent=1)

    if estimate.empty:
        report("-> no consensus available; surprises will use the "
               "time-series (Foster-Olsen-Shevlin) model", indent=1)
        actual['EPS_EST'] = np.nan
    else:
        actual = actual.merge(estimate[['ID', 'PERIOD_END', 'EPS_EST']],
                              on=['ID', 'PERIOD_END'], how='left')

    return (actual[['ID', 'TICKER', 'PERIOD_END', 'ANNOUNCE_DATE',
                    'EPS_ACT', 'EPS_EST']]
            .sort_values(['ID', 'ANNOUNCE_DATE'])
            .reset_index(drop=True))


# ─────────────────────────────────────────────────────────────
# FORWARD-LOOKING + CLASSIFICATION
# ─────────────────────────────────────────────────────────────
def fetch_next_earnings(tickers, client=BQ) -> pd.DataFrame:
    try:
        raw = client.fetch(tickers, {'next_dt': client.data.expected_report_dt()},
                           label='next report')
    except Exception as exc:
        client.report(f"-> expected_report_dt unavailable ({exc})", indent=1)
        return pd.DataFrame(columns=['ID', 'TICKER', 'NEXT_EARNINGS_DATE'])
    if raw.empty:
        return pd.DataFrame(columns=['ID', 'TICKER', 'NEXT_EARNINGS_DATE'])
    val = 'next_dt' if 'next_dt' in raw.columns else raw.columns[-1]
    out = pd.DataFrame({
        'ID': raw['ID'].astype(str),
        'NEXT_EARNINGS_DATE': pd.to_datetime(raw[val], errors='coerce'),
    })
    out['TICKER'] = out['ID'].map(short_ticker)
    return (out.dropna(subset=['NEXT_EARNINGS_DATE'])
               .drop_duplicates('ID')
               .reset_index(drop=True))


def fetch_classification(tickers, client=BQ) -> pd.DataFrame:
    """GICS sector + industry, country of domicile and USD market cap.
    Industry gives the dashboard a drill-down below sector; country gives it a
    geographic cut; market cap lets any statistic be size-weighted."""
    fields = {
        'sector':   client.data.gics_sector_name(),
        'industry': client.data.gics_industry_name(),
        'country':  client.data.cntry_of_domicile(),
        'mktcap':   client.data.cur_mkt_cap(currency='USD'),
    }
    raw = client.fetch(tickers, fields, label='classification')
    if raw.empty:
        return pd.DataFrame(columns=['ID', 'TICKER', 'SECTOR', 'INDUSTRY',
                                     'COUNTRY', 'MKT_CAP_USD'])

    def col(alias, default):
        if alias in raw.columns:
            return raw[alias].fillna(default)
        return pd.Series(default, index=raw.index)

    out = pd.DataFrame({
        'ID': raw['ID'].astype(str),
        'SECTOR': col('sector', 'Unclassified'),
        'INDUSTRY': col('industry', 'Unclassified'),
        'COUNTRY': col('country', 'Unknown'),
        'MKT_CAP_USD': pd.to_numeric(raw['mktcap'], errors='coerce')
        if 'mktcap' in raw.columns else np.nan,
    })
    out['TICKER'] = out['ID'].map(short_ticker)
    return out.drop_duplicates('ID').reset_index(drop=True)


# ─────────────────────────────────────────────────────────────
# ORCHESTRATION
# ─────────────────────────────────────────────────────────────
def _summary_card(code: str, label: str, bundle: dict, failed: dict) -> str:
    px = bundle['prices_wide']
    eps = bundle['earnings']
    cov = eps['EPS_EST'].notna().mean() if len(eps) else 0.0
    rows = [
        ('Constituents resolved', f"{bundle['universe_size']}"),
        ('Price matrix', f"{px.shape[0]:,} sessions x {px.shape[1]} names"
                         if not px.empty else '—'),
        ('Quarterly prints', f"{len(eps):,} "
                             f"(avg {len(eps)/max(bundle['universe_size'],1):.1f} per name)"),
        ('Consensus coverage', f"{cov:.0%} of prints"),
        ('Next report dates', f"{len(bundle['next_earnings'])}"),
        ('Securities dropped', f"{len(failed)}"),
    ]
    body = "".join(
        f"<div style='display:flex;justify-content:space-between;padding:5px 0;"
        f"border-bottom:1px solid {THEME.HAIRLINE}'>"
        f"<span style='font-weight:300'>{k}</span>"
        f"<span style='font-weight:700'>{v}</span></div>" for k, v in rows)
    head = (f"<div style='font-weight:800;font-size:16px;color:{THEME.SPACE_BLUE};"
            f"margin-bottom:8px'>Step 1 complete — {label} ({code})</div>")
    return THEME.panel(head + body, max_width='560px')


class IngestError(RuntimeError):
    """Failure during ingest, tagged with the stage that produced it."""


def _stage(report, n, total, message):
    """Context manager that names the stage in any exception it wraps, so a
    failure surfaces as 'Step 1/5 (resolving constituents): ...' instead of a
    bare message with no indication of which query broke."""
    import contextlib

    @contextlib.contextmanager
    def runner():
        report.step(n, total, f"{message}…")
        try:
            yield
        except Exception as exc:
            raise IngestError(f"stage {n}/{total} ({message}): {exc}") from exc
    return runner()


def probe_universes(codes=None, client=BQ, cfg: Config = CFG) -> pd.DataFrame:
    """Resolve constituents for each configured index and report what came back.

    A cheap pre-flight for exactly the case where an index ticker is wrong or
    unentitled: one members request per index, no price or fundamental data.
    """
    codes = codes or [code for _, code in cfg.universe_options()]
    quiet = Reporter(verbose=False)
    previous, client.report = client.report, quiet
    rows = []
    try:
        for code in codes:
            ticker = cfg.full_ticker(code)
            try:
                members = client.members(ticker)
                rows.append(dict(CODE=code, TICKER=ticker, MEMBERS=len(members),
                                 STATUS='ok' if len(members) else 'empty',
                                 DETAIL=', '.join(members['TICKER'].head(3)) if len(members) else ''))
            except Exception as exc:
                rows.append(dict(CODE=code, TICKER=ticker, MEMBERS=0,
                                 STATUS='failed', DETAIL=str(exc)[:160]))
    finally:
        client.report = previous
    return pd.DataFrame(rows)


def ingest(code: str, client=BQ, store=STORE, report: Reporter | None = None) -> dict:
    """Run the full live ingest for one index and publish it to the store."""
    report = report or Reporter()
    client.report = report
    client.failed = {}
    index_ticker = client.cfg.full_ticker(code)

    with _stage(report, 1, 5, f"Resolving {index_ticker} constituents"):
        members = client.members(index_ticker)
    tickers = members['ID'].tolist()
    if not tickers:
        raise IngestError(f"no constituents returned for {index_ticker}")

    with _stage(report, 2, 5, "Retrieving daily closes + benchmark level"):
        prices_long, prices_wide, canonical = fetch_prices(tickers, client, report)
        if prices_wide.empty:
            raise RuntimeError(f"no price history returned for {index_ticker}")
        benchmark = fetch_benchmark(index_ticker, client)

    with _stage(report, 3, 5, "Retrieving quarterly EPS actuals and consensus"):
        earnings = fetch_eps_history(tickers, client, report)

    with _stage(report, 4, 5, "Retrieving next scheduled report dates"):
        next_earnings = fetch_next_earnings(tickers, client)

    with _stage(report, 5, 5, "Retrieving GICS classification and market cap"):
        sectors = fetch_classification(tickers, client)

    # Align every dataset on the canonical listing set. A name with no usable
    # price history cannot produce a measurable reaction, so carrying its EPS
    # prints forward would only inflate counts.
    tradable = set(canonical['ID'])
    dropped = [t for t in tickers if t not in tradable and t not in client.failed]
    if dropped:
        report(f"-> {len(dropped)} name(s) excluded for lack of usable price "
               f"history", indent=1)
    earnings, next_earnings, sectors = (
        f[f['ID'].isin(tradable)].reset_index(drop=True) if not f.empty else f
        for f in (earnings, next_earnings, sectors))
    members = members[members['ID'].isin(tradable)].reset_index(drop=True)

    # Attach names once, here, so no downstream component needs the map.
    name_by_id = members.set_index('ID')['NAME'].to_dict()
    for frame in (earnings, next_earnings, sectors):
        if not frame.empty:
            frame['NAME'] = frame['ID'].map(name_by_id).fillna(frame['TICKER'])

    bundle = {
        'universe': members,
        'prices_long': prices_long, 'prices_wide': prices_wide,
        'benchmark': benchmark, 'earnings': earnings,
        'next_earnings': next_earnings, 'sectors': sectors,
        'universe_size': len(members),
    }
    for name in ('universe', 'prices_long', 'prices_wide', 'benchmark',
                 'earnings', 'next_earnings', 'sectors'):
        store.put(code, name, bundle[name])

    display(HTML(_summary_card(code, client.cfg.label(code), bundle, client.failed)))
    return bundle


print('Step 1 ready — ingest(code) · probe_universes()')
