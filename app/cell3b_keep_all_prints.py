# ── Cell 3b — keep every announcement inside the plotted window ──────
# build_events used to drop any print whose reaction window was not fully
# inside the price history, which silently removed the most recent print --
# the one with no t+1 close yet, and the one the chart most needs to show.
# A print is now kept whenever the announcement itself lands on the price
# calendar; its RET(%)/FWD_* stay NaN and every downstream mean skips them.
import numpy as np
import pandas as pd


def build_events(earnings: pd.DataFrame, prices_wide: pd.DataFrame,
                 benchmark: pd.DataFrame | None = None,
                 cfg: Config = CFG) -> pd.DataFrame:
    """earnings + prices  ->  the canonical event table."""
    if earnings is None or earnings.empty:
        return pd.DataFrame(columns=EVENT_COLUMNS)

    df = classify(compute_sue(earnings, cfg), cfg)
    if df.empty:
        return pd.DataFrame(columns=EVENT_COLUMNS)

    df['DATE'] = df['ANNOUNCE_DATE']
    if 'NAME' not in df.columns:
        df['NAME'] = df['TICKER']

    rets = event_returns(df, prices_wide, benchmark, cfg)
    df = pd.concat([df, rets], axis=1)
    df = band_signals(df)

    # Prints older than the plotted history: searchsorted pins them to the
    # first session, which would stack them against the left edge of the
    # chart. Void their coordinates so the drop below removes them.
    if prices_wide is not None and not prices_wide.empty:
        before = pd.to_datetime(df['DATE']) < prices_wide.index[0]
        df.loc[before, ['PRICE_AT_EVENT', 'TRADE_DATE_I']] = np.nan

    # Snap the announcement onto the trading calendar so the gallery can place
    # a marker exactly on a plotted point instead of between two sessions.
    if prices_wide is not None and not prices_wide.empty:
        idx = prices_wide.index
        take = df['TRADE_DATE_I'].to_numpy()
        snapped = np.where(np.isfinite(take),
                           idx.to_numpy()[np.nan_to_num(take, nan=0).astype(int)],
                           df['DATE'].to_numpy())
        df['TRADE_DATE'] = pd.to_datetime(snapped)
    else:
        df['TRADE_DATE'] = df['DATE']

    df['QUARTER'] = df['DATE'].dt.to_period('Q').astype(str)
    df['YEAR'] = df['DATE'].dt.year
    df['FISCAL_Q'] = df['FISCAL_Q'].astype(str)

    keep = EVENT_COLUMNS + [f'FWD_{h}D' for h in cfg.horizons]
    for col in keep:
        if col not in df.columns:
            df[col] = np.nan
    # Keep every print that lands on the plotted calendar, including one too
    # recent to have a completed reaction window.
    df = df.dropna(subset=['PRICE_AT_EVENT'])
    return (df[keep].sort_values(['TICKER', 'DATE'])
                    .reset_index(drop=True))


def _hit_rate(df: pd.DataFrame) -> float:
    """Share of surprises whose market reaction agreed with the SUE sign."""
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


print('Cell 3b ready — re-run the pipeline with Force re-pull to rebuild events')
