"""Trace every imported popularity fact to an exact raw dataset record."""
import csv,hashlib,importlib.util,io,json,re,sqlite3,zipfile,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'dist/data';RAW=ROOT/'work/expansion/raw'
spec=importlib.util.spec_from_file_location('base',ROOT/'scripts/import_quotekg.py');base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
want={};files={};coverage=collections.Counter()
for f in sorted((DATA/'records').glob('*.json')):
 rows=json.loads(f.read_text());files[f]=rows
 for q in rows:
  p=q.get('popularity')
  if p and q['likes'] is not None:
   ref=p['sourceUrl'].split('/datasets/')[-1];coverage[ref]+=1;want[(base.norm(q['text']),base.norm(q['author']))]=(q,ref)
checked=set();examples=[]
def verify(text,author,n,ref):
 key=(base.norm(text.replace('\\n','\n').replace('\\r','\r').replace('\\t','\t')),base.norm(author));pair=want.get(key)
 if not pair:return
 q,expected=pair
 if expected!=ref or q['likes']!=n:return
 if q['id'] in checked:return
 q['popularity']['sourceRecordHash']=hashlib.sha256(text.encode()).hexdigest();q['popularity']['recordIdentityNote']='SHA256 of source quote field; not a Goodreads quote ID';checked.add(q['id'])
 if sum(x['source']==ref for x in examples)<8:examples.append({'id':q['id'],'likes':n,'source':ref,'snapshot':q['popularity']['snapshotDate'],'sourceRecordHash':q['popularity']['sourceRecordHash']})
for name,ref in [('goodreads-cc0.zip','souradippal/popular-quotes-from-goodreads'),('goodreads-cc0-2021.zip','abhishekvermasg1/goodreads-quotes')]:
 with zipfile.ZipFile(RAW/name) as z:
  for row in csv.DictReader(io.TextIOWrapper(z.open('quotes.csv'),encoding='utf-8-sig')):
   n=re.sub(r'[^0-9]','',row['likes'])
   if n:verify(row['quote'],row['author'],int(n),ref)
c=sqlite3.connect('file:'+str(RAW/'goodreads.sqlite')+'?mode=ro',uri=True)
for text,author,n in c.execute('SELECT QUOTE,AUTHOR,LIKES FROM QUOTES'):verify(text,author,n,'faellielupe/goodreads-quotes')
assert len(checked)==len(want),(len(checked),len(want))
checksum=hashlib.sha256();initial=[]
for f,rows in files.items():
 f.write_text(json.dumps(rows,ensure_ascii=False,separators=(',',':')))
 if not initial:initial=rows[:10]
 for q in rows:checksum.update(json.dumps(q,sort_keys=True,ensure_ascii=False).encode())
p=DATA/'manifest.json';m=json.loads(p.read_text());m['initial']=initial;m['release']=checksum.hexdigest()[:16];p.write_text(json.dumps(m,ensure_ascii=False,separators=(',',':')))
p=ROOT/'work/expansion/goodreads-report.json';r=json.loads(p.read_text());r['release']=m['release'];r['exactSourceRowsAudited']=len(checked);p.write_text(json.dumps(r,indent=2))
(ROOT/'work/expansion/like-count-audit.json').write_text(json.dumps({'sourceCoverage':dict(coverage),'exactRowsAudited':len(checked),'exampleRecords':examples,'result':'Every published imported count exactly matches one identified raw snapshot row. Distinct punctuation variants may have different source records/counts; recordhash identifies the selected row. Counts are not added.'},indent=2))
print('PASS: all',len(checked),'published counts traced to exact raw dataset records;',dict(coverage))
