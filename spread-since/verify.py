"""Evaluate the mini test workbook with the `formulas` engine and compare the
Top & Bottom tables against an independently computed ranking."""
import json, formulas, openpyxl

xl = formulas.ExcelModel().loads('mini_calc.xlsx').finish()
sol = xl.calculate()

PREFIX = "'[mini_calc.xlsx]{}'!"
def get(sheet, cell):
    v = sol[PREFIX.format(sheet.upper().replace(' ', '_') if False else sheet.upper()) + cell]
    try:
        return v.value[0, 0]
    except Exception:
        return v

wb = openpyxl.load_workbook('mini_calc.xlsx')
tb = wb['Top & Bottom']
exp = json.load(open('mini_expected.json'))

# locate each block by its title row
blocks = {}
for r in range(1, tb.max_row + 1):
    v = tb.cell(r, 1).value
    if isinstance(v, str) and v.startswith(('USD -', 'EUR -', 'GBP -', 'CHF -')):
        ccy = v[:3]
        kind = 'wide' if 'widened' in v else 'tight'
        blocks[(ccy, kind)] = r + 2          # first data row

fails = 0
for (ccy, kind), first in sorted(blocks.items()):
    want = exp[ccy][kind]
    for i in range(10):
        row = first + i
        isin = get('TOP & BOTTOM', 'A{}'.format(row))
        chg  = get('TOP & BOTTOM', 'K{}'.format(row))   # 11th display column = Spread change
        w_isin, w_chg = want[i]
        ok = (str(isin).strip() == str(w_isin).strip()) and abs(float(chg) - w_chg) < 1e-6
        if not ok:
            fails += 1
            print('MISMATCH', ccy, kind, 'pos', i + 1, '| got', isin, chg, '| want', w_isin, w_chg)
print('checked', len(blocks), 'blocks x 10 rows ->', 'ALL MATCH' if fails == 0 else '{} FAILURES'.format(fails))
