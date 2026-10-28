
## Claude connector (`mcp_server.py`)

`mcp_server.py` makes the free data sources available to Claude as tools. It is an MCP server, the format Claude uses for connectors. No account or API key is needed.

| Tool | Source | What it gives |
|---|---|---|
| `yahoo_quote` | Yahoo | Last price, previous close, change, currency |
| `yahoo_history` | Yahoo | OHLCV bars, adjusted |
| `yahoo_profile` | Yahoo | Sector, market cap, P/E, yield, beta, next earnings |
| `yahoo_option_expiries`, `yahoo_option_chain` | Yahoo | Option expiries; bid, ask, last, open interest, implied vol |
| `yahoo_search` | Yahoo | Symbol from a name or ISIN |
| `stooq_history` | Stooq | Full daily history (backup for Yahoo) |
| `ecb_fx`, `ecb_series` | ECB | Euro reference rates; any ECB series (deposit rate, €STR, inflation) |
| `frankfurter_fx` | Frankfurter | ECB rates with any base currency |
| `snb_rates`, `snb_cube` | SNB | SARON, SOFR, €STR, SONIA, TONA, policy rate; any SNB cube |

**Claude Code** starts it by itself: the `.mcp.json` file at the root of the repository declares it. It needs `pip install mcp yfinance`. In a claude.ai cloud environment, put that line in the setup script and allow these domains:

```
query1.finance.yahoo.com
query2.finance.yahoo.com
finance.yahoo.com
fc.yahoo.com
guce.yahoo.com
stooq.com
stooq.pl
data-api.ecb.europa.eu
www.ecb.europa.eu
api.frankfurter.app
api.frankfurter.dev
data.snb.ch
```

**Claude Desktop**: add the same block as in `.mcp.json` to `claude_desktop_config.json`, with the full path to `mcp_server.py`.
