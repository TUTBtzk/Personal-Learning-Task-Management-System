import json
from pathlib import Path
for label,path in [('REF', '.docx_qa/reference.json'),('TARGET','.docx_qa/target.json')]:
 d=json.loads(Path(path).read_text(encoding='utf-8').split('\n---END---')[0])
 print('===',label,'SELECTED PARAGRAPHS===')
 indices=[0,1,2,3,8,19,25,26,27,32,33,34,35,44,51,52,58,59,60,61,62,63,64,65,66,67,68,69,70,71,72,73,74]
 for i in indices:
  if i<len(d['paragraphs']):
   p=d['paragraphs'][i]
   print(json.dumps({k:p[k] for k in ['idx','style','text','align','left','right','first','before','after','line','keep_next','keep_together','has_drawing']},ensure_ascii=False))
 print('===',label,'TABLE CELLS===')
 for t in d['tables'][:4]: print(t)
