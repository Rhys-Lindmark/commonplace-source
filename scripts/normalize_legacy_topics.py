"""Reindex legacy topic suggestions without touching IDs, quotation text or saved books."""
import bisect,collections,hashlib,importlib.util,json,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('importer',ROOT/'scripts/import_quotekg.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
p=ROOT/'dist/data';manifest=json.loads((p/'manifest.json').read_text());catalog=bytearray((p/'catalog.bin').read_bytes());changes=[];delta=collections.Counter();prefixes={}
for n in range((len(manifest['legacyIds'])+199)//200):
 file=p/'records'/f'{n:05}.json';rows=json.loads(file.read_text())
 for j,q in enumerate(rows):
  i=n*200+j
  if i>=len(manifest['legacyIds']):break
  old=q['topics'];new=list(dict.fromkeys((old if q.get('verified') else [])+m.topics_for(q['text'])))
  if old==new:continue
  common=q['text']+' '+q['author']+' '+q['source']+' '+str(q.get('year') or '')
  before=set(m.tokens(common+' '+' '.join(old)));after=set(m.tokens(common+' '+' '.join(new)))
  for t in before-after:
   if len(t)>=2:prefixes.setdefault(t[:2],[]).append((t,i,False))
  for t in after-before:
   if len(t)>=2:prefixes.setdefault(t[:2],[]).append((t,i,True))
  delta.subtract(old);delta.update(new);q['topics']=new;bits=sum(1<<m.TOPICS.index(t) for t in new);struct.pack_into('<II',catalog,i*32+8,bits&0xffffffff,bits>>32);changes.append(i)
 file.write_text(json.dumps(rows,ensure_ascii=False,separators=(',',':')))
for prefix,updates in prefixes.items():
 file=p/'search'/f'{prefix}.json';d=json.loads(file.read_text()) if file.exists() else {}
 for token,i,add in updates:
  values=d.setdefault(token,[])
  if add:
   pos=bisect.bisect_left(values,i)
   if pos==len(values) or values[pos]!=i:values.insert(pos,i)
  elif i in values:values.remove(i)
  if not values:d.pop(token,None)
 file.write_text(json.dumps(d,separators=(',',':')))
(p/'catalog.bin').write_bytes(catalog);checksum=hashlib.sha256();initial=[]
for file in sorted((p/'records').glob('*.json')):
 rows=json.loads(file.read_text());
 if not initial:initial=rows[:10]
 for q in rows:checksum.update(json.dumps(q,sort_keys=True,ensure_ascii=False).encode())
manifest['release']=checksum.hexdigest()[:16];manifest['initial']=initial
for t in manifest['topics']:t['count']+=delta[t['name']]
manifest['searchPrefixes']=sorted(x.stem for x in (p/'search').glob('*.json'))
(p/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,separators=(',',':')))
rfile=ROOT/'work/expansion/import-report.json';report=json.loads(rfile.read_text());report['release']=manifest['release'];report['topics']={t['name']:t['count'] for t in manifest['topics']};report['legacyTopicReclassifications']=len(changes);rfile.write_text(json.dumps(report,indent=2))
print('Refined legacy topics:',len(changes),'release:',manifest['release'])
