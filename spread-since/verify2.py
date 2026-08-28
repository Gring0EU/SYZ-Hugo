"""Check the INDEX/MATCH lookup columns (description, SYZ view, classification,
rating) and the blank-guarding, with the Bloomberg-only columns stripped out."""
import json, formulas, openpyxl
F, L = 7, 110
wb = openpyxl.load_workbook('mini.xlsx')
ws = wb['Spread Monitor']
for r in range(F, L + 1):
    for col in 'BEFGJKLMNOPQRT':          # pure-BDP columns the engine cannot evaluate
        ws[col + str(r)] = None
wb.save('mini_lookup.xlsx')

xl = formulas.ExcelModel().loads('mini_lookup.xlsx').finish()
sol = xl.calculate()
P = "'[mini_lookup.xlsx]SPREAD MONITOR'!"
def g(c):
    v = sol[P + c]
    try:    return v.value[0, 0]
    except Exception: return v

src = openpyxl.load_workbook('mini_lookup.xlsx')
static = {str(src['SYZ_static'].cell(i, 1).value).strip(): i for i in range(2, src['SYZ_static'].max_row + 1)}
descm  = {str(src['Company_desc'].cell(i, 1).value).strip(): src['Company_desc'].cell(i, 2).value
          for i in range(src['Company_desc'].max_row, 1, -1)}      # first match wins -> iterate backwards
bad = 0
checked = 0
for r in range(F, L + 1):
    isin = ws['A' + str(r)].value
    if isin is None:
        for col in 'CDHIS':                                        # blank rows must stay blank
            if g(col + str(r)) not in ('', None):
                print('NOT BLANK', col, r, repr(g(col + str(r)))); bad += 1
        continue
    i = static.get(isin)
    want = {'C': descm.get(isin, src['SYZ_static'].cell(i, 17).value if i else ''),
            'D': src['SYZ_static'].cell(i, 2).value if i else '',
            'H': src['SYZ_static'].cell(i, 20).value if i else '',
            'I': src['SYZ_static'].cell(i, 19).value if i else ''}
    for col, w in want.items():
        got = g(col + str(r))
        checked += 1
        if str(got).strip() != str('' if w is None else w).strip():
            print('MISMATCH', col, r, isin, '| got', repr(got), '| want', repr(w)); bad += 1
print('lookup cells checked:', checked, '->', 'ALL MATCH' if bad == 0 else '{} FAILURES'.format(bad))
