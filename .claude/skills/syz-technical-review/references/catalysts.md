# Writing "What's driving it"

The first line of the verdict box. It tells the advisor, in two or three sentences, why the stock
has moved and what comes next, so that the technical verdict below it makes sense.

## Research

1. `--news <TICKERS>`: the latest 20 headlines per stock, with dates. They give the recent
   catalysts (the last days and weeks).
2. A web search per stock on the bigger move: "why <company> stock fell / rose in <year>",
   "<company> stock <month> <year>". Prefer company releases, regulators, the large financial press
   and filings; treat small blogs as leads to confirm, not as sources.
3. Note the next dated catalyst: results date (the page shows it), investor day, product launch,
   regulatory decision.

## Pattern

`<direction and size of the move> on <main driver(s), with dates>. <Latest catalyst>. <What
supports / the risk>; <next catalyst and date>.`

- About 300 characters (three lines in the box). Longer text shrinks the chart.
- Numbers must match the page: use the page's YTD or 1-year performance and forward P/E.
- Dates as `dd.mm` (e.g. 21.10), the house style of the page.
- Facts only, each one from the research. Nothing from memory, no forecasts, no "we recommend",
  no "buy" or "sell" (the action lines below do that, in technical terms).
- No source or vendor names on the page. List the links in the hand-over instead.
- Balance: for a falling stock say what supports it; for a rising one say the risk.

## Examples

Exit / reduce (Oracle, October 2026):

> Down 56% from its peak on the cost of its AI build-out: record capex funded with debt and new
> shares, negative free cash flow and an S&P downgrade to BBB-. About half of its order book depends
> on OpenAI, whose lower-than-expected revenue hit the stock in October. Next catalysts: Investor
> Day on 28.10, results in mid-December.

Neutral (Booking, October 2026):

> Down 24% this year on fears that AI travel agents will squeeze online agencies' commissions, after
> guidance was cut in April (Middle East) and the EU court upheld the block of the eTraveli deal
> (09.09). On 21.10 the EU opened a probe into fake listings on Booking.com. In support: 13x forward
> earnings and its own AI agent in the works; results on 03.11.

Positive (Apple, October 2026):

> At a record high: iPhone Duo pre-orders sold out, market share rose to 22% in Q3 despite a
> shrinking smartphone market, and the new Siri AI was well received, putting Apple close to
> overtaking Nvidia in market value. Risks: limited Duo supply, a broker downgrade on shipments and
> 36x forward earnings; results on 02.11.

Currency pair (CHF/EUR, October 2026). `--news` returns nothing for pairs: research central bank
decisions and statements (SNB, ECB), rate differentials, safe-haven flows, intervention, then write
from the base currency's side:

> The franc has recovered its September dip against the euro: EUR/CHF fell from 0.948 (30.09) to
> about 0.92, a three-month low, as worries about European public debt, France in particular,
> revived demand for the franc. The SNB holds rates at 0% and softened its intervention warning in
> September, but stays ready to act; next decision on 10.12.

## Avoid

- "Shares fell due to market conditions": name the driver or leave it out.
- Unverified rumours or single-source claims presented as facts: say "reports of …" or drop them.
- Analyst names and price targets of individual brokers (the page already shows the consensus).
