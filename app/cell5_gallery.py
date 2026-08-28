# ══════════════════════════════════════════════════════════════════════
# CELL 5 — STEP 3: PER-ASSET EARNINGS GALLERY
# Price history with Bollinger band, MA200 and every quarterly print marked by
# surprise severity, driven by a universal search over every loaded index.
#
# The band drawn here is the same one the event engine measured the signal
# against (Config.bb_window sessions of volatility, ±Config.bb_sigma), so a
# print ringed as a signal is visibly sitting outside the band it crossed.
#
# Selection model:
#   search box  -> ticker / company / sector / country / index, accent- and
#                  case-insensitive, numeric-ticker aware (5930 finds 005930)
#   filter      -> latest-print surprise state, band signal, recency, frequent
#                  surprisers
#   sort        -> relevance, ticker, name, market cap, |σ|, signals, next report
# Results span indices: picking a DAX name while showing the S&P rebinds the
# chart to the DAX and tells the app shell to follow.
#
# Marker coordinates come from Step 2 (TRADE_DATE / PRICE_AT_EVENT), so
# redrawing a name is a vectorised column assignment rather than a per-event
# search through the price series.
# ══════════════════════════════════════════════════════════════════════
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import ipywidgets as widgets
from IPython.display import display

# CATEGORY -> (colour, symbol, size). Same severity language as the dashboard.
MARKER_STYLE = {
    'Major +':    (THEME.MINT_GREEN,   'triangle-up',   16),
    'Moderate +': (THEME.TEAL_GREEN,   'triangle-up',   11),
    'In Line':    (THEME.SKY_BLUE,     'circle',         7),
    'Moderate −': (THEME.MANGO_AMBER,  'triangle-down', 11),
    'Major −':    (THEME.TIGER_ORANGE, 'triangle-down', 16),
    'Unrated':    ('rgba(75,95,128,0.45)', 'circle-open', 7),
}
CATEGORY_GLYPH = {'Major +': '▲▲', 'Moderate +': '▲', 'In Line': '•',
                  'Moderate −': '▼', 'Major −': '▼▼', 'Unrated': '○'}
SIGNAL_GLYPH = {SIGNAL_LONG: '⚡L', SIGNAL_SHORT: '⚡S', SIGNAL_DIVERGENT: '≠'}

# Trace slots, in the order _build adds them. Named so that inserting a trace
# is a one-line change here rather than a hunt through draw() for magic
# indices -- the previous version of this cell had the signal halo and the
# earnings markers disagreeing about which slot they owned.
T_FILL, T_UPPER, T_LOWER, T_MA, T_CLOSE, T_SIGNAL, T_EVENTS = range(7)

RESULT_LIMIT = 300


class EarningsGallery:
    """Interactive single-name chart. One FigureWidget, mutated in place."""

    def __init__(self, store=STORE, cfg: Config = CFG):
        self.store, self.cfg = store, cfg
        self.code: str | None = None
        self.prices = pd.DataFrame()
        self.events = pd.DataFrame()
        self.catalog = pd.DataFrame()
        self.results = pd.DataFrame()
        self.keys: list[str] = []
        self.ticker: str | None = None
        self.on_index_change = None      # set by the app shell to stay in sync
        self._series: pd.Series | None = None
        self._rescaling = False          # re-entrancy guard for autoscale
        self._syncing = False            # guard while rewriting result options
        self._build()

    # ── construction ─────────────────────────────────────────────────
    def _build(self):
        band = f'BB{self.cfg.bb_window}'
        fig = go.FigureWidget()
        # T_FILL — shaded band interior
        fig.add_trace(go.Scatter(fill='toself', fillcolor='rgba(75,95,128,0.08)',
                                 line=dict(color='rgba(255,255,255,0)'),
                                 hoverinfo='skip', showlegend=False))
        # T_UPPER / T_LOWER — the band the signal is measured against
        fig.add_trace(go.Scatter(mode='lines', name=f'{band} upper',
                                 line=dict(color='rgba(75,95,128,0.45)', width=1,
                                           dash='dot')))
        fig.add_trace(go.Scatter(mode='lines', name=f'{band} lower',
                                 line=dict(color='rgba(75,95,128,0.45)', width=1,
                                           dash='dot')))
        # T_MA — long moving average
        fig.add_trace(go.Scatter(mode='lines', name=f'MA{self.cfg.ma_window}',
                                 line=dict(color=THEME.GOLD_YELLOW, width=1.5)))
        # T_CLOSE — the price series itself
        fig.add_trace(go.Scatter(mode='lines', name='Close',
                                 line=dict(color=THEME.BLUEBERRY_BLUE, width=2)))
        # T_SIGNAL — added before the severity markers so plotly draws the halo
        # underneath: the confirmation rings the print without hiding the
        # category colour or stealing its hover.
        fig.add_trace(go.Scatter(mode='markers', name='Band-confirmed signal',
                                 hoverinfo='skip',
                                 marker=dict(symbol='circle-open', size=26,
                                             color=THEME.SPACE_BLUE,
                                             line=dict(width=2))))
        # T_EVENTS — one marker per quarterly print
        fig.add_trace(go.Scatter(mode='markers', name='Quarterly earnings',
                                 hovertemplate='%{hovertext}<extra></extra>'))

        fig.update_layout(**THEME.layout(
            height=700, hovermode='x unified',
            margin=dict(l=20, r=20, t=60, b=20),
            xaxis=dict(
                type='date', showline=True, linecolor=THEME.AXIS_COLOR,
                gridcolor=THEME.GRID_COLOR,
                rangeselector=dict(buttons=[
                    dict(count=3, label='3M', step='month', stepmode='backward'),
                    dict(count=1, label='1Y', step='year', stepmode='backward'),
                    dict(count=3, label='3Y', step='year', stepmode='backward'),
                    dict(step='all', label='Full 5Y'),
                ], bgcolor=THEME.ZEBRA, activecolor=THEME.BLUEBERRY_BLUE,
                    font=dict(color=THEME.SPACE_BLUE)),
                rangeslider=dict(visible=True, thickness=0.08,
                                 bgcolor=THEME.ZEBRA, bordercolor=THEME.AXIS_COLOR),
            ),
            yaxis=dict(showline=True, linecolor=THEME.AXIS_COLOR,
                       gridcolor=THEME.GRID_COLOR, zeroline=False),
        ))
        # Rescale y to whatever the x-window actually shows: without this the
        # 3M/1Y buttons zoom the x-axis while the series stays visually flat
        # inside a range fixed by the full 5Y extremes.
        fig.layout.on_change(self._on_xrange, 'xaxis.range')
        # Fail loudly if the slot constants and the traces above ever drift
        # apart: a silent mismatch is what leaves the chart showing markers on
        # an empty canvas.
        if len(fig.data) != T_EVENTS + 1:
            raise RuntimeError(f'gallery expects {T_EVENTS + 1} traces, '
                               f'built {len(fig.data)}')
        self.fig = fig

        self.ui_search = widgets.Text(
            value='', placeholder='Search ticker, company, sector, country or index…',
            description='Search:', continuous_update=True,
            style={'description_width': 'initial'}, layout={'width': '460px'})
        self.ui_clear = widgets.Button(description='✕', tooltip='Clear search',
                                       layout={'width': '36px'})
        self.ui_filter = widgets.Dropdown(
            options=ASSET_FILTERS, value='ALL', description='Filter:',
            style={'description_width': 'initial'}, layout={'width': '290px'})
        self.ui_sort = widgets.Dropdown(
            options=ASSET_SORTS, value='REL', description='Sort:',
            style={'description_width': 'initial'}, layout={'width': '230px'})
        self.ui_scope = widgets.Checkbox(
            value=True, description='This index only', indent=False,
            layout={'width': '150px'})
        self.ui_results = widgets.Select(options=[], rows=11,
                                         layout={'width': '520px'})
        self.ui_meta = widgets.HTML(layout={'margin': '0 0 0 16px',
                                            'width': '420px'})
        self.ui_prev = widgets.Button(description='◀ Prev', button_style='info',
                                      layout={'width': '80px'})
        self.ui_next = widgets.Button(description='Next ▶', button_style='info',
                                      layout={'width': '80px'})
        self.ui_status = widgets.HTML(layout={'margin': '0 0 0 16px'})

        self.ui_search.observe(self._on_query, names='value')
        self.ui_filter.observe(self._on_query, names='value')
        self.ui_sort.observe(self._on_query, names='value')
        self.ui_scope.observe(self._on_query, names='value')
        self.ui_clear.on_click(self._on_clear)
        self.ui_results.observe(self._on_pick, names='value')
        self.ui_prev.on_click(lambda _: self._step(-1))
        self.ui_next.on_click(lambda _: self._step(+1))

    @property
    def widget(self):
        row1 = widgets.HBox([self.ui_search, self.ui_clear, self.ui_filter],
                            layout={'align_items': 'center'})
        row2 = widgets.HBox([self.ui_sort, self.ui_scope, self.ui_prev,
                             self.ui_next, self.ui_status],
                            layout={'align_items': 'center',
                                    'margin': '6px 0 6px 0'})
        row3 = widgets.HBox([self.ui_results, self.ui_meta],
                            layout={'align_items': 'flex-start',
                                    'margin': '0 0 12px 0'})
        return widgets.VBox([row1, row2, row3, self.fig])

    # ── data binding ─────────────────────────────────────────────────
    def refresh_catalog(self):
        """Rebuild the cross-index search catalog from whatever the store has."""
        self.catalog = build_catalog(self.store, self.cfg)

    def _bind(self, code: str) -> bool:
        """Point the chart at one index's price/event data."""
        prices = self.store.get(code, 'prices_wide')
        events = self.store.get(code, 'events')
        if prices is None or events is None or prices.empty or events.empty:
            self.code = code
            self.prices, self.events = pd.DataFrame(), pd.DataFrame()
            return False
        self.code = code
        self.prices = prices
        self.events = prepare(events)
        return True

    def load(self, code: str, keep_selection: bool = True):
        previous = self.ticker if keep_selection else None
        self.refresh_catalog()
        ok = self._bind(code)
        if not ok:
            self._empty(f"No data loaded for {self.cfg.label(code)} — "
                        f"run the pipeline for this index first.")
        self._refresh_results(prefer=previous)

    def _empty(self, message: str):
        self._series = None
        self.ticker = None
        with self.fig.batch_update():
            self.fig.layout.title = THEME.title(message, size=15)
            self.fig.layout.shapes = ()
            for trace in self.fig.data:
                trace.x, trace.y = [], []
        self.ui_meta.value = ''

    # ── search / result list ─────────────────────────────────────────
    def _visible_catalog(self) -> pd.DataFrame:
        cat = self.catalog
        if cat.empty:
            return cat
        # "This index only" is a scope, not a filter: a search still reaches
        # across indices when the user unticks it.
        if self.ui_scope.value and self.code:
            cat = cat[cat.CODE == self.code]
        cat = apply_asset_filter(cat, self.ui_filter.value)
        query = self.ui_search.value.strip()
        if query:
            cat = search_catalog(cat, query, limit=RESULT_LIMIT)
        return sort_catalog(cat, self.ui_sort.value).head(RESULT_LIMIT)

    @staticmethod
    def _row_label(row) -> str:
        name = str(row.NAME)
        name = name if len(name) <= 30 else name[:29] + '…'
        bits = [f"{row.TICKER:<8}", name]
        if pd.notna(row.LAST_CATEGORY):
            glyph = CATEGORY_GLYPH.get(row.LAST_CATEGORY, '')
            sig = (f" {row.LAST_SIGMA:+.1f}σ" if pd.notna(row.LAST_SIGMA) else '')
            mark = SIGNAL_GLYPH.get(row.LAST_SIGNAL, '')
            bits.append(f"{glyph}{sig}{(' ' + mark) if mark else ''}")
        bits.append(str(row.CODE))
        if pd.notna(row.DAYS_TO_NEXT) and 0 <= row.DAYS_TO_NEXT <= 99:
            bits.append(f"in {int(row.DAYS_TO_NEXT)}d")
        return ' · '.join(bits)

    def _refresh_results(self, prefer: str | None = None):
        self.results = self._visible_catalog()
        options = [(self._row_label(r), f"{r.CODE}|{r.TICKER}")
                   for r in self.results.itertuples()]
        self.keys = [value for _, value in options]

        target = None
        if prefer and self.code and f"{self.code}|{prefer}" in self.keys:
            target = f"{self.code}|{prefer}"
        elif self.ticker and self.code and f"{self.code}|{self.ticker}" in self.keys:
            target = f"{self.code}|{self.ticker}"
        elif self.keys:
            target = self.keys[0]

        self._syncing = True
        try:
            self.ui_results.options = options
            self.ui_results.value = target
        finally:
            self._syncing = False

        if target:
            self.select(target)
        else:
            # Distinguish "this index was never loaded" from "your filter
            # excluded everything" -- blaming the filter for missing data
            # sends the user hunting in the wrong place.
            if self.prices.empty and self.ui_scope.value and self.code:
                self._empty(f"No data loaded for {self.cfg.label(self.code)} — "
                            f"run the pipeline for this index first.")
            else:
                self._empty('No assets match the current search and filter.')
            self._status()

    def _status(self):
        total = 0 if self.catalog.empty else len(
            self.catalog[self.catalog.CODE == self.code] if self.ui_scope.value
            and self.code else self.catalog)
        shown = len(self.results)
        pos = (self.keys.index(f"{self.code}|{self.ticker}") + 1
               if self.ticker and f"{self.code}|{self.ticker}" in self.keys else 0)
        scope = self.cfg.label(self.code) if self.ui_scope.value and self.code \
            else 'all loaded indices'
        colour = THEME.SPACE_BLUE if shown else THEME.MANGO_AMBER
        self.ui_status.value = (
            f"<span style='font-family:{THEME.FONT};color:{colour}'>"
            f"<b>{pos or '–'}</b> of <b>{shown}</b> shown "
            f"(of {total} in {scope})</span>")

    # ── selection ────────────────────────────────────────────────────
    def select(self, key: str):
        """Select a 'CODE|TICKER' result, switching index if needed."""
        if '|' not in key:
            return
        code, ticker = key.split('|', 1)
        if code != self.code:
            if not self._bind(code):
                self._empty(f"{self.cfg.label(code)} is not loaded — "
                            f"run the pipeline for it first.")
                self._status()
                return
            if callable(self.on_index_change):
                self.on_index_change(code)
        self.draw(ticker)

    # ── drawing ──────────────────────────────────────────────────────
    def draw(self, ticker: str):
        if self.prices.empty or ticker not in self.prices.columns:
            return
        px = self.prices[ticker].dropna()
        if px.empty:
            return
        self._series = px
        self.ticker = ticker

        # Same band definition as the event engine, so what is plotted is what
        # the signal was tested against.
        mid, upper, lower = bollinger_bands(px, self.cfg)
        ma = px.rolling(self.cfg.ma_window,
                        min_periods=max(2, self.cfg.ma_window // 2)).mean()

        ev = self.events[self.events.TICKER == ticker].sort_values('TRADE_DATE')
        ev = ev[ev['PRICE_AT_EVENT'].notna()]
        styles = ev['CATEGORY'].map(MARKER_STYLE)
        fallback = MARKER_STYLE['Unrated']
        colors = [s[0] if isinstance(s, tuple) else fallback[0] for s in styles]
        symbols = [s[1] if isinstance(s, tuple) else fallback[1] for s in styles]
        sizes = [s[2] if isinstance(s, tuple) else fallback[2] for s in styles]
        sig = (ev[ev['SIGNAL'].isin(ACTIVE_SIGNALS)] if 'SIGNAL' in ev.columns
               else ev.iloc[0:0])
        sig_colors = [THEME.MINT_GREEN if s == SIGNAL_LONG else THEME.TIGER_ORANGE
                      for s in sig['SIGNAL']]

        idx = list(px.index)
        data = self.fig.data
        with self.fig.batch_update():
            name = ev['NAME'].iloc[0] if not ev.empty and 'NAME' in ev else ticker
            self.fig.layout.title = THEME.title(
                f"<b>{ticker}</b> | {name} — {self.cfg.label(self.code)}", size=18)

            # Band interior as one closed polygon: up the upper band, back down
            # the lower one.
            data[T_FILL].x = idx + idx[::-1]
            data[T_FILL].y = list(upper) + list(lower)[::-1]
            for slot, series in ((T_UPPER, upper), (T_LOWER, lower),
                                 (T_MA, ma), (T_CLOSE, px)):
                data[slot].x = idx
                data[slot].y = list(series)

            halo = data[T_SIGNAL]
            halo.x = list(sig['TRADE_DATE'])
            halo.y = list(sig['PRICE_AT_EVENT'])
            # An empty colour list is not a valid marker colour, so fall back
            # to the scalar default when the name has no confirmed signal.
            halo.marker.color = sig_colors or THEME.SPACE_BLUE

            marker = data[T_EVENTS]
            marker.x = list(ev['TRADE_DATE'])
            marker.y = list(ev['PRICE_AT_EVENT'])
            marker.marker = dict(color=colors, symbol=symbols, size=sizes,
                                 line=dict(color='rgba(32,41,69,0.6)', width=1))
            marker.hovertext = [self._hover(r) for _, r in ev.iterrows()]

            # Vertical event guides as paper-referenced shapes: they always span
            # the plot area and, unlike sentinel-valued traces, never interfere
            # with the y-range we compute for the visible window.
            self.fig.layout.shapes = tuple(
                dict(type='line', xref='x', yref='paper', y0=0, y1=1,
                     x0=d, x1=d, layer='below',
                     line=dict(color='rgba(32,41,69,0.15)', width=1, dash='dash'))
                for d in ev['TRADE_DATE'])
            self.fig.layout.xaxis.range = [idx[0], idx[-1]]
        self._rescale([idx[0], idx[-1]])

        key = f"{self.code}|{ticker}"
        if key in self.keys and self.ui_results.value != key:
            self._syncing = True
            try:
                self.ui_results.value = key
            finally:
                self._syncing = False
        self.ui_meta.value = self._meta_html(ticker)
        self._status()

    def _meta_html(self, ticker: str) -> str:
        rows = self.catalog[(self.catalog.CODE == self.code) &
                            (self.catalog.TICKER == ticker)]
        if rows.empty:
            return ''
        r = rows.iloc[0]
        cap = (f"{r.MKT_CAP_USD/1e9:,.1f}bn" if pd.notna(r.MKT_CAP_USD) else '—')
        last = (f"{r.LAST_CATEGORY} ({r.LAST_SIGMA:+.2f}σ)"
                if pd.notna(r.LAST_SIGMA) else str(r.LAST_CATEGORY or '—'))
        nxt = (f"{pd.Timestamp(r.NEXT_DATE):%Y-%m-%d}"
               + (f" · in {int(r.DAYS_TO_NEXT)}d" if pd.notna(r.DAYS_TO_NEXT) else '')
               if pd.notna(r.NEXT_DATE) else '—')
        rate = (f"{r.N_SURPRISES}/{r.N_PRINTS} prints ({r.SURPRISE_RATE:.0%})"
                if pd.notna(r.SURPRISE_RATE) else '—')
        signal = (f"{r.LAST_SIGNAL} ({r.LAST_CROSS} band)"
                  if r.LAST_SIGNAL in ACTIVE_SIGNALS else
                  ('divergent break' if r.LAST_SIGNAL == SIGNAL_DIVERGENT
                   else 'no band cross'))
        items = [('Bloomberg ID', r.ID if pd.notna(r.ID) else '—'),
                 ('Index', f"{r.INDEX} ({r.CODE})"),
                 ('Sector', r.SECTOR), ('Country', r.COUNTRY),
                 ('Market cap', cap), ('Latest print', last),
                 ('Latest signal', signal),
                 (f'Band signals ({self.cfg.bb_window}d)', f"{r.N_SIGNALS}"),
                 ('Surprise history', rate), ('Next report', nxt)]
        body = "".join(
            f"<div style='display:flex;justify-content:space-between;gap:12px;"
            f"padding:3px 0;border-bottom:1px solid {THEME.HAIRLINE}'>"
            f"<span style='font-weight:300;font-size:12px'>{k}</span>"
            f"<span style='font-weight:700;font-size:12px;text-align:right'>{v}</span>"
            f"</div>" for k, v in items)
        head = (f"<div style='font-weight:800;font-size:14px;"
                f"color:{THEME.SPACE_BLUE};margin-bottom:6px'>"
                f"{r.TICKER} — {r.NAME}</div>")
        return THEME.panel(head + body, pad='10px 14px')

    @staticmethod
    def _hover(row) -> str:
        bits = [f"<b>{row['CATEGORY']}</b>",
                f"Date: {pd.Timestamp(row['DATE']):%Y-%m-%d}"]
        if pd.notna(row.get('SIGMA')):
            bits.append(f"SUE: {row['SIGMA']:+.2f}σ")
        if pd.notna(row.get('EPS_ACT')):
            est = (f" vs est {row['EPS_EST']:.2f}"
                   if pd.notna(row.get('EPS_EST')) else '')
            bits.append(f"EPS: {row['EPS_ACT']:.2f}{est}")
        bits.append(f"Reaction: {row['RET(%)']:+.2f}%")
        if pd.notna(row.get('ABN_RET(%)')):
            bits.append(f"vs index: {row['ABN_RET(%)']:+.2f}%")
        cross = row.get('BB_CROSS', CROSS_NA)
        signal = row.get('SIGNAL', SIGNAL_NONE)
        if signal in ACTIVE_SIGNALS:
            bits.append(f"<b>Signal: {signal}</b> — closed through the "
                        f"{str(cross).lower()} band")
        elif signal == SIGNAL_DIVERGENT:
            bits.append(f"Divergent: broke the {str(cross).lower()} band "
                        f"against the surprise")
        elif cross == CROSS_NONE:
            bits.append('No band cross')
        if pd.notna(row.get('FWD_20D')):
            bits.append(f"20D drift: {row['FWD_20D']:+.2f}%")
        return '<br>'.join(bits)

    # ── interaction ──────────────────────────────────────────────────
    def _on_xrange(self, layout, xrange):
        self._rescale(xrange)

    def _rescale(self, xrange):
        if self._series is None or not xrange or self._rescaling:
            return
        try:
            lo_x, hi_x = pd.Timestamp(xrange[0]), pd.Timestamp(xrange[1])
        except (TypeError, ValueError):
            return
        visible = self._series[(self._series.index >= lo_x) &
                               (self._series.index <= hi_x)]
        if visible.empty:
            return
        self._rescaling = True
        try:
            pad = (visible.max() - visible.min()) * 0.08 or visible.max() * 0.05
            self.fig.layout.yaxis.range = [float(visible.min() - pad),
                                           float(visible.max() + pad)]
        finally:
            self._rescaling = False

    def _on_query(self, change):
        if self._syncing:
            return
        self._refresh_results(prefer=self.ticker)

    def _on_clear(self, _):
        if self.ui_search.value:
            self.ui_search.value = ''      # observer refreshes the list

    def _on_pick(self, change):
        if self._syncing or not change.get('new'):
            return
        self.select(change['new'])

    def _step(self, delta: int):
        if not self.keys:
            return
        current = f"{self.code}|{self.ticker}"
        i = (self.keys.index(current) if current in self.keys else 0) + delta
        if 0 <= i < len(self.keys):
            self._syncing = True
            try:
                self.ui_results.value = self.keys[i]
            finally:
                self._syncing = False
            self.select(self.keys[i])


print('Step 3 ready — EarningsGallery() with universal search')
