# ══════════════════════════════════════════════════════════════════════
# CELL 7 — PIPELINE ORCHESTRATION + APP SHELL
# One index selector and one Load button drive the whole system: ingest ->
# event engine -> both front-ends, all off the same in-memory bundle.
# Switching to an index already in the store (or on disk) re-renders with no
# Bloomberg round-trip at all.
# ══════════════════════════════════════════════════════════════════════
import traceback

import ipywidgets as widgets
from IPython.display import HTML, display, clear_output


def run_pipeline(code: str, force: bool = False, store=STORE,
                 cfg: Config = CFG, report: Reporter | None = None) -> dict:
    """Step 1 + Step 2 for one index. Cheap and idempotent when data is fresh."""
    report = report or Reporter()
    if not force and store.is_fresh(code, 'events'):
        age = store.age(code, 'events') or 0
        report(f"{cfg.label(code)}: using cached data "
               f"({age/60:.0f} min old, TTL {cfg.cache_ttl/60:.0f} min)")
        return store.bundle(code)

    bundle = ingest(code, report=report)
    bundle['events'] = run_event_engine(code, report=report)
    return bundle


def ensure_loaded(code: str, store=STORE, cfg: Config = CFG,
                  report: Reporter | None = None) -> bool:
    """True if the index can be displayed. Pulls from memory, then disk, and
    only queries Bloomberg when neither has it."""
    if store.get(code, 'events') is not None and store.get(code, 'prices_wide') is not None:
        return True
    try:
        run_pipeline(code, store=store, cfg=cfg, report=report)
        return True
    except Exception as exc:
        (report or Reporter())(f"Could not load {cfg.label(code)}: {exc}")
        return False


class ResearchLab:
    """The whole lab behind one control bar."""

    def __init__(self, store=STORE, cfg: Config = CFG):
        self.store, self.cfg = store, cfg
        self.gallery = EarningsGallery(store, cfg)
        self.dashboard = ConclusionDashboard(store, cfg)
        # A cross-index search result rebinds the gallery on its own; this
        # keeps the shell's dropdown and dashboard pointing at the same index.
        self.gallery.on_index_change = self._follow_gallery
        self._following = False

        self.ui_index = widgets.Dropdown(
            options=cfg.universe_options(), value=cfg.universes[0][1],
            description='Index:', style={'description_width': 'initial'},
            layout={'width': '260px'})
        self.ui_load = widgets.Button(description='Load / refresh',
                                      button_style='info', icon='download',
                                      layout={'width': '160px'})
        self.ui_force = widgets.Checkbox(value=False, description='Force re-pull',
                                         indent=False, layout={'width': '150px'})
        # Any Bloomberg index, without editing Config: index ticker conventions
        # differ by terminal, and a name that does not resolve here may resolve
        # under a different ticker.
        self.ui_custom = widgets.Text(
            value='', placeholder='or load any index ticker, e.g. SMI Index',
            description='Custom:', style={'description_width': 'initial'},
            layout={'width': '330px'})
        self.ui_state = widgets.HTML()
        self.console = widgets.Output(layout={'border': f'1px solid {THEME.HAIRLINE}',
                                              'padding': '8px',
                                              'max_height': '320px',
                                              'overflow': 'auto'})
        self.status = widgets.Output()

        self.tabs = widgets.Tab(children=[
            widgets.VBox([self.console, self.status]),
            self.gallery.widget,
            self.dashboard.widget,
        ])
        for i, title in enumerate(('Data & log', 'Asset gallery',
                                   'Conclusion dashboard')):
            self.tabs.set_title(i, title)

        self.ui_load.on_click(self._on_load)
        self.ui_index.observe(self._on_index, names='value')

    # ── rendering ────────────────────────────────────────────────────
    def show(self):
        THEME.inject()
        bar = widgets.HBox([self.ui_index, self.ui_load, self.ui_force,
                            self.ui_state],
                           layout={'align_items': 'center'})
        bar2 = widgets.HBox([self.ui_custom],
                            layout={'align_items': 'center',
                                    'margin': '4px 0 10px 0'})
        display(widgets.VBox([bar, bar2, self.tabs]))
        self._sync(self.ui_index.value, allow_fetch=False)

    def _flag(self, text: str, colour: str):
        self.ui_state.value = (f"<span style='font-family:{THEME.FONT};"
                               f"color:{colour};font-weight:600;margin-left:12px'>"
                               f"{text}</span>")

    def _sync(self, code: str, allow_fetch: bool, refresh_gallery: bool = True):
        """Point both front-ends at an index, fetching only if asked to."""
        available = self.store.get(code, 'events') is not None
        if not available and allow_fetch:
            available = ensure_loaded(code, self.store, self.cfg)
        if refresh_gallery:
            self.gallery.load(code, keep_selection=False)
        self.dashboard.render(code)
        with self.status:
            clear_output(wait=True)
            frame = self.store.status()
            if not frame.empty:
                display(HTML(THEME.note('Store contents', size=13)))
                display(frame)
        if available:
            age = self.store.age(code, 'events')
            stamp = f" · {age/60:.0f} min old" if age else ''
            self._flag(f"{self.cfg.label(code)} ready{stamp}", THEME.MINT_GREEN)
        else:
            self._flag(f"{self.cfg.label(code)} not loaded — press "
                       f"Load / refresh", THEME.MANGO_AMBER)

    # ── callbacks ────────────────────────────────────────────────────
    def _register_custom(self) -> str | None:
        """Turn whatever is in the custom box into a selectable universe."""
        raw = self.ui_custom.value.strip()
        if not raw:
            return None
        code = register_universe(raw)
        options = self.cfg.universe_options()
        if self.ui_index.options != options:
            self._following = True          # options churn must not re-sync
            try:
                self.ui_index.options = options
            finally:
                self._following = False
        self.ui_index.value = code
        self.ui_custom.value = ''
        return code

    def _on_load(self, _):
        try:
            custom = self._register_custom()
        except Exception as exc:
            self._flag(f'invalid ticker: {exc}', THEME.TIGER_ORANGE)
            return
        code = custom or self.ui_index.value
        self.ui_load.disabled, self.ui_load.description = True, 'Running…'
        self._flag('working…', THEME.BLUEBERRY_BLUE)
        self.tabs.selected_index = 0
        failure = None
        with self.console:
            clear_output(wait=True)
            try:
                run_pipeline(code, force=self.ui_force.value,
                             store=self.store, cfg=self.cfg)
            except Exception as exc:
                failure = exc
                # The formatted traceback goes to stdout so it stays inline in
                # the log; print_exc() would send it to stderr, where the
                # front-end renders it as a detached block.
                print(f"Pipeline failed for {self.cfg.label(code)} ({code}): {exc}\n")
                print(traceback.format_exc())
                print(f"To check whether the index ticker itself resolves, run:"
                      f"\n    probe_universes(['{code}'])")
            finally:
                self.ui_load.disabled = False
                self.ui_load.description = 'Load / refresh'
        self._sync(code, allow_fetch=False)
        if failure is not None:
            # _sync would otherwise leave 'not loaded', which points the user at
            # the wrong problem -- the load was attempted and it broke.
            self._flag('load failed — see the log tab', THEME.TIGER_ORANGE)

    def _on_index(self, change):
        # Switching index never triggers a pull on its own: a 500-name refresh
        # should be a deliberate click, not a side effect of browsing.
        # When the gallery drove the change, it has already rebound itself --
        # reloading it here would throw away the asset the user just picked.
        self._sync(change['new'], allow_fetch=False,
                   refresh_gallery=not self._following)

    def _follow_gallery(self, code: str):
        if code == self.ui_index.value:
            return
        self._following = True
        try:
            self.ui_index.value = code
        finally:
            self._following = False


LAB = ResearchLab()
LAB.show()
