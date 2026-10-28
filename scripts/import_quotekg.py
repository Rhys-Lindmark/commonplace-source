#!/usr/bin/env python3
"""Bounded-memory QuoteKG v1.2 importer. RDF is staged in SQLite, never a whole graph."""
import argparse,collections,difflib,gzip,hashlib,json,re,sqlite3,struct,time,unicodedata
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit,parse_qsl,urlencode

def sanitize_citation_url(value):
 """Do not redistribute document-access or authentication query parameters."""
 try:
  u=urlsplit(value)
  denied={"access_key","api_key","apikey","token","access_token","auth","authorization","signature","sig"}
  query=[(k,v) for k,v in parse_qsl(u.query,keep_blank_values=True) if k.lower() not in denied and not k.lower().startswith("x-amz-")]
  return urlunsplit((u.scheme,u.netloc,u.path,urlencode(query),u.fragment))
 except ValueError:return ""

ROOT=Path(__file__).resolve().parents[1]
PREFIX='https://quotekg.l3s.uni-hannover.de/resource/'
LICENSE='https://creativecommons.org/licenses/by-sa/4.0/'
TOPICS=['Science','Biology','History','Technology','Parenting','Habits','Learning','Courage','Friendship','Life & meaning','Love','Inspiration','Humor','Philosophy','God','Wisdom','Romance','Truth','Poetry','Life lessons','Death','Happiness','Hope','Faith','Relationships','Spirituality','Motivation','Religion','Writing','Success','Time','Politics','Art','Nature']
PATTERNS={
'Science':r'\b(scien\w*|experiment\w*|discover\w*|physics|astronom\w*|universe|evidence|hypothesis|quantum|mathematics)\b',
'Biology':r'\b(biolog\w*|evolution\w*|species|organism\w*|genetic\w*|cellular|bacteria|ecosystem\w*|biodiversity|botany|zoology|natural selection)\b',
'History':r'\b(history|historical|civilization\w*|antiquity|renaissance|revolution\w*|empire\w*|centuries)\b',
'Technology':r'\b(technolog\w*|computer\w*|software|internet|digital|engineer\w*|invention\w*|artificial intelligence|machine\w*|robot\w*)\b',
'Parenting':r'\b(parent\w*|child\w*|mother\w*|father\w*|family|families|upbringing|infant\w*|toddler\w*)\b',
'Habits':r'\b(habit\w*|practice\w*|discipline|routine\w*|persist\w*|persever\w*|daily|effort\w*)\b',
'Learning':r'\b(learn\w*|teach\w*|knowledge|education|school\w*|question\w*|understand\w*|student\w*|reading)\b',
'Courage':r'\b(courage\w*|brav\w*|fear\w*|risk\w*|doubt\w*|adversity|resilien\w*)\b',
'Friendship':r'\b(friend\w*|companion\w*|kindness|compassion|generosity|gratitude)\b',
'Life & meaning':r'\b(life|living|purpose|meaning|existence|humanity|mortal\w*)\b',
'Love':r'\b(love\w*|loving|beloved|affection\w*)\b','Inspiration':r'\b(inspir\w*|imagin\w*|dream\w*|possibilit\w*|vision\w*)\b',
'Humor':r'\b(humou?r\w*|laugh\w*|joke\w*|funny|comedy|comic\w*|irony|satir\w*)\b',
'Philosophy':r'\b(philosoph\w*|metaphysic\w*|ethic\w*|morality|logic|reason|consciousness|rational\w*)\b',
'God':r'\b(god|gods|divine|deity|deities|almighty|creator)\b',
'Wisdom':r'\b(wisdom|wise|virtue\w*|prudence|judgment|discern\w*)\b',
'Romance':r'\b(romance|romantic\w*|lover\w*|kiss\w*|sweetheart|courtship|passion\w*)\b',
'Truth':r'\b(truth\w*|honest\w*|falsehood\w*|deceit|sincer\w*|lie|lies|lying)\b',
'Poetry':r'\b(poet\w*|verse|rhyme\w*|stanza\w*|lyric\w*)\b',
'Life lessons':r'\b(experience\w*|mistake\w*|lesson\w*|regret\w*|matur\w*|forgiv\w*)\b',
'Death':r'\b(death|dying|dead|die|dies|mortality|grief|funeral|grave\w*|bereave\w*)\b',
'Happiness':r'\b(happi\w*|joy\w*|delight\w*|contentment|cheer\w*)\b',
'Hope':r'\b(hope\w*|optimis\w*|tomorrow|future)\b','Faith':r'\b(faith\w*|belie\w*|trust\w*)\b',
'Relationships':r'\b(relationship\w*|marriage|married|husband\w*|wife|wives|partner\w*|divorce)\b',
'Spirituality':r'\b(spirit\w*|soul\w*|meditat\w*|mindful\w*|enlighten\w*|transcend\w*)\b',
'Motivation':r'\b(motivat\w*|goal\w*|ambition\w*|striv\w*|determination|achiev\w*|willpower|encourag\w*)\b',
'Religion':r'\b(religio\w*|church\w*|christ\w*|buddh\w*|hindu\w*|islam\w*|muslim\w*|jew\w*|judaism|sacred|prayer\w*|worship\w*)\b',
'Writing':r'\b(writ\w*|author\w*|literatur\w*|novel\w*|book\w*|story|stories|storytell\w*)\b',
'Success':r'\b(success\w*|succeed\w*|failure\w*|winning|victory|accomplish\w*)\b',
'Time':r'\b(time|moment\w*|etern\w*|yesterday|clock\w*|hour\w*|minute\w*|patience)\b',
'Politics':r'\b(politic\w*|democra\w*|government\w*|liberty|freedom|justice|war|peace|nation\w*|citizen\w*)\b',
'Art':r'\b(art|artist\w*|paint\w*|music\w*|beauty|beautiful|sculpt\w*|creativ\w*|theatre|theater)\b',
'Nature':r'\b(nature|natural|forest\w*|tree\w*|flower\w*|garden\w*|ocean\w*|mountain\w*|river\w*|animal\w*|earth|wilder\w*)\b'}
COMPILED={k:re.compile(v,re.I) for k,v in PATTERNS.items()}
# Tokenizer for the fixed rdflib Turtle serialization; strings are handled before punctuation.
TOKEN=re.compile(r'"""(?:[^"\\]|\\.|"(?!""))*"""|\'\'\'(?:[^\'\\]|\\.|\'(?!\'\'))*\'\'\'|"(?:[^"\\\r\n]|\\.)*"|\'(?:[^\'\\\r\n]|\\.)*\'|<[^>]*>|@[a-zA-Z-]+|\^\^|[A-Za-z_][\w-]*:[^\s;,\[\]()]+|\b(?:a|true|false)\b|[;,\[\]()]|\.(?=\s|$)',re.S)
ESC=re.compile(r'\\(u[0-9a-fA-F]{4}|U[0-9a-fA-F]{8}|[tbnrf"\'\\])')
ESCAPES={'t':'\t','b':'\b','n':'\n','r':'\r','f':'\f','"':'"',"'":"'",'\\':'\\'}
def literal(s):
 n=3 if s.startswith(('"""',"'''")) else 1
 return ESC.sub(lambda m:chr(int(m[1][1:],16)) if m[1][0] in 'uU' else ESCAPES[m[1]],s[n:-n])
def parse(block):
 ts=TOKEN.findall(block); subject=ts[0]; props=collections.defaultdict(list);i=1
 while i<len(ts):
  if ts[i] in [';', '.']:i+=1;continue
  pred=ts[i];i+=1
  while i<len(ts):
   token=ts[i];i+=1
   if token in [';', '.']:break
   if token==',':continue
   lang=''
   if token.startswith(('"',"'")):value=literal(token);kind='literal'
   elif token.startswith('<'):value=token[1:-1];kind='iri'
   else:value=token;kind='id'
   if i<len(ts) and ts[i].startswith('@'):lang=ts[i][1:];i+=1
   if i<len(ts) and ts[i]=='^^':i+=2
   props[pred].append((value,lang,kind))
   if i<len(ts) and ts[i] in [';', '.']:i+=1;break
 return subject,props
START=re.compile(r'^qkg:(?:Person|Quotation|Mention|Context)\w*\s+a\s')
def blocks(file):
 lines=[]
 with open(file,encoding='utf8') as f:
  for line in f:
   if START.match(line):
    if lines:yield ''.join(lines)
    lines=[line]
   elif lines:lines.append(line)
  if lines:yield ''.join(lines)
def first(p,key,lang=None):
 return next((v for v,l,k in p.get(key,[]) if lang is None or l==lang),'')
def values(p,key):return [v for v,l,k in p.get(key,[])]
def stage(raw,db):
 con=sqlite3.connect(db);con.executescript('PRAGMA journal_mode=OFF;PRAGMA synchronous=OFF;PRAGMA cache_size=-12000;CREATE TABLE people(id TEXT PRIMARY KEY,name TEXT,wiki TEXT);CREATE TABLE contexts(id TEXT PRIMARY KEY,text TEXT,source TEXT);CREATE TABLE mentions(id TEXT PRIMARY KEY,text TEXT,page TEXT,contexts TEXT,description TEXT);CREATE TABLE quotations(id TEXT PRIMARY KEY,person TEXT,mentions TEXT,misattributed INTEGER);')
 stats=collections.Counter();started=time.monotonic()
 for block in blocks(raw):
  sid,p=parse(block);typ=sid[4:].rstrip('0123456789');stats[typ]+=1
  if typ=='Person':
   name=first(p,'skos:prefLabel') or first(p,'rdfs:label','en');wiki=next((v for v in values(p,'owl:sameAs') if v.startswith('https://en.wikiquote.org/wiki/')),'')
   con.execute('INSERT INTO people VALUES(?,?,?)',(sid,name,wiki))
  elif typ=='Context':
   text=first(p,'qkg:contextText','en');src=first(p,'so:source') or first(p,'dcterms:source')
   if text or src:con.execute('INSERT INTO contexts VALUES(?,?,?)',(sid,text,src))
  elif typ=='Mention':
   text=first(p,'so:text','en')
   if text:con.execute('INSERT INTO mentions VALUES(?,?,?,?,?)',(sid,text,first(p,'so:isPartOf'),json.dumps(values(p,'qkg:hasContext')),json.dumps([v for v,l,k in p.get('so:description',[]) if l in ('en','')])))
  elif typ=='Quotation':
   mis=first(p,'qkg:isMisattributed');person=first(p,'so:spokenByCharacter')
   if mis=='false' and person:con.execute('INSERT INTO quotations VALUES(?,?,?,0)',(sid,person,json.dumps(values(p,'qkg:hasMention'))))
  if sum(stats.values())%50000==0:con.commit();print('Staged',dict(stats),'seconds',round(time.monotonic()-started),flush=True)
 con.commit();print('Staging complete',dict(stats),'seconds',round(time.monotonic()-started),flush=True);return con,stats

def norm(s):return ''.join(c for c in unicodedata.normalize('NFKD',s).casefold() if c.isalnum() and not unicodedata.combining(c))
def tokens(s):return re.findall('[a-z0-9]+',''.join(c for c in unicodedata.normalize('NFKD',s.lower()) if not unicodedata.combining(c)))
def topics_for(text):return [k for k,v in COMPILED.items() if v.search(text)] or ['Life & meaning']
def age_for(text,topics):
 words=tokens(text);age=12 if len(words)<=35 else 15
 if any(t in topics for t in ['Death','Politics','Religion','Romance']):age=max(age,15)
 if re.search(r'\b(fuck\w*|shit|bitch\w*|sex\w*|suicid\w*|rape\w*|torture|porn\w*)\b',text,re.I):age=18
 return age

def build(con,target,out,reuse_eligible=False):
 started=time.monotonic();seed=json.loads((ROOT/'dist/quotes.json').read_text());accepted=[];seen={};aliases={};dups=collections.Counter();near={};conflicts=[];rejected=collections.Counter();source_rows=0
 print_points=set(json.loads((ROOT/'work/expansion/print-codepoints.json').read_text()))
 def display(s):
  return unicodedata.normalize('NFC',unicodedata.normalize('NFKC',s)).replace('\u00ad','').replace('\u200b','').replace('\u2060','').replace('\u2011','-').replace('\u2010','-')
 def printable(s):return all(ord(c) in print_points or c.isspace() for c in s)
 def accept(q,legacy=False):
  key=norm(q['text']); prev=seen.get(key)
  if prev is not None:
   old=accepted[prev];dups['exact']+=1
   if legacy and q['id']!=old['id']:aliases[q['id']]=old['id']
   if norm(q['author'])!=norm(old['author']):
    old.setdefault('alternateAttributions',[])
    if len(old['alternateAttributions'])<5:old['alternateAttributions'].append({'author':q['author'],'sourceUrl':q['sourceUrl']})
    conflicts.append({'canonical':old['id'],'author':q['author'],'sourceUrl':q['sourceUrl']})
   if q.get('provenance'):
    old.setdefault('additionalSources',[])
    if len(old['additionalSources'])<3:old['additionalSources'].append(q['provenance'])
   return False
  words=tokens(q['text']);near_keys=[]
  if len(words)>=12 and not legacy:
   near_keys=[norm(q['author'])+'|'+','.join(words[:8]),norm(q['author'])+'|'+','.join(words[-8:])]
   for candidate in set(i for k in near_keys for i in near.get(k,[])):
    other=accepted[candidate]
    if abs(len(other['text'])-len(q['text']))/max(len(q['text']),1)>.06:continue
    if difflib.SequenceMatcher(None,other['text'].casefold(),q['text'].casefold(),autojunk=False).ratio()>=.97:
     other.setdefault('variants',[])
     if len(other['variants'])<3:other['variants'].append({'text':q['text'],'sourceUrl':q['sourceUrl']})
     dups['near']+=1;seen[key]=candidate;return False
  idx=len(accepted);seen[key]=idx;accepted.append(q)
  for k in near_keys:near.setdefault(k,[]).append(idx)
  return True
 for q in seed:
  q=dict(q);q['topics']=list(dict.fromkeys((q['topics'] if q.get('verified') else [])+topics_for(q['text'])));q['originalTags']=[];q['provenance']={'dataset':'Commonplace seed / Quotable' if not q.get('verified') else 'Source-checked public-domain passage','sourceUrl':q['sourceUrl'],'attribution':'source-checked' if q.get('verified') else 'community-unverified'};accept(q,True)
 legacy_ids=[q['id'] for q in accepted];legacy_count=len(accepted)
 # Round-robin authors: broad representation before selecting additional quotations per author.
 if not reuse_eligible:
  con.executescript('DROP TABLE IF EXISTS eligible;CREATE TABLE IF NOT EXISTS eligible(qid TEXT,person TEXT,mid TEXT,text TEXT,page TEXT,contexts TEXT,description TEXT);CREATE INDEX IF NOT EXISTS eligible_person ON eligible(person);')
  for qid,person,mids in con.execute('SELECT id,person,mentions FROM quotations ORDER BY id'):
   for mid in sorted(json.loads(mids)):
    row=con.execute('SELECT text,page,contexts,description FROM mentions WHERE id=?',(mid,)).fetchone()
    if not row:continue
    text,page,cids,description=row;text=re.sub(r'\s+',' ',text).strip();source_rows+=1
    if not 20<=len(text)<=1000:rejected['length']+=1;continue
    if len(tokens(text))<4 or sum(c.isascii() for c in text)/len(text)<.8:rejected['language_or_fragment']+=1;continue
    if re.search(r'\[\[|\{\{|(?:^|\s)(?:w:|s:|File:)',text):rejected['residual_markup']+=1;continue
    con.execute('INSERT INTO eligible VALUES(?,?,?,?,?,?,?)',(qid,person,mid,text,page,cids,description));break
  con.commit()
 rows=con.execute('SELECT e.qid,e.mid,e.text,e.page,e.contexts,e.description,p.name,p.wiki FROM (SELECT *,ROW_NUMBER() OVER(PARTITION BY person ORDER BY qid) AS rn FROM eligible) e JOIN people p ON e.person=p.id ORDER BY e.rn,e.qid')
 for qid,mid,text,page,cids,description,author,wiki in rows:
  if len(accepted)>=target:break
  if not author or len(author)>150:rejected['author']+=1;continue
  text=display(text);author=display(author)
  if not printable(text+author):rejected['unsupported_print_glyphs']+=1;continue
  desc=json.loads(description);citations=[];links=[]
  for cid in json.loads(cids):
   r=con.execute('SELECT text,source FROM contexts WHERE id=?',(cid,)).fetchone()
   if r:
    if r[0]:citations.append(r[0])
    if r[1]:links.append(sanitize_citation_url(r[1]))
  source=display('; '.join(desc)[:250]) or 'Wikiquote via QuoteKG'
  if not printable(source):source='Wikiquote via QuoteKG'
  digest=hashlib.sha256(norm(text).encode()).hexdigest()[:16];ts=topics_for(text)
  q={'id':'cq-'+digest,'text':text,'author':author,'year':None,'topics':ts,'minAge':age_for(text,ts),'importance':3,'likes':None,'source':source,'sourceUrl':page or wiki or PREFIX+qid[4:],'verified':False,'authorInfo':'','originalTags':[],
   'provenance':{'dataset':'QuoteKG v1.2','quotation':PREFIX+qid[4:],'mention':PREFIX+mid[4:],'wikiquote':page or wiki,'citations':citations[:3],'citationUrls':links[:3],'descriptions':desc,'license':LICENSE,'retrievedAt':'2026-10-25','attribution':'source-linked; not independently verified','isMisattributed':False}}
  accept(q)
 if reuse_eligible and (ROOT/'work/expansion/source-filter-report.json').exists():
  prior=json.loads((ROOT/'work/expansion/source-filter-report.json').read_text());source_rows=prior.get('sourceMentionCandidates',source_rows);rejected.update(prior.get('rejected',{}))
 elif not reuse_eligible:
  (ROOT/'work/expansion/source-filter-report.json').write_text(json.dumps({'sourceMentionCandidates':source_rows,'eligibleQuotationRows':con.execute('SELECT COUNT(*) FROM eligible').fetchone()[0],'rejected':dict(rejected)},indent=2))
 if len(accepted)<target:raise RuntimeError(f'Only {len(accepted)} accepted; target {target}')
 out.mkdir(parents=True,exist_ok=True);(out/'records').mkdir(exist_ok=True);(out/'search').mkdir(exist_ok=True)
 authors=sorted({q['author'] for q in accepted},key=lambda s:(s.casefold(),s));author_ranks={s:i for i,s in enumerate(authors)};counter=collections.Counter();postings=collections.defaultdict(lambda:collections.defaultdict(list));catalog=bytearray();checksum=hashlib.sha256()
 for i,q in enumerate(accepted):
  bits=sum(1<<TOPICS.index(t) for t in set(q['topics']));counter.update(q['topics']);h=hashlib.sha256(norm(q['text']).encode()).digest()[:8]
  catalog+=struct.pack('<8sIIIHhBB6x',h,bits&0xffffffff,bits>>32,author_ranks[q['author']],len(q['text']),q['year'] if q['year'] is not None else 32767,q['minAge'],q['importance'])
  searchable=q['text']+' '+q['author']+' '+' '.join(q['topics'])+' '+q['source']+' '+str(q.get('year') or '')
  for token in set(tokens(searchable)):
   if len(token)>=2:postings[token[:2]][token].append(i)
  checksum.update(json.dumps(q,sort_keys=True,ensure_ascii=False).encode())
  if i%200==0:
   chunk=accepted[i:i+200];(out/'records'/f'{i//200:05}.json').write_text(json.dumps(chunk,ensure_ascii=False,separators=(',',':')))
 (out/'catalog.bin').write_bytes(catalog)
 for prefix,data in sorted(postings.items()):(out/'search'/f'{prefix}.json').write_text(json.dumps(data,separators=(',',':')))
 release=checksum.hexdigest()[:16]
 manifest={'version':2,'release':release,'total':len(accepted),'authors':len(authors),'authorNames':authors,'topics':[{'name':t,'count':counter[t]} for t in TOPICS],'legacyIds':legacy_ids,'aliases':aliases,'chunkSize':200,'searchPrefixes':sorted(postings),'initial':accepted[:10],'catalog':'catalog.bin','source':'QuoteKG v1.2 + existing Commonplace seed','sourceUrl':'https://zenodo.org/records/6385077','license':LICENSE,'attribution':'QuoteKG: Tin Kuculo, Simon Gottschalk, Elena Demidova; Wikiquote contributors. Normalized, filtered, deduplicated, categorized and indexed by Commonplace.','generatedAt':'2026-10-25'}
 (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,separators=(',',':')))
 (out/'LICENSE.txt').write_text('QuoteKG v1.2 by Tin Kuculo, Simon Gottschalk and Elena Demidova, derived from Wikiquote contributors. DOI:10.5281/zenodo.6385077. https://quotekg.l3s.uni-hannover.de/\nCompilation/extract: CC BY-SA 4.0 https://creativecommons.org/licenses/by-sa/4.0/\nModifications: English filtering, normalized whitespace/formatting controls, exact and near-duplicate consolidation, author balancing, suggested topics/ages, pagination and search indexes. Original quotations remain their authors’ words. The compilation license does not establish rights in every underlying quoted work. Existing Quotable/source-checked seed records retain their original provenance.\n')
 snapshot=ROOT/'work/expansion/accepted-quotes.jsonl.gz'
 with gzip.open(snapshot,'wt',encoding='utf8',compresslevel=6) as f:
  for q in accepted:f.write(json.dumps(q,ensure_ascii=False,separators=(',',':'))+'\n')
 report={'accepted':len(accepted),'legacy':legacy_count,'new':len(accepted)-legacy_count,'authors':len(authors),'sourceMentionCandidates':source_rows if source_rows else None,'eligibleQuotationRows':con.execute('SELECT COUNT(*) FROM eligible').fetchone()[0],'duplicates':dict(dups),'alternateAttributionMatches':len(conflicts),'rejected':dict(rejected),'topics':dict(counter),'aliases':aliases,'release':release,'catalogBytes':len(catalog),'searchShards':len(postings),'recordChunks':(len(accepted)+199)//200,'buildSeconds':round(time.monotonic()-started,2),'sourceVersion':'QuoteKG v1.2','sourceMD5':'57f28b3944c275529de9bd1c790b816e'}
 (ROOT/'work/expansion/import-report.json').write_text(json.dumps(report,indent=2));(ROOT/'work/expansion/attribution-review.json').write_text(json.dumps(conflicts[:1000],ensure_ascii=False,indent=2))
 print(json.dumps(report,indent=2),flush=True)
 return report

def main():
 p=argparse.ArgumentParser();p.add_argument('--raw',type=Path,default=ROOT/'work/expansion/raw/quotekg.ttl');p.add_argument('--db',type=Path,default=ROOT/'work/expansion/staging.sqlite');p.add_argument('--target',type=int,default=100000);p.add_argument('--reuse-staging',action='store_true');args=p.parse_args()
 if args.reuse_staging:con=sqlite3.connect(args.db)
 else:
  md5=hashlib.md5()
  with open(args.raw,'rb') as f:
   for chunk in iter(lambda:f.read(1024*1024),b''):md5.update(chunk)
  if md5.hexdigest()!='57f28b3944c275529de9bd1c790b816e':raise RuntimeError('Archive checksum mismatch; refuse import.')
  con,_=stage(args.raw,args.db)
 build(con,args.target,ROOT/'dist/data',reuse_eligible=args.reuse_staging)
if __name__=='__main__':
 main()
 from complete_dates import complete
 complete(apply=True)
 from build_sections import build_sections
 build_sections()
