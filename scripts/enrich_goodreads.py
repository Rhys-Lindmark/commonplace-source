#!/usr/bin/env python3
"""Import CC0 Goodreads quotes and match factual historical like counts to existing text."""
import ast,bisect,collections,csv,hashlib,html,importlib.util,io,json,re,sqlite3,struct,unicodedata,zipfile
from pathlib import Path
from urllib.parse import quote
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'dist/data';RAW=ROOT/'work/expansion/raw'
spec=importlib.util.spec_from_file_location('base',ROOT/'scripts/import_quotekg.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
CC0='https://creativecommons.org/publicdomain/zero/1.0/'
SOURCES=[('goodreads-cc0-2021.zip','abhishekvermasg1/goodreads-quotes',4,'2021-03-30'),('goodreads-cc0.zip','souradippal/popular-quotes-from-goodreads',1,'2023-07-01')]
points=set(json.loads((ROOT/'work/expansion/print-codepoints.json').read_text()))
def display(s):return re.sub(r'\s+',' ',unicodedata.normalize('NFC',unicodedata.normalize('NFKC',html.unescape(s)))).strip().replace('\u00ad','').replace('\u200b','').replace('\u2060','').replace('\u2011','-').replace('\u2010','-')
def clean(s):
 s=display(s);s=re.sub(r'\s*[―—]\s*$','',s).strip()
 if len(s)>1 and (s[0],s[-1]) in [('“','”'),('"','"'),('‘','’')]:s=s[1:-1].strip()
 return s

def likes(s):
 if s is None:return None
 if isinstance(s,(int,float)):return int(s) if 0<=s<0xffffffff else None
 v=re.sub(r'\s*likes?\s*$','',str(s).strip(),flags=re.I).replace(',','')
 return int(v) if re.fullmatch(r'\d+',v) and int(v)<0xffffffff else None

def make_pop(n,ref,date,author,version=1):return{'source':'Goodreads','likes':n,'snapshotDate':date,'dateMeaning':'Dataset release date; individual observation time unknown','sourceUrl':'https://www.kaggle.com/datasets/'+ref,'datasetVersion':version,'attributedAuthor':author,'retrievedAt':'2026-10-25'}

def update(q,n,pop):
 if n is None:return False
 old=q.get('popularity')
 if old and old.get('snapshotDate','')>pop['snapshotDate']:return False
 q['likes']=n;q['popularity']=pop;return True

def main():
 manifest=json.loads((DATA/'manifest.json').read_text());rows=[]
 baseline=json.loads((ROOT/'work/expansion/import-report.json').read_text())['accepted']
 for f in sorted((DATA/'records').glob('*.json')):rows.extend(json.loads(f.read_text()))
 rows=rows[:baseline]
 for q in rows:q['likes']=None;q.pop('popularity',None)
 by_text={m.norm(q['text']):i for i,q in enumerate(rows)};report=collections.Counter();seen_cc0=set();credits=[]
 for file,ref,version,date in SOURCES:
  if not (RAW/file).exists():raise RuntimeError('Missing pinned Goodreads input: '+file)
  digest=hashlib.sha256((RAW/file).read_bytes()).hexdigest();credits.append({'ref':ref,'version':version,'releaseDate':date,'sha256':digest,'license':CC0})
  with zipfile.ZipFile(RAW/file) as z:
   for x in csv.DictReader(io.TextIOWrapper(z.open('quotes.csv'),encoding='utf-8-sig')):
    report['cc0Rows']+=1;text=clean(x.get('quote',''));author=display(x.get('author',''));n=likes(x.get('likes'));key=m.norm(text)
    if not text or not author or not 20<=len(text)<=1000 or len(author)>150 or any(ord(c) not in points and not c.isspace() for c in text+author):report['cc0ExcludedQualityOrPrint']+=1;continue
    if len(m.tokens(text))<4 or sum(c.isascii() for c in text)/len(text)<.8:report['cc0ExcludedLanguageOrFragment']+=1;continue
    if text.startswith(('“','\"')) or text.endswith('”'):report['cc0ExcludedIncompleteWrapper']+=1;continue
    i=by_text.get(key);pop=make_pop(n,ref,date,author,version)
    if i is None and ref.startswith('abhishekvermasg1/'):
     report['olderExportUnmatchedMetadataOnly']+=1;continue
    if i is not None:
     q=rows[i]
     if m.norm(q['author'])!=m.norm(author):report['cc0AttributionMismatch']+=1;continue
     if update(q,n,pop):report['cc0MatchedExisting']+=1
    else:
     ts=m.topics_for(text);raw_tags=x.get('tags','');tags=[]
     if raw_tags:
      try:
       parsed=ast.literal_eval(raw_tags)
       if isinstance(parsed,list):tags=[str(t) for t in parsed]
      except (ValueError,SyntaxError):tags=[t.strip() for t in raw_tags.split(';') if t.strip()]
     mapping={'inspirational':'Inspiration','inspiration':'Inspiration','motivational':'Motivation','motivation':'Motivation','life':'Life & meaning','life-lessons':'Life lessons','humour':'Humor'}
     by_name={t.casefold():t for t in m.TOPICS}
     for t in tags:
      value=mapping.get(t.casefold()) or by_name.get(t.casefold())
      if value and value not in ts:ts.append(value)
     url='https://www.goodreads.com/quotes/search?q='+quote(author+' '+text[:100])
     q={'id':'cq-'+hashlib.sha256(key.encode()).hexdigest()[:16],'text':text,'author':author,'year':None,'topics':ts,'minAge':m.age_for(text,ts),'importance':3,'likes':n,'source':'Goodreads community quotation','sourceUrl':url,'verified':False,'authorInfo':'','originalTags':tags,'popularity':pop,'provenance':{'dataset':'Goodreads CC0 collection','sourceUrl':'https://www.kaggle.com/datasets/'+ref,'license':CC0,'snapshotDate':date,'retrievedAt':'2026-10-25','attribution':'Goodreads community attribution; not independently verified','datasetVersion':version}}
     rows.append(q);by_text[key]=len(rows)-1;report['cc0NewQuotes']+=1
    seen_cc0.add(rows[by_text[key]]['id'])
 # This source has no explicit compilation license. Import numeric popularity facts only;
 # its quote text/metadata are used transiently as exact matching keys, never added to the corpus.
 con=sqlite3.connect('file:'+str(RAW/'goodreads.sqlite')+'?mode=ro',uri=True)
 for text,author,n in con.execute('SELECT QUOTE,AUTHOR,LIKES FROM QUOTES'):
  report['metadataRows']+=1;key=m.norm(text.replace('\\n','\n').replace('\\r','\r').replace('\\t','\t'));i=by_text.get(key)
  if i is None:continue
  q=rows[i]
  if m.norm(author)!=m.norm(q['author']):report['metadataAttributionMismatch']+=1;continue
  if update(q,likes(n),make_pop(likes(n),'faellielupe/goodreads-quotes','2020-02-22',author)):report['metadataMatched']+=1
 con.close()
 authors=sorted({q['author'] for q in rows},key=lambda s:(s.casefold(),s));ranks={a:i for i,a in enumerate(authors)};counts=collections.Counter();postings=collections.defaultdict(lambda:collections.defaultdict(list));catalog=bytearray();checksum=hashlib.sha256();known=0
 for i,q in enumerate(rows):
  bits=sum(1<<m.TOPICS.index(t) for t in set(q['topics']));counts.update(q['topics']);h=hashlib.sha256(m.norm(q['text']).encode()).digest()[:8];value=q['likes'] if q.get('likes') is not None else 0xffffffff
  catalog+=struct.pack('<8sIIIHhBB2xI',h,bits&0xffffffff,bits>>32,ranks[q['author']],len(q['text']),q['year'] if q['year'] is not None else 32767,q['minAge'],q['importance'],value)
  if value!=0xffffffff:known+=1
  for token in set(m.tokens(q['text']+' '+q['author']+' '+' '.join(q['topics'])+' '+q['source']+' '+str(q.get('year') or ''))):
   if len(token)>=2:postings[token[:2]][token].append(i)
  checksum.update(json.dumps(q,sort_keys=True,ensure_ascii=False).encode())
  if i%200==0:(DATA/'records'/f'{i//200:05}.json').write_text(json.dumps(rows[i:i+200],ensure_ascii=False,separators=(',',':')))
 for file in (DATA/'records').glob('*.json'):
  if int(file.stem)>=(len(rows)+199)//200:file.unlink()
 (DATA/'catalog.bin').write_bytes(catalog)
 for file in (DATA/'search').glob('*.json'):
  if file.stem not in postings:file.unlink()
 for prefix,d in postings.items():(DATA/'search'/f'{prefix}.json').write_text(json.dumps(d,separators=(',',':')))
 manifest.update(release=checksum.hexdigest()[:16],total=len(rows),authors=len(authors),authorNames=authors,topics=[{'name':t,'count':counts[t]} for t in m.TOPICS],initial=rows[:10],hasLikeCounts=True,goodreadsKnownCount=known,goodreadsImportedCount=len(seen_cc0),goodreadsSources=credits,goodreadsMetadataSource={'ref':'faellielupe/goodreads-quotes','version':1,'releaseDate':'2020-02-22','usage':'numeric popularity facts matched by exact normalized text and author only'},source='QuoteKG, original Commonplace collection and CC0 Goodreads quotes',searchPrefixes=sorted(postings))
 (DATA/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,separators=(',',':')))
 license_file=DATA/'LICENSE.txt';license_text=license_file.read_text().split('\nGoodreads source data:')[0].split('\nGoodreads quote-text additions:')[0];license_file.write_text(license_text);
 with open(license_file,'a') as f:f.write('\nGoodreads source data: Abhishek Verma (Kaggle abhishekvermasg1/goodreads-quotes v4,2021-03-30) for matched numeric facts; quote-text additions from Souradip Pal (souradippal/popular-quotes-from-goodreads v1,2023-07-01); providerlabelsCC0. Historicalnumericlikes additionally matched from faellielupe/goodreads-quotes v1,2020-02-22; no new quote text imported from that unlicensed compilation. Datasetrelease dates are not exact observationtimes.\n')
 report=dict(report);report.update(total=len(rows),goodreadsKnownCount=known,goodreadsCC0Unique=len(seen_cc0),authors=len(authors),release=manifest['release']);(ROOT/'work/expansion/goodreads-report.json').write_text(json.dumps(dict(report),indent=2))
 print(json.dumps(dict(report),indent=2),flush=True)
if __name__=='__main__':
 main()
 from complete_dates import complete
 complete(apply=True)
 from build_sections import build_sections
 build_sections()
