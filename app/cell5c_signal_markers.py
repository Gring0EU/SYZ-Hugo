# ── Cell 5c — make the band signal visible on the chart ──────────────
# A signalled print is the whole point of the app, so it should read at a
# glance: a coloured vertical line on the announcement date and a labelled
# arrow on the print itself, green for LONG and orange for SHORT. Wrapping
# draw() rather than editing it keeps this a small, paste-safe cell.
import pandas as pd

_gallery_draw = EarningsGallery.draw

SIGNAL_COLOR = {SIGNAL_LONG: THEME.MINT_GREEN, SIGNAL_SHORT: THEME.TIGER_ORANGE}


def draw(self, ticker: str):
    _gallery_draw(self, ticker)                 # lines, band, markers, halos
    if self.prices.empty or self.events.empty:
        return

    ev = self.events[(self.events.TICKER == ticker) &
                     self.events['SIGNAL'].isin(ACTIVE_SIGNALS)]
    ev = ev[ev['PRICE_AT_EVENT'].notna()]

    shapes, notes = list(self.fig.layout.shapes), []
    for _, r in ev.iterrows():
        date = pd.Timestamp(r['TRADE_DATE'])
        colour = SIGNAL_COLOR.get(r['SIGNAL'], THEME.SPACE_BLUE)
        # Solid, coloured guide replaces nothing — it sits on top of the faint
        # grey guide already drawn for every print, so the signalled dates are
        # the only ones that read as a line.
        shapes.append(dict(type='line', xref='x', yref='paper', y0=0, y1=1,
                           x0=date, x1=date, layer='below',
                           line=dict(color=colour, width=2)))
        sigma = (f" · {r['SIGMA']:+.1f}σ" if pd.notna(r.get('SIGMA')) else '')
        notes.append(dict(
            x=date, y=float(r['PRICE_AT_EVENT']), xref='x', yref='y',
            text=f"<b>{r['SIGNAL']}</b> {date:%d %b %Y}{sigma}",
            showarrow=True, arrowhead=2, arrowsize=1, arrowwidth=1.5,
            arrowcolor=colour, ax=0, ay=-46,
            font=dict(family=THEME.FONT, size=11, color=THEME.WHITE),
            bgcolor=colour, bordercolor=colour, borderpad=3, opacity=0.95))

    with self.fig.batch_update():
        self.fig.layout.shapes = tuple(shapes)
        self.fig.layout.annotations = tuple(notes)
        # Bigger, thicker halo: at chart scale the 26px ring was easy to miss.
        self.fig.data[T_SIGNAL].marker.size = 30
        self.fig.data[T_SIGNAL].marker.line.width = 3


EarningsGallery.draw = draw

print('Cell 5c ready — signalled prints now carry a coloured guide and label')
