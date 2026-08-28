# ══════════════════════════════════════════════════════════════════════
# CELL 5B — GALLERY, PART 2: metadata panel, hover, interaction
# Attached to the class defined in Cell 5. Splitting the gallery here keeps
# each cell short enough to paste reliably, and the attachment loop at the
# bottom fails loudly if anything is missing rather than blowing up later
# inside _build.
# ══════════════════════════════════════════════════════════════════════
import numpy as np
import pandas as pd


def _meta_html(self, ticker: str) -> str:
    """Fact panel beside the result list: what this name is, and what its
    surprise history has looked like."""
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
    tint = SIGNAL_COLOR.get(r.LAST_SIGNAL, THEME.SPACE_BLUE)
    items = [('Latest signal', f"<span style='color:{tint}'>{signal}</span>"),
             (f'Band signals ({self.cfg.bb_window}d)', f"{r.N_SIGNALS}"),
             ('Latest print', last),
             ('Surprise history', rate),
             ('Next report', nxt),
             ('Sector', r.SECTOR), ('Country', r.COUNTRY),
             ('Market cap', cap),
             ('Index', f"{r.INDEX} ({r.CODE})"),
             ('Bloomberg ID', r.ID if pd.notna(r.ID) else '—')]
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


def _hover(row) -> str:
    bits = [f"<b>{row['CATEGORY']}</b>",
            f"Date: {pd.Timestamp(row['DATE']):%Y-%m-%d}"]
    if pd.notna(row.get('SIGMA')):
        bits.append(f"SUE: {row['SIGMA']:+.2f}σ")
    if pd.notna(row.get('EPS_ACT')):
        est = (f" vs est {row['EPS_EST']:.2f}"
               if pd.notna(row.get('EPS_EST')) else '')
        bits.append(f"EPS: {row['EPS_ACT']:.2f}{est}")
    # The most recent print is on the chart before its reaction window closes,
    # so it has no return yet -- say so rather than print '+nan%'.
    bits.append(f"Reaction: {row['RET(%)']:+.2f}%" if pd.notna(row.get('RET(%)'))
                else 'Reaction: pending — window not closed yet')
    if pd.notna(row.get('ABN_RET(%)')):
        bits.append(f"vs index: {row['ABN_RET(%)']:+.2f}%")
    cross = row.get('BB_CROSS', CROSS_NA)
    signal = row.get('SIGNAL', SIGNAL_NONE)
    if signal in ACTIVE_SIGNALS:
        bits.append(f"<b>Signal: {signal}</b> — closed through the "
                    f"{str(cross).lower()} band")
    elif signal == SIGNAL_DIVERGENT:
        bits.append(f"Divergent: broke the {str(cross).lower()} band against "
                    f"the surprise")
    elif cross == CROSS_NONE:
        bits.append('No band cross')
    if pd.notna(row.get('FWD_20D')):
        bits.append(f"20D drift: {row['FWD_20D']:+.2f}%")
    return '<br>'.join(bits)


# ── interaction ──────────────────────────────────────────────────────
def _on_xrange(self, layout, xrange):
    self._rescale(xrange)


def _window(self, xrange):
    """The slice of the plotted series the x-range actually selects.

    Falls back to the whole series when the range is missing, unparseable, or
    selects nothing -- the rangeslider can report a normalised (0-1) range,
    and trusting it leaves the y-axis scaled to a window with no data in it.
    """
    env = self._envelope
    if env is None or not xrange:
        return env
    try:
        lo_x, hi_x = pd.Timestamp(xrange[0]), pd.Timestamp(xrange[1])
    except (TypeError, ValueError, OverflowError):
        return env
    window = env[(env.index >= lo_x) & (env.index <= hi_x)]
    return window if len(window) >= 2 else env


def _rescale(self, xrange=None):
    """Fit the y-axis to everything visible in the current x-window.

    The band, not the close, sets the extremes on a 100-day window, so scaling
    on the close alone clipped the band off the top and bottom of the plot --
    and with it the signal labels. Extra headroom above leaves room for the
    labels, which are drawn up to ~124px over their marker.
    """
    if self._envelope is None or self._rescaling:
        return
    window = self._window(xrange)
    if window is None or window.empty:
        return
    lo, hi = float(np.nanmin(window.to_numpy())), float(np.nanmax(window.to_numpy()))
    if not np.isfinite(lo) or not np.isfinite(hi):
        return
    span = (hi - lo) or (abs(hi) * 0.05) or 1.0
    head = 0.22 if self.ui_labels.value else 0.08
    self._rescaling = True
    try:
        self.fig.layout.yaxis.range = [lo - span * 0.06, hi + span * head]
    finally:
        self._rescaling = False


def _on_query(self, change):
    if self._syncing:
        return
    self._refresh_results(prefer=self.ticker)


def _on_redraw(self, change):
    """Chart-only options: repaint the current name, leave the list alone."""
    if self._syncing or not self.ticker:
        return
    self.draw(self.ticker)


def _on_reset(self, _):
    """Back to the full plotted history, whatever the zoom state."""
    with self.fig.batch_update():
        self.fig.layout.xaxis.autorange = True
    self._rescale()


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


# _hover takes a row, not self, so it stays a staticmethod on the class.
EarningsGallery._hover = staticmethod(_hover)
for _f in (_meta_html, _window, _on_xrange, _rescale, _on_query,
           _on_redraw, _on_reset, _on_clear, _on_pick, _step):
    setattr(EarningsGallery, _f.__name__, _f)

_REQUIRED = ('__init__', '_bind', '_build', '_empty', '_hover', '_meta_html',
             '_on_clear', '_on_pick', '_on_query', '_on_redraw', '_on_reset',
             '_on_xrange', '_window',
             '_refresh_results', '_rescale', '_row_label', '_signal_annotations',
             '_status', '_step', '_visible_catalog', 'draw', 'load',
             'refresh_catalog', 'select')
_missing = [n for n in _REQUIRED if not hasattr(EarningsGallery, n)]
if _missing:
    raise RuntimeError(f'EarningsGallery is incomplete — missing {_missing}. '
                       f'Re-paste Cell 5, then Cell 5b.')

print('Step 3 ready — EarningsGallery() complete')
