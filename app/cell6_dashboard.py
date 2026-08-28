# ══════════════════════════════════════════════════════════════════════
# CELL 6 — STEP 4: CONCLUSION DASHBOARD  (part 1 of 2)
# Cards, tables and figures. Cell 6b assembles them into the tabbed panel
# with its window / sector / signal controls.
# Index-level read on the selected trailing window:
#   KPI strip · sector & quarter breakdowns · drift by severity · pos/neg split
#   per-category reaction + PEAD table · band-signal table
#   country & industry detail · upcoming-earnings radar
# All numbers come from the analytics layer; this cell only arranges them.
# ══════════════════════════════════════════════════════════════════════
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import ipywidgets as widgets
from IPython.display import HTML, display, clear_output


def _as_widget(fig: go.Figure):
    """Prefer FigureWidget -- inside a QuApp the widget path is the one that
    reliably draws inside an Output. Plotly 6 needs `anywidget` for that, so
    fall back to the plain figure rather than failing to render at all."""
    try:
        return go.FigureWidget(fig)
    except Exception:
        return fig


# ─────────────────────────────────────────────────────────────
# HTML BLOCKS
# ─────────────────────────────────────────────────────────────
def kpi_strip(k: dict, label: str, note: str) -> str:
    """Headline cards, all of them about band crossings.

    Reports -> crossings -> the two directions -> what the drift was. EPS does
    not appear: the dashboard measures what price did after a report, and the
    crossing is the event.
    """
    def card(title, value, sub, accent):
        return (f"<div style='flex:1;min-width:132px;background:{THEME.SPACE_BLUE};"
                f"border-radius:10px;padding:14px 16px;margin:4px;"
                f"border-left:4px solid {accent}'>"
                f"<div style='color:#9BA6BF;font-size:11px;font-weight:300;"
                f"letter-spacing:.5px;text-transform:uppercase'>{title}</div>"
                f"<div style='color:#fff;font-size:26px;font-weight:800;"
                f"line-height:1.15'>{value}</div>"
                f"<div style='color:{accent};font-size:12px;font-weight:600'>{sub}</div>"
                f"</div>")

    rate = fmt(k['cross_rate'] * 100 if np.isfinite(k.get('cross_rate', np.nan))
               else None, '%', 0)
    horizon = k.get('drift_horizon', 20)
    cards = "".join([
        card('Earnings reports', f"{k['prints']}",
             f"{k.get('names', 0)} names" + (f" · {k['pending']} pending"
                                             if k.get('pending') else ''),
             THEME.NEUTRAL),
        card('Band crossings', f"{k['signals']}", f"{rate} of reports",
             THEME.GOLD_YELLOW),
        card('Upper break', f"{k['n_long']}",
             f"react {fmt(k['avg_ret_long'], '%', 2)}", THEME.POSITIVE),
        card('Lower break', f"{k['n_short']}",
             f"react {fmt(k['avg_ret_short'], '%', 2)}", THEME.NEGATIVE),
        card(f'Drift {horizon}D · upper', fmt(k.get('drift_long'), '%', 2),
             f"lower {fmt(k.get('drift_short'), '%', 2)}", THEME.POSITIVE),
        card(f'Drift {horizon}D · no cross', fmt(k.get('drift_quiet'), '%', 2),
             'the comparison that matters', THEME.NEUTRAL),
    ])
    tail = THEME.note(note) if note else ''
    return (f"<div style='font-family:{THEME.FONT};background:{THEME.WHITE}'>"
            f"<div style='display:flex;flex-wrap:wrap'>{cards}</div>{tail}</div>")


def window_caption(tf: str, cutoff, anchor, n_prints: int, k: dict) -> str:
    if anchor is None:
        return ''
    span = (f"most recent report per constituent, as of {anchor:%Y-%m-%d}"
            if tf == 'LAST' else f"{cutoff:%Y-%m-%d} → {anchor:%Y-%m-%d}")
    pending = (f" &nbsp;·&nbsp; {k['pending']} report(s) too recent to have a "
               f"completed reaction window" if k.get('pending') else '')
    return THEME.note(
        f"Window: <b>{TF_LABELS[tf]}</b> &nbsp;·&nbsp; {span} &nbsp;·&nbsp; "
        f"{n_prints} earnings reports{pending}"
        f"<br>Every panel counts <b>Bollinger band crossings after an earnings "
        f"report</b>: the close was inside the {CFG.bb_window}-day "
        f"±{CFG.bb_sigma}σ band before the print and outside it after. Nothing "
        f"here is derived from EPS.")


def _table(title: str, headers, rows_html: str, footnote: str) -> str:
    # Backgrounds and colours are set inline with !important on every table,
    # row and cell: Jupyter/JupyterLab/VS Code dark themes style <td> directly,
    # so styling only the wrapper is not enough to keep this legible.
    head = "".join(
        f"<th style='padding:8px 11px;text-align:{a};font-weight:300;"
        f"background-color:{THEME.SPACE_BLUE} !important;color:#FFFFFF !important'>"
        f"{h}</th>" for h, a in headers)
    return (f"<div style='font-family:{THEME.FONT};margin-top:6px;"
            f"background-color:{THEME.WHITE} !important'>"
            f"<div style='color:{THEME.SPACE_BLUE} !important;font-weight:800;"
            f"font-size:15px;margin:6px 4px'>{title}</div>"
            f"<table style='border-collapse:collapse;width:100%;font-size:13px;"
            f"background-color:{THEME.WHITE} !important'>"
            f"<thead><tr>{head}</tr></thead><tbody>{rows_html}</tbody></table>"
            f"<div style='color:{THEME.NEUTRAL} !important;font-size:11px;"
            f"font-weight:300;margin:6px 4px'>{footnote}</div></div>")


def _cell(text, bg, color=None, weight=300, align='right'):
    return (f"<td style='padding:7px 11px;text-align:{align};font-weight:{weight};"
            f"background-color:{bg} !important;"
            f"color:{color or THEME.SPACE_BLUE} !important'>{text}</td>")


def signal_table_html(tbl: pd.DataFrame, cfg: Config = CFG) -> str:
    """Confirmed signals against the surprises that never broke the band."""
    if tbl is None or tbl.empty:
        return THEME.note('No rated surprises in this window, so no band '
                          'signals to compare.', THEME.NEUTRAL)
    fwd_cols = [f'FWD_{h}D' for h in cfg.horizons]
    headers = ([('Group', 'left'), ('N', 'right'), ('React %', 'right'),
                ('vs Index %', 'right')] +
               [(f'Fwd {h}D', 'right') for h in cfg.horizons])
    tint = {'Positive — closed through the upper band': THEME.POSITIVE,
            'Negative — closed through the lower band': THEME.NEGATIVE}
    rows = ''
    for i, (_, r) in enumerate(tbl.iterrows()):
        bg = THEME.WHITE if i % 2 == 0 else THEME.ZEBRA
        cells = (_cell(r.Group, bg, tint.get(r.Group, THEME.NEUTRAL), 700, 'left')
                 + _cell(int(r.N), bg)
                 + _cell(fmt(r.React, '%', 2), bg)
                 + _cell(fmt(r.Abn, '%', 2), bg)
                 + "".join(_cell(fmt(r.get(c), '%', 2), bg) for c in fwd_cols))
        rows += f"<tr style='background-color:{bg} !important'>{cells}</tr>"
    return _table(
        'Band surprises — does leaving the range pay?',
        headers, rows,
        f"A signal fires when a rated surprise is confirmed by the close crossing "
        f"the {cfg.bb_window}-day ±{cfg.bb_sigma}σ band in the same direction "
        f"during the reaction window; the price must have been inside the band "
        f"before the print, so a name already outside it does not re-fire. "
        f"Divergent = the band broke against the surprise. The filter earns its "
        f"keep only if the confirmed rows drift further than 'No band cross'.")


def radar_table_html(df: pd.DataFrame, tf_label: str, cfg: Config = CFG) -> str:
    if df is None or df.empty:
        return THEME.note('No upcoming report dates in the loaded data — '
                          're-run the pipeline to refresh them.', THEME.NEUTRAL)
    horizon = cfg.horizons[1] if len(cfg.horizons) > 1 else cfg.horizons[0]
    headers = [('Ticker', 'left'), ('Name', 'left'), ('Next report', 'left'),
               ('In', 'right'), ('Sector', 'left'), ('Mkt cap $bn', 'right'),
               ('Reports', 'right'), ('Crossings', 'right'), ('Cross rate', 'right'),
               ('Upper', 'right'), ('Lower', 'right'), ('Avg react %', 'right'),
               (f'Avg {horizon}D %', 'right'), ('Tendency', 'left')]
    rows = ''
    for i, (_, r) in enumerate(df.iterrows()):
        bg = THEME.WHITE if i % 2 == 0 else THEME.ZEBRA
        tend = r.get('Tendency', '—')
        tint = (THEME.POSITIVE if tend == 'POS' else
                THEME.NEGATIVE if tend == 'NEG' else THEME.NEUTRAL)
        cap = r.get('MKT_CAP_USD')

        def count(key):
            v = r.get(key)
            return '—' if v is None or pd.isna(v) else int(v)

        cells = (_cell(r['TICKER'], bg, THEME.SPACE_BLUE, 700, 'left')
                 + _cell(r['DISPLAY_NAME'], bg, align='left')
                 + _cell(f"{pd.Timestamp(r['NEXT_EARNINGS_DATE']):%Y-%m-%d}", bg,
                         align='left')
                 + _cell(f"{int(r['DAYS_AWAY'])}d", bg)
                 + _cell(r.get('SECTOR', '—'), bg, align='left')
                 + _cell(fmt(cap / 1e9 if pd.notna(cap) else None, '', 1), bg)
                 + _cell(count('Prints'), bg)
                 + _cell(count('Crossings'), bg)
                 + _cell(fmt(r['CrossRate'] * 100 if pd.notna(r.get('CrossRate'))
                             else None, '%', 0), bg)
                 + _cell(count('Upper'), bg)
                 + _cell(count('Lower'), bg)
                 + _cell(fmt(r.get('AvgReact'), '%', 2), bg)
                 + _cell(fmt(r.get('AvgDrift'), '%', 2), bg)
                 + _cell(tend, bg, tint, 700, 'left'))
        rows += f"<tr style='background-color:{bg} !important'>{cells}</tr>"
    return _table(
        'Upcoming reports — how often this name leaves its range', headers, rows,
        f"Report dates are Bloomberg estimates and can move. History is computed "
        f"over the selected window ({tf_label}): Crossings counts reports whose "
        f"close broke the {cfg.bb_window}-day band, Cross rate is that as a share "
        f"of the name's reports, and Tendency is the direction it breaks more "
        f"often.")


def recent_signals_html(ev: pd.DataFrame, n: int = 12) -> str:
    """The last N band crossings: the app's actual output, at the top of the
    page rather than buried under the figures."""
    sig = signalled(ev)
    if sig is None or sig.empty:
        return THEME.note(
            f"No band crossings in this window — every report left the price "
            f"inside its {CFG.bb_window}-day ±{CFG.bb_sigma}σ range.",
            THEME.NEUTRAL)
    total = len(sig)
    sig = sig.sort_values('DATE', ascending=False).head(n)
    headers = [('Reported', 'left'), ('Ticker', 'left'), ('Name', 'left'),
               ('Direction', 'left'), ('Band crossed', 'left'),
               ('Close', 'right'), ('React %', 'right'), ('Fwd 20D %', 'right')]
    rows = ''
    for i, (_, r) in enumerate(sig.iterrows()):
        bg = THEME.WHITE if i % 2 == 0 else THEME.ZEBRA
        up = r['SIGNAL'] == SIGNAL_LONG
        tint = THEME.POSITIVE if up else THEME.NEGATIVE
        rows += (f"<tr style='background-color:{bg} !important'>"
                 + _cell(f"{pd.Timestamp(r['DATE']):%Y-%m-%d}", bg, align='left')
                 + _cell(r['TICKER'], bg, THEME.SPACE_BLUE, 700, 'left')
                 + _cell(r.get('NAME', '—'), bg, align='left')
                 + _cell('Positive' if up else 'Negative', bg, tint, 700, 'left')
                 + _cell(f"{str(r['BB_CROSS']).lower()} band", bg, align='left')
                 + _cell(fmt(r.get('PRICE_AT_EVENT'), '', 2), bg)
                 + _cell(fmt(r.get('RET(%)'), '%', 2), bg)
                 + _cell(fmt(r.get('FWD_20D'), '%', 2), bg)
                 + "</tr>")
    return _table(
        f'Latest band crossings after an earnings report — {total} in this window',
        headers, rows,
        f"The close was inside the {CFG.bb_window}-day ±{CFG.bb_sigma}σ band "
        f"before the report and outside it after: through the upper band is a "
        f"positive surprise, through the lower a negative one. React % is the "
        f"reaction around the print; Fwd 20D % is the drift measured from the "
        f"close of that window.")


# ─────────────────────────────────────────────────────────────
# FIGURES
# ─────────────────────────────────────────────────────────────
def overview_figure(sector_bd, period_bd, sig_tbl, k, label, tf_label,
                    cfg: Config = CFG) -> go.Figure:
    """Where the crossings are, when they happened, and what they paid."""
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=('Band crossings by GICS sector',
                        'Band crossings by quarter',
                        'Mean return after the report, by what the band did',
                        'Crossing direction'),
        specs=[[{'type': 'xy'}, {'type': 'xy'}],
               [{'type': 'xy'}, {'type': 'domain'}]],
        horizontal_spacing=0.12, vertical_spacing=0.16)

    for col, colour, name, show in (('POS', THEME.POSITIVE, 'Upper break', True),
                                    ('NEG', THEME.NEGATIVE, 'Lower break', True)):
        fig.add_trace(go.Bar(y=sector_bd.index, x=sector_bd.get(col, []),
                             name=name, orientation='h', marker_color=colour,
                             legendgroup=name, showlegend=show), 1, 1)
        fig.add_trace(go.Bar(x=period_bd.index, y=period_bd.get(col, []),
                             name=name, marker_color=colour,
                             legendgroup=name, showlegend=False), 1, 2)

    # The third panel is the whole argument: a break that keeps drifting, next
    # to the reports that never left the range.
    order = [SIGNAL_GROUP_UP, SIGNAL_GROUP_DOWN, SIGNAL_GROUP_NONE]
    short = {SIGNAL_GROUP_UP: 'Upper break', SIGNAL_GROUP_DOWN: 'Lower break',
             SIGNAL_GROUP_NONE: 'No cross'}
    groups = [g for g in order if not sig_tbl.empty and g in set(sig_tbl.Group)]
    sub = sig_tbl.set_index('Group').reindex(groups) if groups else pd.DataFrame()
    if not sub.empty:
        fig.add_trace(go.Bar(x=[short[g] for g in groups], y=sub['React'],
                             name='Reaction', marker_color=THEME.BLUEBERRY_BLUE),
                      2, 1)
        for h in cfg.horizons:
            col = f'FWD_{h}D'
            if col in sub.columns:
                fig.add_trace(go.Bar(x=[short[g] for g in groups], y=sub[col],
                                     name=f'{h}D drift',
                                     marker_color=THEME.HORIZON_COLORS.get(
                                         h, THEME.NEUTRAL)), 2, 1)

    fig.add_trace(go.Pie(labels=['Upper break', 'Lower break'],
                         values=[k['n_long'], k['n_short']], hole=.55,
                         marker_colors=[THEME.POSITIVE, THEME.NEGATIVE],
                         sort=False, textinfo='label+percent',
                         showlegend=False), 2, 2)

    fig.update_layout(**THEME.layout(
        height=760, barmode='group', bargap=0.25,
        margin=dict(l=20, r=20, t=90, b=20),
        title=THEME.title(f"<b>{label}</b> — {tf_label} band crossings after "
                          f"earnings")))
    THEME.style_axes(fig)
    fig.update_yaxes(row=1, col=1, automargin=True)
    fig.update_xaxes(row=1, col=2, tickangle=-45)
    fig.update_yaxes(row=2, col=1, title_text='Mean return %')
    return fig


def detail_figure(country_bd, industry_bd, label, tf_label) -> go.Figure:
    fig = make_subplots(rows=1, cols=2, horizontal_spacing=0.16,
                        subplot_titles=('Band crossings by country',
                                        'Band crossings by industry (top 12)'))
    for col, colour, name in (('POS', THEME.POSITIVE, 'Upper break'),
                              ('NEG', THEME.NEGATIVE, 'Lower break')):
        fig.add_trace(go.Bar(y=country_bd.index, x=country_bd.get(col, []),
                             name=name, orientation='h', marker_color=colour,
                             legendgroup=name, showlegend=True), 1, 1)
        fig.add_trace(go.Bar(y=industry_bd.index, x=industry_bd.get(col, []),
                             name=name, orientation='h', marker_color=colour,
                             legendgroup=name, showlegend=False), 1, 2)

    height = max(360, 34 * max(len(country_bd), len(industry_bd), 4))
    fig.update_layout(**THEME.layout(
        height=height, barmode='group', bargap=0.25,
        title=THEME.title(f"<b>{label}</b> — geographic and industry detail "
                          f"({tf_label})", size=16)))
    THEME.style_axes(fig)
    fig.update_yaxes(automargin=True)
    return fig


print('Step 4 (part 1) ready — now run Cell 6b for the dashboard panel')
