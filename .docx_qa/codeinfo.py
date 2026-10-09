import json
from pathlib import Path
for label,path in [('REF', '.docx_qa/reference.json'),('TARGET','.docx_qa/target.json')]:
 d=json.loads(Path(path).read_text(encoding='utf-8').split('\n---END---')[0])
 print('===',label,'CODE & FIGURE PARAGRAPHS===')
 for p in d['paragraphs']:
  if p['text'].startswith('enable') or p['text'].startswith('# SQL') or p['has_drawing']:
   print(p['idx'],p['text'][:80], 'para=',{k:p[k] for k in ['align','left','first','before','after','line']}, 'runs=',[(r['name'],r['eastAsia'],r['ascii'],r['size'],r['bold']) for r in p['runs'][:5]])
 print('===',label,'FONT COUNTS===')
 from collections import Counter
 c=Counter()
 for p in d['paragraphs']:
  for r in p['runs']:
   c[(r['name'],r['eastAsia'],r['ascii'],r['size'],r['bold'])]+=len(r['text'])
 print(c.most_common(15))
