# Usage: python3 -I split.py <app.html> <outdir> -- writes rules.json, pdf.js, worker.js, tsn.js
import re, json, sys, os
s = open(sys.argv[1], encoding='utf-8').read(); out = sys.argv[2]
json.dump(json.loads(re.search(r'<script>window\.TS_RULES = (.*?);</script>', s, re.S).group(1)), open(os.path.join(out, 'rules.json'), 'w'), ensure_ascii=False)
scripts = re.findall(r'<script[^>]*>(.*?)</script>', s, re.S)
open(os.path.join(out, 'pdf.js'), 'w').write(next(x for x in scripts if 'pdfjsLib' in x[:20000] and 'WorkerMessageHandler' not in x[-500:] and x.lstrip().startswith('/**')))
open(os.path.join(out, 'worker.js'), 'w').write(next(x for x in scripts if 'WorkerMessageHandler' in x[-500:]))
open(os.path.join(out, 'tsn.js'), 'w').write(next(x for x in scripts if 'const TSN' in x))
