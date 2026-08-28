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
    """Headline cards. 'Earnings prints' is every announcement in the window;
    everything to its right narrows -- rated, then surprising, then confirmed
    by the band -- so the strip reads left to right as a funnel and the counts
    reconcile against the chart."""

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

    rate = fmt(k['rate'] * 100 if np.isfinite(k['rate']) else None, '%', 0)
    sig_rate = fmt(k['signal_rate'] * 100
                   if np.isfinite(k.get('signal_rate', np.nan)) else None, '%', 0)
    prints = k['total'] + k['unrated']
    cards = "".join([
        card('Earnings prints', f"{prints}",
             f"{k['total']} rated · {k['unrated']} unrated", THEME.NEUTRAL),
        card('Rated events', f"{k['total']}",
             (f"{k['unrated']} unrated" if k['unrated'] else label), THEME.POSITIVE),
        card('Surprises', f"{k['surprises']}", f"{rate} of rated", THEME.NEGATIVE),
        card('Positive', f"{k['n_pos']}",
             f"react {fmt(k['avg_ret_pos'], '%', 2)}", THEME.POSITIVE),
        card('Negative', f"{k['n_neg']}",
             f"react {fmt(k['avg_ret_neg'], '%', 2)}", THEME.NEGATIVE),
        card('Band surprises', f"{k.get('signals', 0)}",
             f"{k.get('n_long', 0)} upper / {k.get('n_short', 0)} lower "
             f"· {sig_rate} of prints", THEME.GOLD_YELLOW),
        card('Hit-rate', fmt(k['hit'] * 100 if k['hit'] == k['hit'] else None, '%', 0),
             f"pos {fmt(k['pos_hit']*100 if k['pos_hit']==k['pos_hit'] else None,'%',0)}"
             f" / neg {fmt(k['neg_hit']*100 if k['neg_hit']==k['neg_hit'] else None,'%',0)}",
             THEME.NEUTRAL),
    ])
    tail = THEME.note(note) if note else ''
    return (f"<div style='font-family:{THEME.FONT};background:{THEME.WHITE}'>"
            f"<div style='display:flex;flex-wrap:wrap'>{cards}</div>{tail}</div>")


def window_caption(tf: str, cutoff, anchor, n_rated: int, k: dict) -> str:
    if anchor is None:
        return ''
    span = (f"most recent print per constituent, as of {anchor:%Y-%m-%d}"
            if tf == 'LAST' else f"{cutoff:%Y-%m-%d} → {anchor:%Y-%m-%d}")
    src = (f" &nbsp;·&nbsp; {k['analyst_share']:.0%} of scores from consensus"
           if np.isfinite(k.get('analyst_share', np.nan)) else '')
    pending = (f" &nbsp;·&nbsp; {k['pending']} print(s) too recent to have a "
               f"completed reaction window" if k.get('pending') else '')
    return THEME.note(
        f"Window: <b>{TF_LABELS[tf]}</b> &nbsp;·&nbsp; {span} &nbsp;·&nbsp; "
        f"{n_rated} rated prints{src}{pending}"
        f"<br>Sector, quarter and pos/neg panels count <b>surprise prints "
        f"only</b> (|SUE| ≥ {CFG.moderate_sigma}); the category and drift "
        f"tables cover every rated print, In Line included.")


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


def category_table_html(tbl: pd.DataFrame, cfg: Config = CFG) -> str:
    if tbl.empty:
        return ''
    fwd_cols = [f'FWD_{h}D' for h in cfg.horizons]
    headers = ([('Category', 'left'), ('N', 'right'), ('Signals', 'right'),
                ('Avg σ', 'right'), ('React %', 'right'), ('vs Index %', 'right')] +
               [(f'Fwd {h}D', 'right') for h in cfg.horizons] +
               [('Hit %', 'right')])
    rows = ''
    for i, (_, r) in enumerate(tbl.iterrows()):
        bg = THEME.WHITE if i % 2 == 0 else THEME.ZEBRA
        accent = THEME.CATEGORY_COLORS.get(r.Category, THEME.NEUTRAL)
        cells = (_cell(r.Category, bg, accent, 700, 'left')
                 + _cell(int(r.N), bg)
                 + _cell(int(r.get('Signals', 0)), bg)
                 + _cell(fmt(r.AvgSigma, '', 2), bg)
                 + _cell(fmt(r.React, '%', 2), bg)
                 + _cell(fmt(r.Abn, '%', 2), bg)
                 + "".join(_cell(fmt(r.get(c), '%', 2), bg) for c in fwd_cols)
                 + _cell(fmt(r.HitRate * 100 if pd.notna(r.HitRate) else None,
                             '%', 0), bg))
        rows += f"<tr style='background-color:{bg} !important'>{cells}</tr>"
    return _table(
        'Per-category performance — reaction and post-event drift', headers, rows,
        f"React % = {cfg.reaction_pre}+{cfg.reaction_post} day reaction around the "
        f"print. vs Index % = same window, benchmark-adjusted. Signals = prints in "
        f"the bucket that also closed through the {cfg.bb_window}-day "
        f"±{cfg.bb_sigma}σ Bollinger band. Fwd = mean return measured from the "
        f"close of the reaction window, so it isolates drift from the announcement "
        f"jump. Hit % = share of surprises whose reaction agreed with the SUE sign "
        f"(undefined for In Line).")


def signal_table_html(tbl: pd.DataFrame, cfg: Config = CFG) -> str:
    """Confirmed signals against the surprises that never broke the band."""
    if tbl is None or tbl.empty:
        return THEME.note('No rated surprises in this window, so no band '
                          'signals to compare.', THEME.NEUTRAL)
    fwd_cols = [f'FWD_{h}D' for h in cfg.horizons]
    headers = ([('Group', 'left'), ('N', 'right'), ('Avg SUE σ', 'right'),
                ('React %', 'right'), ('vs Index %', 'right')] +
               [(f'Fwd {h}D', 'right') for h in cfg.horizons] +
               [('EPS agreed %', 'right')])
    tint = {'Positive — closed through the upper band': THEME.POSITIVE,
            'Negative — closed through the lower band': THEME.NEGATIVE}
    rows = ''
    for i, (_, r) in enumerate(tbl.iterrows()):
        bg = THEME.WHITE if i % 2 == 0 else THEME.ZEBRA
        cells = (_cell(r.Group, bg, tint.get(r.Group, THEME.NEUTRAL), 700, 'left')
                 + _cell(int(r.N), bg)
                 + _cell(fmt(r.AvgSigma, '', 2), bg)
                 + _cell(fmt(r.React, '%', 2), bg)
                 + _cell(fmt(r.Abn, '%', 2), bg)
                 + "".join(_cell(fmt(r.get(c), '%', 2), bg) for c in fwd_cols)
                 + _cell(fmt(r.SueAgrees * 100 if pd.notna(r.SueAgrees) else None,
                             '%', 0), bg))
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


def radar_table_html(df: pd.DataFrame, tf_label: str) -> str:
    if df is None or df.empty:
        return THEME.note('No upcoming report dates in the loaded data — '
                          're-run the pipeline to refresh them.', THEME.NEUTRAL)
    headers = [('Ticker', 'left'), ('Name', 'left'), ('Next report', 'left'),
               ('In', 'right'), ('Sector', 'left'), ('Mkt cap $bn', 'right'),
               ('Prints', 'right'), ('Surprises', 'right'), ('Signals', 'right'),
               ('Avg σ', 'right'), ('Avg react %', 'right'), ('Hit %', 'right'),
               ('Tendency', 'left')]
    rows = ''
    for i, (_, r) in enumerate(df.iterrows()):
        bg = THEME.WHITE if i % 2 == 0 else THEME.ZEBRA
        tend = r.get('Tendency', '—')
        tint = (THEME.POSITIVE if tend == 'POS' else
                THEME.NEGATIVE if tend == 'NEG' else THEME.NEUTRAL)
        cap = r.get('MKT_CAP_USD')
        prints_ = r.get('Prints')
        surp = r.get('Surprises')
        sigs = r.get('Signals')
        cells = (_cell(r['TICKER'], bg, THEME.SPACE_BLUE, 700, 'left')
                 + _cell(r['DISPLAY_NAME'], bg, align='left')
                 + _cell(f"{pd.Timestamp(r['NEXT_EARNINGS_DATE']):%Y-%m-%d}", bg,
                         align='left')
                 + _cell(f"{int(r['DAYS_AWAY'])}d", bg)
                 + _cell(r.get('SECTOR', '—'), bg, align='left')
                 + _cell(fmt(cap / 1e9 if pd.notna(cap) else None, '', 1), bg)
                 + _cell('—' if pd.isna(prints_) else int(prints_), bg)
                 + _cell('—' if pd.isna(surp) else int(surp), bg)
                 + _cell('—' if sigs is None or pd.isna(sigs) else int(sigs), bg)
                 + _cell(fmt(r.get('AvgSigma'), '', 2), bg)
                 + _cell(fmt(r.get('AvgRet'), '%', 2), bg)
                 + _cell(fmt(r['HitRate'] * 100 if pd.notna(r.get('HitRate'))
                             else None, '%', 0), bg)
                 + _cell(tend, bg, tint, 700, 'left'))
        rows += f"<tr style='background-color:{bg} !important'>{cells}</tr>"
    return _table(
        'Upcoming earnings radar — next reports vs historical tendency', headers,
        rows,
        f"Report dates are Bloomberg estimates and can move. History columns are "
        f"computed over the selected window ({tf_label}); Signals counts past "
        f"prints where a surprise was confirmed by a Bollinger band cross; "
        f"Tendency is the majority direction of that name's past surprises.")


def recent_signals_html(ev: pd.DataFrame, n: int = 10) -> str:
    """The last N band-confirmed signals: the app's actual output, at the top
    of the page instead of buried under four figures."""
    sig = signalled(ev)
    if sig is None or sig.empty:
        return THEME.note(
            f"No band-confirmed signals in this window — every surprise either "
            f"stayed inside the {CFG.bb_window}-day band or broke it against "
            f"the surprise.", THEME.NEUTRAL)
    sig = sig.sort_values('DATE', ascending=False).head(n)
    headers = [('Reported', 'left'), ('Ticker', 'left'), ('Name', 'left'),
               ('Signal', 'left'), ('Band', 'left'), ('SUE σ', 'right'),
               ('React %', 'right'), ('Fwd 20D %', 'right')]
    rows = ''
    for i, (_, r) in enumerate(sig.iterrows()):
        bg = THEME.WHITE if i % 2 == 0 else THEME.ZEBRA
        tint = THEME.POSITIVE if r['SIGNAL'] == SIGNAL_LONG else THEME.NEGATIVE
        rows += (f"<tr style='background-color:{bg} !important'>"
                 + _cell(f"{pd.Timestamp(r['DATE']):%Y-%m-%d}", bg, align='left')
                 + _cell(r['TICKER'], bg, THEME.SPACE_BLUE, 700, 'left')
                 + _cell(r.get('NAME', '—'), bg, align='left')
                 + _cell(r['SIGNAL'], bg, tint, 700, 'left')
                 + _cell(f"{r['BB_CROSS']} band", bg, align='left')
                 + _cell(fmt(r.get('SIGMA'), '', 2), bg)
                 + _cell(fmt(r.get('RET(%)'), '%', 2), bg)
                 + _cell(fmt(r.get('FWD_20D'), '%', 2), bg)
                 + "</tr>")
    return _table(
        f'Latest band surprises — {len(signalled(ev))} in this window',
        headers, rows,
        f"An earnings surprise whose close crossed the {CFG.bb_window}-day "
        f"±{CFG.bb_sigma}σ band in the same direction during the reaction "
        f"window. React % is the announcement reaction; Fwd 20D % is the drift "
        f"measured from the close of that window.")


# ─────────────────────────────────────────────────────────────
# FIGURES
# ─────────────────────────────────────────────────────────────
def overview_figure(sector_bd, period_bd, tbl, k, label, tf_label,
                    cfg: Config = CFG) -> go.Figure:
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=('Surprise prints by GICS sector',
                        'Surprise prints by quarter',
                        'Post-event drift by severity — all rated prints',
                        'Surprise prints: positive vs negative'),
        specs=[[{'type': 'xy'}, {'type': 'xy'}],
               [{'type': 'xy'}, {'type': 'domain'}]],
        horizontal_spacing=0.12, vertical_spacing=0.16)

    for col, colour, name, show in (('POS', THEME.POSITIVE, 'Positive', True),
                                    ('NEG', THEME.NEGATIVE, 'Negative', True)):
        fig.add_trace(go.Bar(y=sector_bd.index, x=sector_bd.get(col, []),
                             name=name, orientation='h', marker_color=colour,
                             legendgroup=name, showlegend=show), 1, 1)
        fig.add_trace(go.Bar(x=period_bd.index, y=period_bd.get(col, []),
                             name=name, marker_color=colour,
                             legendgroup=name, showlegend=False), 1, 2)

    cats = [c for c in CAT_ORDER if c in set(tbl.Category)] if not tbl.empty else []
    sub = tbl.set_index('Category').reindex(cats) if cats else pd.DataFrame()
    for h in cfg.horizons:
        col = f'FWD_{h}D'
        if not sub.empty and col in sub.columns:
            fig.add_trace(go.Bar(x=cats, y=sub[col], name=f'{h}D',
                                 marker_color=THEME.HORIZON_COLORS.get(
                                     h, THEME.NEUTRAL)), 2, 1)

    fig.add_trace(go.Pie(labels=['Positive', 'Negative'],
                         values=[k['n_pos'], k['n_neg']], hole=.55,
                         marker_colors=[THEME.POSITIVE, THEME.NEGATIVE],
                         sort=False, textinfo='label+percent',
                         showlegend=False), 2, 2)

    fig.update_layout(**THEME.layout(
        height=760, barmode='group', bargap=0.25,
        margin=dict(l=20, r=20, t=90, b=20),
        title=THEME.title(f"<b>{label}</b> — {tf_label} earnings-surprise conclusion")))
    THEME.style_axes(fig)
    fig.update_yaxes(row=1, col=1, automargin=True)
    fig.update_xaxes(row=1, col=2, tickangle=-45)
    fig.update_yaxes(row=2, col=1, title_text='Mean fwd return %')
    return fig


def detail_figure(country_bd, industry_bd, label, tf_label) -> go.Figure:
    fig = make_subplots(rows=1, cols=2, horizontal_spacing=0.16,
                        subplot_titles=('Surprises by country',
                                        'Surprises by industry (top 12)'))
    for col, colour, name in (('POS', THEME.POSITIVE, 'Positive'),
                              ('NEG', THEME.NEGATIVE, 'Negative')):
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
