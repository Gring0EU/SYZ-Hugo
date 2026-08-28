# ══════════════════════════════════════════════════════════════════════
# CELL 6B — STEP 4, PART 2: THE DASHBOARD PANEL
# The same statistics as before, but arranged so the answer is reachable
# without scrolling: a control bar (window · sector · signals only), then four
# tabs instead of one long column.
#
#   Signals   — what fired, and the headline numbers behind it
#   Breakdown — sector / quarter / drift / split figure, category + signal tables
#   Detail    — country and industry
#   Radar     — who reports next, and how they have behaved
#
# Everything is drawn on the brand white canvas; no colour or palette changes.
# ══════════════════════════════════════════════════════════════════════
import numpy as np
import pandas as pd
import ipywidgets as widgets
from IPython.display import HTML, display, clear_output

TAB_TITLES = ('Signals', 'Breakdown', 'Detail', 'Radar')


class ConclusionDashboard:
    def __init__(self, store=STORE, cfg: Config = CFG):
        self.store, self.cfg = store, cfg
        self.code: str | None = None
        self._syncing = False

        self.ui_window = widgets.Dropdown(
            options=TF_OPTIONS, value='5Y', description='Window:',
            style={'description_width': 'initial'}, layout={'width': '220px'})
        self.ui_sector = widgets.Dropdown(
            options=[('All sectors', 'ALL')], value='ALL', description='Sector:',
            style={'description_width': 'initial'}, layout={'width': '260px'})
        # The technical view: drop every print that price never confirmed.
        self.ui_signals_only = widgets.Checkbox(
            value=False, description='Band-confirmed signals only', indent=False,
            layout={'width': '250px'})
        self.ui_caption = widgets.HTML()

        self.panels = [widgets.Output() for _ in TAB_TITLES]
        self.tabs = widgets.Tab(children=self.panels)
        for i, title in enumerate(TAB_TITLES):
            self.tabs.set_title(i, title)

        for control in (self.ui_window, self.ui_sector, self.ui_signals_only):
            control.observe(self._on_control, names='value')

    @property
    def widget(self):
        bar = widgets.HBox([self.ui_window, self.ui_sector, self.ui_signals_only],
                           layout={'align_items': 'center',
                                   'margin': '0 0 4px 0'})
        return widgets.VBox([bar, self.ui_caption, self.tabs])

    # ── controls ─────────────────────────────────────────────────────
    def _on_control(self, change):
        if not self._syncing:
            self.render(self.code)

    def _sync_sectors(self, sectors: pd.DataFrame):
        """Offer only the sectors this index actually has, keeping the current
        choice when it survives the switch."""
        options = [('All sectors', 'ALL')]
        if sectors is not None and not sectors.empty and 'SECTOR' in sectors:
            options += [(s, s) for s in sorted(sectors['SECTOR'].dropna().unique())]
        if [o[1] for o in options] == [o[1] for o in self.ui_sector.options]:
            return
        keep = self.ui_sector.value
        self._syncing = True
        try:
            self.ui_sector.options = options
            self.ui_sector.value = keep if keep in [o[1] for o in options] else 'ALL'
        finally:
            self._syncing = False

    def _apply_filters(self, ev: pd.DataFrame, sectors: pd.DataFrame):
        """Sector and signal-only narrowing, applied once for every panel."""
        note = []
        if self.ui_sector.value != 'ALL' and sectors is not None \
                and not sectors.empty and 'SECTOR' in sectors:
            members = sectors.loc[sectors['SECTOR'] == self.ui_sector.value,
                                  'TICKER']
            ev = ev[ev['TICKER'].isin(set(members))]
            note.append(f"sector <b>{self.ui_sector.value}</b>")
        if self.ui_signals_only.value:
            ev = signalled(ev)
            note.append('<b>band-confirmed signals only</b>')
        return ev, note

    # ── rendering ────────────────────────────────────────────────────
    def render(self, code: str | None):
        if code is None:
            return
        self.code = code
        tf = self.ui_window.value
        label = self.cfg.label(code)
        events = self.store.get(code, 'events')
        sectors = self.store.get(code, 'sectors')
        self._sync_sectors(sectors)

        if events is None or events.empty:
            self._message(f"No events loaded for <b>{label}</b> — run the "
                          f"pipeline for this index first.", THEME.NEGATIVE)
            return

        ev = ensure_forward_returns(prepare(events),
                                    self.store.get(code, 'prices_wide'), self.cfg)
        ev, cutoff, anchor = filter_window(ev, tf)
        ev, note = self._apply_filters(ev, sectors)
        if ev.empty:
            self._message(f"Nothing matches the current window and filters for "
                          f"<b>{label}</b>.", THEME.MANGO_AMBER)
            return

        k = kpis(ev)
        tbl = category_table(ev, self.cfg)
        extra = (' &nbsp;·&nbsp; ' + ' &nbsp;·&nbsp; '.join(note)) if note else ''
        self.ui_caption.value = (window_caption(tf, cutoff, anchor, k['total'], k)
                                 + (THEME.note(f"Filtered by{extra}") if note else ''))

        # 1 — Signals: the output first, the headline numbers under it.
        with self.panels[0]:
            clear_output(wait=True)
            display(HTML(kpi_strip(k, label, drift_summary(tbl, self.cfg))))
            display(HTML(recent_signals_html(ev)))

        # 2 — Breakdown: where the surprises are and what they paid.
        with self.panels[1]:
            clear_output(wait=True)
            display(_as_widget(overview_figure(
                dim_breakdown(ev, sectors, 'SECTOR'), period_breakdown(ev),
                tbl, k, label, TF_LABELS[tf], self.cfg)))
            display(HTML(category_table_html(tbl, self.cfg)))
            display(HTML(signal_table_html(signal_table(ev, self.cfg), self.cfg)))

        # 3 — Detail: geography and industry.
        with self.panels[2]:
            clear_output(wait=True)
            display(_as_widget(detail_figure(
                dim_breakdown(ev, sectors, 'COUNTRY'),
                dim_breakdown(ev, sectors, 'INDUSTRY', top_n=12),
                label, TF_LABELS[tf])))

        # 4 — Radar: what is coming, and how it has behaved.
        with self.panels[3]:
            clear_output(wait=True)
            display(HTML(radar_table_html(
                radar_table(ev, sectors, self.store.get(code, 'next_earnings')),
                TF_LABELS[tf])))

    def _message(self, html: str, colour: str):
        self.ui_caption.value = ''
        for i, panel in enumerate(self.panels):
            with panel:
                clear_output(wait=True)
                if i == 0:
                    display(HTML(THEME.note(html, colour)))


print('Step 4 ready — ConclusionDashboard() with window · sector · signal filters')
