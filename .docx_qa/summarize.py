import json
from pathlib import Path
import sys
sys.stdout.reconfigure(encoding='utf-8')
for label,path in [('REF', '.docx_qa/reference.json'),('TARGET','.docx_qa/target.json')]:
 d=json.loads(Path(path).read_text(encoding='utf-8').split('\n---END---')[0])
 print('===',label,'===')
 print('sections',d['sections'])
 print('media',d['media'])
 print('tables',d['tables'])
 print('headers',[(x['linked'],[p['text'] for p in x['paras']]) for x in d['headers']])
 print('footers',[(x['linked'],[p['text'] for p in x['paras']]) for x in d['footers']])
 print('styles')
 for s in d['styles']:
  if s['name'] in ['Normal','正文','Title','Heading 1','Heading 2','Heading 3','Subtitle','Header','Footer'] or s['font_size'] or s['font_name']:
   print(s)
 print('paragraph samples')
 for p in d['paragraphs'][:60]:
  print(p['idx'],p['style'],repr(p['text'][:80]),'align=',p['align'],'fonts=',[(r['name'],r['eastAsia'],r['size'],r['bold']) for r in p['runs'][:3]])
