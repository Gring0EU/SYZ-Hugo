# ══════════════════════════════════════════════════════════════════════
# CELL 1 — CORE LAYER
# Config · brand theme · BQL access layer · unified data store
# Everything downstream (ingest, event engine, gallery, dashboard) is built
# on these four objects, so there is exactly one place that talks to
# Bloomberg and exactly one place that holds data.
# ══════════════════════════════════════════════════════════════════════
from __future__ import annotations

import os
import time
import unicodedata
from dataclasses import dataclass, field
from typing import Callable, Mapping, Sequence

import numpy as np
import pandas as pd
from IPython.display import HTML, display

# ─────────────────────────────────────────────────────────────
# 1. CONFIGURATION  (single source of truth for every tunable)
# ─────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Config:
    # --- history windows -------------------------------------------------
    lookback: str = '-5Y'          # price history start, relative to today
    today: str = '0D'
    n_quarters: int = 24           # fiscal quarters of EPS (5Y + buffer)

    # --- request shaping -------------------------------------------------
    batch_size: int = 100          # cross-sectional (single point per name)
    price_batch_size: int = 50     # date-series requests are much heavier
    max_retries: int = 3
    backoff_base: float = 2.0

    # --- surprise classification ----------------------------------------
    major_sigma: float = 2.0       # |SUE| >= 2.0  -> Major Surprise
    moderate_sigma: float = 1.0    # |SUE| >= 1.0  -> Moderate Surprise
    min_sue_history: int = 4       # prior prints needed to standardise
    winsor_sigma: float = 8.0      # clip absurd SUE from stale/odd data
    sigma_floor: float = 0.01      # EPS dispersion floor, currency units.
    # Guards against the degenerate case where a name's surprises are almost
    # perfectly stable (a chronically biased consensus): the standard
    # deviation collapses toward zero and every print would score as a Major
    # surprise. One cent of EPS is treated as the smallest meaningful
    # dispersion, below which a beat is noise rather than information.

    # --- Bollinger band / overlays --------------------------------------
    bb_window: int = 100           # trading days of volatility in the band
    bb_sigma: float = 2.0          # band half-width, in standard deviations
    ma_window: int = 200
    # The band is measured over a fixed 100-session volatility window rather
    # than the conventional 20. A quarter of trading days spans the previous
    # earnings print, so the dispersion the band carries is the name's own
    # inter-earnings volatility, not the fortnight before the release. The
    # bands are correspondingly wider, which is the point: a cross of a
    # 100-day band is a genuine break out of the trading range, not a routine
    # two-week wobble, so it is a defensible confirmation of a surprise.

    # --- event window mechanics -----------------------------------------
    reaction_pre: int = 1          # trading days before announcement
    reaction_post: int = 1         # trading days after announcement
    horizons: tuple = (5, 20, 60)  # PEAD drift horizons (trading days)

    # --- persistence / caching ------------------------------------------
    data_dir: str = 'syz_data'
    persist: bool = True           # best-effort; auto-skips if read-only
    cache_ttl: int = 3600          # seconds before in-memory data is stale

    universes: tuple = (
        ('S&P 500',           'SPX',    'SPX Index'),
        ('Nasdaq 100',        'NDX',    'NDX Index'),
        ('Dow Jones',         'INDU',   'INDU Index'),
        ('Russell 2000',      'RTY',    'RTY Index'),
        ('Euro Stoxx 50',     'SX5E',   'SX5E Index'),
        ('STOXX Europe 600',  'SXXP',   'SXXP Index'),
        ('CAC 40',            'CAC',    'CAC Index'),
        ('DAX',               'DAX',    'DAX Index'),
        ('SMI (Switzerland)', 'SMI',    'SMI Index'),
        ('Swiss Performance', 'SPI',    'SPI Index'),
        ('KOSPI 200',         'KOSPI2', 'KOSPI2 Index'),
        ('Nikkei 225',        'NKY',    'NKY Index'),
    )

    # -- band helpers -----------------------------------------------------
    @property
    def bb_min_periods(self) -> int:
        """Sessions required before a band is drawn at all.

        A 100-day band seeded from two observations would open the history
        with an absurdly tight band and manufacture crosses that mean nothing.
        A quarter of the window is the shortest span that still measures
        volatility rather than noise.
        """
        return max(2, self.bb_window // 4)

    # -- universe registry ------------------------------------------------
    # Index ticker conventions vary by terminal and entitlement, so the built-in
    # list is a starting point rather than a fixed menu. Anything registered at
    # runtime is resolved here too, which is why these are methods reading a
    # module-level dict rather than data baked in at construction: Config is
    # frozen and is captured as a default argument all over the system, so a
    # rebound global would never reach those call sites.
    def _entries(self):
        extra = [(label, code, ticker)
                 for code, (label, ticker) in EXTRA_UNIVERSES.items()]
        return extra + list(self.universes)      # runtime entries win

    def universe_options(self):
        """ipywidgets Dropdown options: (label, short code), de-duplicated."""
        seen, options = set(), []
        for label, code, _ in self._entries():
            if code not in seen:
                seen.add(code)
                options.append((label, code))
        return options

    def full_ticker(self, code: str) -> str:
        for _, c, full in self._entries():
            if c == code:
                return full
        return code if ' ' in code else f'{code} Index'

    def label(self, code: str) -> str:
        for label, c, _ in self._entries():
            if c == code:
                return label
        return code


# code -> (label, bloomberg ticker), populated by register_universe()
EXTRA_UNIVERSES: dict[str, tuple[str, str]] = {}


def register_universe(ticker: str, label: str | None = None,
                      code: str | None = None) -> str:
    """Make an arbitrary Bloomberg index loadable without editing Config.

    Returns the short code the rest of the system will use for it. Lets a
    terminal whose index tickers differ from the defaults work immediately,
    instead of waiting on a code change.
    """
    ticker = ticker.strip()
    if not ticker:
        raise ValueError('an index ticker is required')
    if ' ' not in ticker:                    # 'SMI' -> 'SMI Index'
        ticker = f'{ticker} Index'
    code = (code or ticker.split(' ')[0]).upper()
    EXTRA_UNIVERSES[code] = (label or ticker, ticker)
    return code


CFG = Config()


# ─────────────────────────────────────────────────────────────
# 2. BRAND THEME  (palette, typography, CSS, plotly defaults)
# ─────────────────────────────────────────────────────────────
class Theme:
    SPACE_BLUE     = '#202945'
    TIGER_ORANGE   = '#FF6C0E'
    MANGO_AMBER    = '#FFA400'
    GOLD_YELLOW    = '#FFC545'
    MINT_GREEN     = '#3BAF90'
    TEAL_GREEN     = '#9DD9D2'
    SKY_BLUE       = '#79D6FF'
    PEACH_PINK     = '#E6A4AD'
    MULBERRY_PINK  = '#AC5D85'
    BLUEBERRY_BLUE = '#4B5F80'

    POSITIVE = MINT_GREEN
    NEGATIVE = TIGER_ORANGE
    NEUTRAL  = BLUEBERRY_BLUE

    WHITE      = '#FFFFFF'
    ZEBRA      = '#F4F6FA'
    HAIRLINE   = '#E4E8F0'
    AXIS_COLOR = 'rgba(32,41,69,0.4)'
    GRID_COLOR = 'rgba(32,41,69,0.12)'
    FONT       = 'Nunito, "Segoe UI", sans-serif'

    CATEGORY_COLORS = {
        'Major +':    MINT_GREEN,
        'Moderate +': TEAL_GREEN,
        'In Line':    NEUTRAL,
        'Moderate −': MANGO_AMBER,
        'Major −':    TIGER_ORANGE,
    }
    HORIZON_COLORS = {5: SKY_BLUE, 20: GOLD_YELLOW, 60: MULBERRY_PINK}

    # A plain widget/output area has no background of its own, so under a dark
    # JupyterLab / VS Code / classic-notebook theme our Space-Blue text renders
    # dark-on-dark. Forcing a white canvas on the output area *and* on the form
    # controls themselves is what keeps the whole surface legible.
    @classmethod
    def css(cls) -> str:
        return f"""
<style>
.jp-OutputArea-output, .output_area, .output_subarea,
.jupyter-widgets-output-area, .cell-output-ipywidget-background,
.widget-hbox, .widget-vbox, .widget-box, .jupyter-widgets-view,
.widget-tab, .widget-tab-contents {{
    background-color: {cls.WHITE} !important;
}}
.jupyter-widgets, .widget-label, .widget-html-content,
.jp-OutputArea-output pre, .output_text pre {{
    font-family: {cls.FONT} !important;
    color: {cls.SPACE_BLUE} !important;
}}
.widget-dropdown, .widget-dropdown select, select.widget-dropdown,
.jupyter-widgets select,
.widget-combobox input, .widget-text input {{
    background-color: {cls.WHITE} !important;
    color: {cls.SPACE_BLUE} !important;
    border: 1px solid #C7CEDC !important;
}}
.widget-dropdown option, select option {{
    background-color: {cls.WHITE} !important;
    color: {cls.SPACE_BLUE} !important;
}}
</style>"""

    @classmethod
    def inject(cls):
        display(HTML(cls.css()))

    @classmethod
    def layout(cls, **overrides) -> dict:
        """Shared plotly layout: flat, minimalist, brand typography."""
        base = dict(
            template='plotly_white',
            paper_bgcolor=cls.WHITE, plot_bgcolor=cls.WHITE,
            font=dict(family=cls.FONT, color=cls.SPACE_BLUE, size=12),
            margin=dict(l=20, r=20, t=80, b=20),
            legend=dict(orientation='h', yanchor='bottom', y=1.04,
                        xanchor='right', x=1),
        )
        base.update(overrides)
        return base

    @classmethod
    def style_axes(cls, fig):
        fig.update_xaxes(showline=True, linecolor=cls.AXIS_COLOR,
                         gridcolor=cls.GRID_COLOR, zeroline=False)
        fig.update_yaxes(showline=True, linecolor=cls.AXIS_COLOR,
                         gridcolor=cls.GRID_COLOR, zeroline=True,
                         zerolinecolor=cls.AXIS_COLOR)
        return fig

    @classmethod
    def title(cls, text: str, size: int = 20) -> dict:
        return dict(text=text, font=dict(size=size, color=cls.SPACE_BLUE),
                    x=0.01, xanchor='left')

    # -- small HTML builders (used by the dashboard + summary cards) ------
    @classmethod
    def panel(cls, inner: str, pad: str = '14px 18px', max_width: str = 'none') -> str:
        return (f"<div style='font-family:{cls.FONT};background:{cls.WHITE};padding:{pad};"
                f"border-radius:10px;border:1px solid {cls.HAIRLINE};"
                f"max-width:{max_width}'>{inner}</div>")

    @classmethod
    def note(cls, text: str, color: str | None = None, size: int = 12) -> str:
        return (f"<div style='font-family:{cls.FONT};font-weight:300;"
                f"color:{color or cls.SPACE_BLUE};font-size:{size}px;"
                f"margin:2px 4px 10px'>{text}</div>")


THEME = Theme


def fmt(value, suffix: str = '', dp: int = 1, dash: str = '—') -> str:
    """NaN/None-safe number formatting for every table and card."""
    if value is None:
        return dash
    if isinstance(value, float) and not np.isfinite(value):
        return dash
    if pd.isna(value):
        return dash
    return f'{value:.{dp}f}{suffix}'


# ─────────────────────────────────────────────────────────────
# 3. PROGRESS REPORTER
# Keeps logging out of the query code and lets the UI capture it.
# ─────────────────────────────────────────────────────────────
class Reporter:
    def __init__(self, verbose: bool = True, sink: Callable[[str], None] | None = None):
        self.verbose = verbose
        self.sink = sink or print
        self.messages: list[str] = []

    def __call__(self, msg: str, indent: int = 0):
        line = f"{'  ' * indent}{msg}"
        self.messages.append(line)
        if self.verbose:
            self.sink(line)

    def step(self, i: int, n: int, msg: str):
        self(f"[{i}/{n}] {msg}")


# ─────────────────────────────────────────────────────────────
# 4. BQL ACCESS LAYER
# The only component that imports bql. It owns batching, retries,
# per-batch failure isolation and response normalisation, so callers
# just describe the fields they want.
# ─────────────────────────────────────────────────────────────
def batched(seq: Sequence, n: int):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def short_ticker(value) -> str:
    """'AAPL US Equity' -> 'AAPL' (the join key used across all tables).

    Deliberately format-agnostic: it returns whatever the local convention is
    -- 'AAPL' (US), 'NESN' (Switzerland), 'MC' (France), '005930' (Korea) --
    because the exchange, not the code shape, is what disambiguates a listing.
    """
    return str(value).split(' ')[0]


def exchange_code(value) -> str:
    """'NESN SW Equity' -> 'SW'. Empty when the ID carries no venue."""
    parts = str(value).split(' ')
    return parts[1] if len(parts) > 2 else ''


# Folding a few letters that NFKD leaves alone; without these, searching
# "Muenchener" or "Munchener" would miss "Münchener" and "Bunzl" would not
# match a Danish or German name carrying ß/ø.
_FOLD_MAP = str.maketrans({'ß': 'ss', 'æ': 'ae', 'ø': 'o', 'å': 'a',
                           'đ': 'd', 'ł': 'l', 'þ': 'th', 'ð': 'd', "'": ' ',
                           '’': ' ', '-': ' ', '.': '', ',': '', '&': ' and '})


def fold_text(value) -> str:
    """Case-, accent- and punctuation-insensitive search key.

    'Société Générale' -> 'societe generale', 'Münchener Rück' -> 'munchener
    ruck'. European constituents are unusable in a search box without this.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ''
    text = str(value).lower().translate(_FOLD_MAP)
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    return ' '.join(text.split())


def numeric_key(ticker) -> str:
    """Leading-zero-insensitive form of a numeric ticker, so a KOSPI name can
    be found by typing 5930 as well as 005930. Empty for alphabetic codes."""
    code = str(ticker).strip()
    return code.lstrip('0') or '0' if code.isdigit() else ''


def pick_column(df: pd.DataFrame, *keywords, exclude=()) -> str | None:
    """Locate a column by fragment, case-insensitively, in priority order.
    BQL field metadata differs by field/version; this keeps us tolerant."""
    cols = {c.upper(): c for c in df.columns}
    for kw in keywords:
        for up, orig in cols.items():
            if kw.upper() in up and not any(x.upper() in up for x in exclude):
                return orig
    return None


class EmptyResponseError(RuntimeError):
    """BQL answered, but with nothing in it — usually an unresolvable universe."""


class BQLClient:
    """Thin, resilient wrapper around bql.Service.

    - batches large universes,
    - retries transient failures with exponential backoff,
    - bisects a failing batch so one bad security cannot void 500 names,
    - normalises every response to a tidy frame with an ``ID`` column.
    """

    def __init__(self, cfg: Config = CFG, report: Reporter | None = None):
        self.cfg = cfg
        self.report = report or Reporter()
        self._svc = None
        self._bql = None
        self.failed: dict[str, str] = {}

    # -- service handle ------------------------------------------------
    @property
    def bql(self):
        if self._bql is None:
            import bql  # imported lazily so this cell runs off-Bloomberg too
            self._bql = bql
        return self._bql

    @property
    def bq(self):
        if self._svc is None:
            self._svc = self.bql.Service()
        return self._svc

    @property
    def available(self) -> bool:
        try:
            self.bq
            return True
        except Exception as exc:  # pragma: no cover - environment dependent
            self.report(f"BQL unavailable: {exc}")
            return False

    @property
    def data(self):
        return self.bq.data

    @property
    def func(self):
        return self.bq.func

    @property
    def univ(self):
        return self.bq.univ

    # -- response normalisation ---------------------------------------
    def _to_frame(self, response) -> pd.DataFrame:
        """Merge a multi-item BQL response into one tidy frame.

        Deliberately not bql.combined_df: that helper is deprecated, and its
        documented replacement -- pd.concat([x.df()[x.name] for x in response])
        -- keeps only the value column. This pipeline needs the metadata that
        comes back beside it (DATE for price series, PERIOD_END_DATE and
        ANNOUNCED_DATE for fundamentals), so we join the full frames and keep
        the first occurrence of each column.
        """
        items = list(response)
        if not items:
            # An empty response is what BQL returns when the universe itself
            # resolved to nothing -- an index ticker that does not exist or is
            # not entitled. Saying so beats an IndexError three frames down.
            raise EmptyResponseError(
                'BQL returned no response items — the universe resolved to '
                'zero securities')

        frames = [item.df() for item in items]
        df = frames[0]
        for extra in frames[1:]:
            new = [c for c in extra.columns if c not in df.columns]
            if new:
                df = df.join(extra[new], how='outer')

        df = df.reset_index()
        if df.columns.empty:
            raise EmptyResponseError('BQL response carried no columns')
        idc = pick_column(df, 'ID') or df.columns[0]
        return df.rename(columns={idc: 'ID'})

    # -- single request ------------------------------------------------
    def _execute(self, universe, fields: Mapping[str, object]) -> pd.DataFrame:
        request = self.bql.Request(list(universe), dict(fields))
        return self._to_frame(self.bq.execute(request))

    # -- batched request with isolation --------------------------------
    def fetch(self, universe: Sequence[str], fields: Mapping[str, object],
              label: str = 'data', batch_size: int | None = None) -> pd.DataFrame:
        universe = list(universe)
        if not universe:
            return pd.DataFrame()
        size = batch_size or self.cfg.batch_size
        frames = []
        for i, batch in enumerate(batched(universe, size), 1):
            part = self._fetch_batch(batch, fields, label, i)
            if part is not None and not part.empty:
                frames.append(part)
        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, ignore_index=True)

    def _fetch_batch(self, batch, fields, label, seq,
                     attempts: int | None = None) -> pd.DataFrame | None:
        attempts = self.cfg.max_retries if attempts is None else attempts
        last_err: Exception | None = None
        for attempt in range(attempts):
            try:
                df = self._execute(batch, fields)
                self.report(f"-> {label} batch {seq}: {len(df):,} rows "
                            f"({len(batch)} securities)", indent=1)
                return df
            except EmptyResponseError as exc:
                # Nothing came back at all: retrying and bisecting cannot help,
                # because there is no bad security to isolate.
                last_err = exc
                break
            except Exception as exc:
                last_err = exc
                if attempt < attempts - 1:
                    time.sleep(self.cfg.backoff_base ** attempt)

        # Retries exhausted: bisect so a single bad security is quarantined
        # instead of discarding everything that shares its batch. The halves
        # are tried once each -- the batch has already proven it contains a
        # hard failure, so re-paying the backoff at every level of the
        # recursion would cost minutes and buy nothing.
        if len(batch) > 1:
            mid = len(batch) // 2
            self.report(f"-> {label} batch {seq} failed, bisecting "
                        f"({last_err})", indent=1)
            left = self._fetch_batch(batch[:mid], fields, label, seq, attempts=1)
            right = self._fetch_batch(batch[mid:], fields, label, seq, attempts=1)
            parts = [p for p in (left, right) if p is not None and not p.empty]
            return pd.concat(parts, ignore_index=True) if parts else None

        self.failed[batch[0]] = str(last_err)
        self.report(f"-> dropped {batch[0]}: {last_err}", indent=1)
        return None

    # -- universe resolution -------------------------------------------
    def members(self, index_ticker: str) -> pd.DataFrame:
        """Resolve index constituents live. Returns ID + NAME."""
        try:
            df = self._execute([self.univ.members(index_ticker)],
                               {'name': self.data.name()})
        except EmptyResponseError as exc:
            raise EmptyResponseError(
                f"'{index_ticker}' returned no constituents. Check the ticker "
                f"in <GO> (an index that exists may still not support "
                f"univ.members, or may not be entitled on this terminal), then "
                f"adjust Config.universes.") from exc
        out = pd.DataFrame({'ID': df['ID'].astype(str)})
        name_col = pick_column(df, 'name')
        out['NAME'] = df[name_col] if name_col else out['ID']
        out['TICKER'] = out['ID'].map(short_ticker)
        out = out.drop_duplicates('ID').reset_index(drop=True)
        self.report(f"-> {len(out)} constituents resolved for {index_ticker}",
                    indent=1)
        return out


# ─────────────────────────────────────────────────────────────
# 5. DATA STORE
# One container for every dataset, keyed by (index code, dataset name).
# Memory is authoritative -- that is what makes a QuApp work, where the
# filesystem is typically not writable. Parquet is a best-effort cache so
# a Quant notebook session can pick up where the last one left off.
# ─────────────────────────────────────────────────────────────
DATASETS = ('universe', 'prices_wide', 'prices_long', 'benchmark', 'earnings',
            'next_earnings', 'sectors', 'events')

# Filenames written by the earlier flat-file version of this project, so
# existing workspace parquet keeps loading without a re-pull.
LEGACY_NAMES = {
    'prices_wide':   '{code}_step1_data_prices_wide.parquet',
    'prices_long':   '{code}_step1_data_prices_long.parquet',
    'earnings':      '{code}_step1_data_earnings_hist.parquet',
    'next_earnings': '{code}_step1_data_next_earnings.parquet',
    'sectors':       '{code}_step1_data_sectors.parquet',
    'events':        '{code}_step2_events.parquet',
}

DATE_COLUMNS = ('DATE', 'ANNOUNCE_DATE', 'PERIOD_END', 'NEXT_EARNINGS_DATE')


class DataStore:
    def __init__(self, cfg: Config = CFG, report: Reporter | None = None):
        self.cfg = cfg
        self.report = report or Reporter(verbose=False)
        self._mem: dict[tuple[str, str], pd.DataFrame] = {}
        self._stamp: dict[tuple[str, str], float] = {}
        self.persist = cfg.persist

    # -- paths ---------------------------------------------------------
    def _paths(self, code: str, name: str) -> list[str]:
        primary = os.path.join(self.cfg.data_dir, f'{code}_{name}.parquet')
        paths = [primary]
        legacy = LEGACY_NAMES.get(name)
        if legacy:
            paths.append(legacy.format(code=code))
        return paths

    # -- write ---------------------------------------------------------
    def put(self, code: str, name: str, df: pd.DataFrame, save: bool = True):
        self._mem[(code, name)] = df
        self._stamp[(code, name)] = time.time()
        if save and self.persist:
            self._save(code, name, df)
        return df

    def _save(self, code: str, name: str, df: pd.DataFrame):
        target = self._paths(code, name)[0]
        try:
            os.makedirs(os.path.dirname(target) or '.', exist_ok=True)
            keep_index = name in ('prices_wide', 'benchmark')
            df.to_parquet(target, index=keep_index)
        except Exception as exc:
            # Read-only app sandbox: memory still holds everything.
            self.persist = False
            self.report(f"(parquet persistence disabled — {exc})", indent=1)

    # -- read ----------------------------------------------------------
    def get(self, code: str, name: str, allow_disk: bool = True) -> pd.DataFrame | None:
        hit = self._mem.get((code, name))
        if hit is not None:
            return hit
        if not allow_disk:
            return None
        for path in self._paths(code, name):
            if os.path.exists(path):
                try:
                    df = self._coerce(name, pd.read_parquet(path))
                except Exception as exc:
                    self.report(f"(could not read {path}: {exc})", indent=1)
                    continue
                self._mem[(code, name)] = df
                self._stamp[(code, name)] = os.path.getmtime(path)
                return df
        return None

    @staticmethod
    def _coerce(name: str, df: pd.DataFrame) -> pd.DataFrame:
        """Restore dtypes and column conventions a stored file may not carry.

        This is the one place that reconciles files written by earlier versions
        of the pipeline with what the current code expects, so no downstream
        component has to defend itself against an old parquet layout.
        """
        if name in ('prices_wide', 'benchmark'):
            df.index = pd.to_datetime(df.index)
            df = df.sort_index()
            return DataStore._short_ticker_columns(df) if name == 'prices_wide' else df
        for col in DATE_COLUMNS:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
        # Short ticker is the join key everywhere; older files stored only the
        # full Bloomberg ID.
        if 'TICKER' not in df.columns and 'ID' in df.columns:
            df['TICKER'] = df['ID'].map(short_ticker)
        return df

    @staticmethod
    def _short_ticker_columns(df: pd.DataFrame) -> pd.DataFrame:
        """Re-key a price matrix stored under full IDs ('AAPL US Equity') onto
        short tickers. Without this an older price file silently matches no
        events at all, and the event table comes back empty for no visible
        reason."""
        if not any(' ' in str(c) for c in df.columns):
            return df
        short = [short_ticker(c) for c in df.columns]
        if len(set(short)) == len(short):
            df.columns = short
            return df
        coverage = df.notna().sum()          # collision: keep deepest history
        best: dict[str, object] = {}
        for original, code in zip(df.columns, short):
            if code not in best or coverage[original] > coverage[best[code]]:
                best[code] = original
        codes = sorted(best)
        out = df[[best[c] for c in codes]].copy()
        out.columns = codes
        return out

    def has(self, code: str, *names: str) -> bool:
        return all(self.get(code, n) is not None for n in (names or DATASETS))

    def age(self, code: str, name: str = 'events') -> float | None:
        ts = self._stamp.get((code, name))
        return None if ts is None else time.time() - ts

    def is_fresh(self, code: str, name: str = 'events') -> bool:
        age = self.age(code, name)
        return age is not None and age <= self.cfg.cache_ttl

    def bundle(self, code: str) -> dict[str, pd.DataFrame]:
        return {n: self.get(code, n) for n in DATASETS}

    def clear(self, code: str | None = None):
        for key in list(self._mem):
            if code is None or key[0] == code:
                self._mem.pop(key, None)
                self._stamp.pop(key, None)

    def status(self) -> pd.DataFrame:
        rows = []
        for (code, name), df in sorted(self._mem.items()):
            age = self.age(code, name)
            rows.append(dict(INDEX=code, DATASET=name, ROWS=len(df),
                             AGE_MIN=round((age or 0) / 60, 1),
                             FRESH=self.is_fresh(code, name)))
        return pd.DataFrame(rows)


STORE = DataStore(CFG)
BQ = BQLClient(CFG)

THEME.inject()
print('Core layer ready — CFG · THEME · BQ · STORE')
