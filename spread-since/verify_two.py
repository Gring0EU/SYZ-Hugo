"""Seed Q/R with known numbers, evaluate with the `formulas` engine, and compare
the summary block against an independent computation."""
import json, random, statistics, openpyxl, formulas
random.seed(11)
SRC, TST = 'Spread_Variation_USD_EUR_since_14Jul2026.xlsx', 'two_calc.xlsx'
BDP_COLS = 'BCDEFGHIJKLMNOPT'          # pure-Bloomberg columns the engine cannot evaluate

wb = openpyxl.load_workbook(SRC)
ws = wb[wb.sheetnames[0]]

# find each table's data extent from the ListObject refs
blocks = {}
for name, ref in ws.tables.items():
    a, b = (ref if isinstance(ref, str) else ref.ref).split(":")
    hrow = int(''.join(ch for ch in a if ch.isdigit()))
    last = int(''.join(ch for ch in b if ch.isdigit()))
    blocks[name] = (hrow + 1, last)
print('tables:', blocks)

truth = {}
for name, (first, last) in blocks.items():
    vals = []
    for r in range(first, last + 1):
        for col in BDP_COLS:
            ws[col + str(r)] = None
        isin = ws['A' + str(r)].value
        if isin is None:
            continue
        q = round(random.uniform(40, 700), 3)
        dq = round(random.choice([0, 7.5, -7.5, 20, -20, random.uniform(-45, 45)]), 3)
        ws['Q' + str(r)] = q
        ws['R' + str(r)] = q - dq
        ws['C' + str(r)] = 'Issuer ' + str(r)
        vals.append((isin, round(dq, 6), r, 'Issuer ' + str(r)))
    truth[name] = vals
wb.save(TST)

xl = formulas.ExcelModel().loads(TST).finish()
sol = xl.calculate()
sheet = wb.sheetnames[0].upper()
P = "'[{}]{}'!".format(TST, sheet)
def gv(cell):
    v = sol[P + cell]
    try:    return v.value[0, 0]
    except Exception: return v

# locate summary rows by their labels
labels = {}
for r in range(1, ws.max_row + 1):
    v = ws.cell(r, 1).value
    if isinstance(v, str) and v.strip() in ('Bonds priced', 'Average spread change', 'Median spread change',
                                            'Widened / tightened', 'Biggest widening', 'Biggest tightening',
                                            '... which bond'):
        labels.setdefault(v.strip(), []).append(r)
    elif isinstance(v, str) and v.strip() == '... which bond':
        labels.setdefault('which', []).append(r)
which = [r for r in range(1, ws.max_row + 1)
         if isinstance(ws.cell(r, 1).value, str) and ws.cell(r, 1).value.strip() == '... which bond']

order = list(blocks.keys())                     # tblUSD written first, tblEUR second
bad = 0
for idx, name in enumerate(order):
    vals = truth[name]
    chg = [v[1] for v in vals]
    exp = {
        'Bonds priced':          '{} of {}'.format(len(chg), len(chg)),
        'Average spread change': statistics.fmean(chg),
        'Median spread change':  statistics.median(chg),
        'Widened / tightened':   '{} wider / {} tighter'.format(sum(1 for c in chg if c > 0),
                                                                sum(1 for c in chg if c < 0)),
        'Biggest widening':      max(chg),
        'Biggest tightening':    min(chg),
    }
    for label, want in exp.items():
        got = gv('B{}'.format(labels[label][idx]))
        ok = (abs(float(got) - want) < 1e-6) if isinstance(want, float) else (str(got).strip() == want)
        if not ok:
            print('MISMATCH', name, label, '| got', repr(got), '| want', repr(want)); bad += 1
    # the two "... which bond" lines: first = widener, second = tightener
    for k, target in ((0, max(chg)), (1, min(chg))):
        row = which[idx * 2 + k]
        hit = next(v for v in vals if v[1] == target)
        want = '{} - {}'.format(hit[0], hit[3])
        got = str(gv('B{}'.format(row))).strip()
        if got != want:
            print('MISMATCH', name, 'which bond', k, '| got', repr(got), '| want', repr(want)); bad += 1
    # spare rows must stay blank
    first, last = blocks[name]
    for r in range(first + len(vals), last + 1):
        if gv('S{}'.format(r)) not in ('', None):
            print('SPARE ROW NOT BLANK', name, r, repr(gv('S{}'.format(r)))); bad += 1
print('->', 'ALL MATCH' if bad == 0 else '{} FAILURES'.format(bad))
