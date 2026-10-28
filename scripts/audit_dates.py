#!/usr/bin/env python3
"""Audit every quote without guessing dates from author lifetimes or dataset timestamps."""
import argparse, collections, hashlib, json, re, struct, unicodedata
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'dist/data'
VERSION=1
CURRENT_YEAR=2026
BLOCK=re.compile(r'\b(?:translat\w*|edition|antholog\w*|compilation|dictionary|familiar quotations|collected (?:works|writings|sayings)|complete works|as quoted|quoted in)\b|\bed\.',re.I)
MONTH=r'(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'

def tokens(value):
    return set(t for t in re.findall(r'[a-z0-9]+',unicodedata.normalize('NFKD',str(value)).encode('ascii','ignore').decode().lower()) if len(t)>=2)

def year_label(y,era=False):
    return f'{-y} BCE' if y<0 else f'{y} CE' if era or y<1000 else str(y)

def date_label(start,end,approx=False,precision=None):
    if precision=='century':
        n=(-start+99)//100 if end<0 else (start-1)//100+1
        suffix='th' if 10<n%100<14 else {1:'st',2:'nd',3:'rd'}.get(n%10,'th')
        return f'{n}{suffix} century '+('BCE' if end<0 else 'CE')
    if precision=='decade':return f'{start}s'
    if start==end:out=year_label(start)
    elif end<0:out=f'{-start}–{-end} BCE'
    elif start>0:out=f'{start}–{end}'+(' CE' if end<1000 else '')
    else:out=f'{year_label(start)}–{year_label(end,True)}'
    return ('c. ' if approx else '')+out

def parse_expression(value):
    s=re.sub(r'\s+',' ',value.strip()).replace('–','-').replace('—','-').replace('−','-')
    s=re.sub(r'^(?:first published|published|written|composed|delivered|released)\s+','',s,flags=re.I)
    approximate=bool(re.match(r'^(?:c\.?|ca\.?|circa|about|approximately)\s*\d|^(?:c\.?|ca\.?|circa|about|approximately)\s+(?:AD|CE|BC|BCE)',s,re.I))
    if approximate:s=re.sub(r'^(?:circa|approximately|about|ca\.?|c\.?)\s*','',s,flags=re.I)
    s=re.sub(r'\bB\.?\s*C\.?\s*E\.?\b','BCE',s,flags=re.I)
    s=re.sub(r'\bB\.?\s*C\.?','BC',s,flags=re.I)
    s=re.sub(r'\bA\.?\s*D\.?','AD',s,flags=re.I)
    s=re.sub(r'\bC\.?\s*E\.?\b','CE',s,flags=re.I)
    s=s.strip().rstrip('.')
    century=re.fullmatch(r'(\d{1,2})(?:st|nd|rd|th) century\s*(BC|BCE|AD|CE)',s,re.I)
    if century:
        n=int(century[1]);era=century[2].upper()
        if not 1<=n<=30:return None
        a,b=(-n*100,-(n-1)*100-1) if era.startswith('BC') else ((n-1)*100+1,n*100)
        if b>CURRENT_YEAR:return None
        return dict(startYear=a,endYear=b,approximate=approximate,precision='century',label=date_label(a,b,approximate,'century'))
    decade=re.fullmatch(r'(\d{3}0)s',s)
    if decade:
        a=int(decade[1])
        if a%100==0 or a+9>CURRENT_YEAR:return None
        return dict(startYear=a,endYear=a+9,approximate=False,precision='decade',label=f'{a}s')
    for pattern in [rf'(?:\d{{1,2}}(?:st|nd|rd|th)?\s+)?{MONTH}\s+(?:\d{{1,2}}(?:st|nd|rd|th)?,?\s+)?(\d{{4}})',rf'\d{{1,2}}\s+{MONTH},?\s+(\d{{4}})']:
        m=re.fullmatch(pattern,s,re.I)
        if m:
            y=int(m[1])
            if 1000<=y<=CURRENT_YEAR:return dict(startYear=y,endYear=y,approximate=False,precision='year',label=str(y))
    m=re.fullmatch(r'(?:(BC|BCE|AD|CE)\s*)?(\d{1,4})(?:\s*(?:-|to|and)\s*(\d{1,4}))?\s*(BC|BCE|AD|CE)?',s,re.I)
    if not m:return None
    prefix,a,b,suffix=m.groups();era=(suffix or prefix or '').upper()
    if prefix and suffix and prefix.upper()!=suffix.upper():return None
    a=int(a);raw_b=b;b=int(b) if b else a
    if not era and (a<1000 or b<1000):
        if raw_b and a>=1000 and len(raw_b)<4:
            scale=10**len(raw_b);b=(a//scale)*scale+b
            if b<a:b+=scale
        else:return None
    if era.startswith('BC'):a,b=-a,-b
    a,b=sorted((a,b))
    if not(-3000<=a<=b<=CURRENT_YEAR) or a==0 or b==0 or b-a>400:return None
    return dict(startYear=a,endYear=b,approximate=approximate,precision='year' if a==b else 'range',label=date_label(a,b,approximate))

def context_dates(label):
    if BLOCK.search(label):return [],'edition-or-compilation-context'
    matches=[]
    for expression in re.findall(r'\(([^()]*)\)',label):
        parsed=parse_expression(expression)
        if parsed:matches.append((parsed,2))
    if not matches:
        parsed=parse_expression(label)
        if parsed:matches.append((parsed,1))
    if not matches and ',' in label:
        parsed=parse_expression(label.rsplit(',',1)[1])
        if parsed:matches.append((parsed,2))
    return matches,None

def unknown(reason,note=None):
    out={'version':VERSION,'kind':'unknown','reason':reason}
    if note:out['note']=note
    return out

def classify(q,references):
    p=q.get('provenance',{})
    labels=[str(x) for x in p.get('descriptions',[]) if x] or [q.get('source','')]
    context=' | '.join(dict.fromkeys([q.get('source','')]+labels))
    for rule in references.get('mappings',[]):
        if re.search(rule['authorPattern'],q['author'],re.I) and re.search(rule['workPattern'],context,re.I):
            if rule.get('startYear') is None:return unknown('reviewed-context-has-no-original-date',rule.get('basis'))
            a,b=rule['startYear'],rule.get('endYear',rule['startYear'])
            out={'version':VERSION,'kind':rule.get('kind','work'),'startYear':a,'endYear':b,'approximate':bool(rule.get('approximate')),'label':rule.get('label') or date_label(a,b,rule.get('approximate',False)),'evidence':context[:600],'sourceUrls':rule.get('sourceUrls',[]),'note':rule.get('basis','Date of the cited work.'),'reviewed':True,'referenceId':rule['id']}
            if rule.get('disputed'):out['disputed']=True
            return out
    if q.get('year') is not None:
        y=q['year']
        return {'version':VERSION,'kind':'work','startYear':y,'endYear':y,'approximate':False,'label':date_label(y,y),'evidence':q.get('source',''),'sourceUrls':[q['sourceUrl']],'note':'Publication date of the original cited work; independently checked seed source.','reviewed':True}
    for block in references.get('blockedContexts',[]):
        if re.search(block.get('authorPattern','.*'),q['author'],re.I) and re.search(block['workPattern'],context,re.I):
            return {**unknown(block.get('reason','reviewed-context-has-no-original-date'),block.get('basis')),'sourceUrls':block.get('sourceUrls',[]),'reviewed':True,'referenceId':block['id']}
    candidates=[];blocked=False
    for label in labels:
        found,reason=context_dates(label)
        blocked=blocked or bool(reason)
        candidates.extend((date,score,label) for date,score in found)
    if not candidates:return unknown('edition-or-compilation-context' if blocked else 'no-unambiguous-source-date')
    score=max(x[1] for x in candidates);strong=[x for x in candidates if x[1]==score]
    keys={(x[0]['startYear'],x[0]['endYear'],x[0]['approximate']) for x in strong}
    if len(keys)!=1:return unknown('conflicting-source-dates')
    date,_,evidence=strong[0]
    return {'version':VERSION,'kind':'source-context',**date,'evidence':evidence[:600],'sourceUrls':[q.get('sourceUrl') or p.get('wikiquote') or p.get('quotation')],'note':'Date explicitly supplied by the source context. It has not been independently confirmed as the original composition or first publication date.','reviewed':False}

def audit(apply=False):
    reference_path=ROOT/'work/date-audit/reference-dates.json'
    references=json.loads(reference_path.read_text()) if reference_path.exists() else {}
    if apply and not references:raise RuntimeError('Finish the reviewed reference mappings before applying.')
    manifest=json.loads((DATA/'manifest.json').read_text());catalog=bytearray((DATA/manifest['catalog']).read_bytes())
    audit_id=hashlib.sha256(Path(__file__).read_bytes()+json.dumps(references,sort_keys=True).encode()).hexdigest()[:16]
    counts=collections.Counter();reasons=collections.Counter();earliest=[];examples=collections.defaultdict(list);extra=collections.defaultdict(lambda:collections.defaultdict(set));seed_ids={q['id'] for q in json.loads((ROOT/'dist/quotes.json').read_text())}|{q['id'] for q in manifest['initial']};seed={};checksum=hashlib.sha256();before=hashlib.sha256();after=hashlib.sha256();ordinal=0
    for file in sorted((DATA/'records').glob('*.json')):
        rows=json.loads(file.read_text())
        for q in rows:
            original={k:v for k,v in q.items() if k!='chronology'};old_json=json.dumps(original,ensure_ascii=False,sort_keys=True);before.update(old_json.encode())
            date=classify(q,references);date['auditId']=audit_id;q['chronology']=date
            after.update(json.dumps({k:v for k,v in q.items() if k!='chronology'},ensure_ascii=False,sort_keys=True).encode());counts['audited']+=1;counts[date['kind']]+=1
            if date['kind']=='unknown':reasons[date['reason']]+=1;sort_year=32767
            else:
                sort_year=date['startYear'];assert -3000<=sort_year<=date['endYear']<=CURRENT_YEAR and sort_year!=0
                if sort_year<0:counts['BCE']+=1
                if date.get('reviewed'):counts['reviewed']+=1
                if date.get('disputed'):counts['disputed']+=1
                for token in tokens(' '.join([date['label'],str(date['startYear']),str(date['endYear'])])):extra[token[:2]][token].add(ordinal)
                earliest.append({'id':q['id'],'author':q['author'],'source':q['source'],'startYear':sort_year,'label':date['label'],'kind':date['kind'],'reviewed':date.get('reviewed',False)})
                earliest=sorted(earliest,key=lambda x:(x['startYear'],x['id']))[:25]
            if len(examples[date['kind']])<5:examples[date['kind']].append({'id':q['id'],'author':q['author'],'date':date})
            struct.pack_into('<h',catalog,ordinal*32+22,sort_year)
            checksum.update(json.dumps(q,sort_keys=True,ensure_ascii=False).encode())
            if q['id'] in seed_ids:seed[q['id']]=q
            ordinal+=1
        if apply:file.write_text(json.dumps(rows,ensure_ascii=False,separators=(',',':')))
    assert counts['audited']==manifest['total']
    assert before.digest()==after.digest(),'Only chronology metadata may change.'
    release=checksum.hexdigest()[:16]
    report={'version':VERSION,'applied':apply,'date':'2026-10-26','counts':dict(counts),'unknownReasons':dict(reasons),'earliest':earliest,'examples':dict(examples),'release':release,'unchangedContentFingerprint':before.hexdigest(),'scope':'All records classified; source-context dates are explicitly unverified. No author lifetimes or dataset timestamps used.'}
    if apply:
        (DATA/manifest['catalog']).write_bytes(catalog)
        for prefix,postings in sorted(extra.items()):
            path=DATA/'search'/f'{prefix}.json';dictionary=json.loads(path.read_text()) if path.exists() else {}
            for token,ordinals in postings.items():dictionary[token]=sorted(set(dictionary.get(token,[]))|ordinals)
            path.write_text(json.dumps(dictionary,separators=(',',':')))
        seed_rows=json.loads((ROOT/'dist/quotes.json').read_text())
        (ROOT/'dist/quotes.json').write_text(json.dumps([seed.get(q['id'],q) for q in seed_rows],ensure_ascii=False,separators=(',',':')))
        manifest.update(release=release,hasChronologyDates=True,dateAuditVersion=VERSION,dateAuditId=audit_id,chronology={'version':VERSION,'audited':counts['audited'],'dated':counts['work']+counts['source-context'],'reviewed':counts['reviewed'],'sourceDated':counts['source-context'],'unknown':counts['unknown'],'bce':counts['BCE']},searchPrefixes=sorted(set(manifest['searchPrefixes'])|set(extra)),initial=[seed.get(q['id'],q) for q in manifest['initial']])
        (DATA/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,separators=(',',':')))
        (ROOT/'work/date-audit/report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    result=audit(args.apply);print(json.dumps({k:v for k,v in result.items() if k!='examples'},ensure_ascii=False,indent=2))
