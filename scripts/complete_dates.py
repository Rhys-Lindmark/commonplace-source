#!/usr/bin/env python3
"""Source-first dates, followed by explicitly recorded, reproducible estimates."""
import argparse
import collections
import hashlib
import json
import re
import statistics
import struct
import unicodedata
import urllib.parse
from array import array
from pathlib import Path
from audit_dates import classify, date_label, context_dates, parse_expression, tokens, BLOCK, MONTH

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'dist/data'
WORK=ROOT/'work/date-estimates'
YEAR=2026
VERSION=2
CARRIER=re.compile(r'\b(?:as quoted|quoted (?:in|from|by)|as cited|cited in|as reported|reported by|recalled by|remembered by|accessed|retrieved|archived|reprinted|reprinting|translat\w*|edition|antholog\w*|dictionary|familiar quotations|collected (?:works|writings|sayings)|complete works)\b',re.I)
DATE=re.compile(rf'(?:(?:\d{{1,2}}(?:st|nd|rd|th)?\s+)?{MONTH}\s+(?:\d{{1,2}}(?:st|nd|rd|th)?,?\s+)?\d{{4}}|\d{{1,2}}\s+{MONTH},?\s+\d{{4}})',re.I)

def normalize(value):
    return ''.join(c for c in unicodedata.normalize('NFKD',value).casefold() if c.isalnum() and not unicodedata.combining(c))

def midpoint(values):
    values=[int(v) for v in values if v]
    if not values:return None
    value=int(statistics.median(values))
    return value or 1

def years(values, historical=False):
    result=[]
    for value in values or []:
        match=re.match(r'^([+-]?\d{1,5})-',value)
        if match:
            year=int(match[1])
            if year<=0 and not historical:year-=1
            if -10000<=year<=YEAR and year:result.append(year)
    return sorted(set(result))

def cutoff(quote):
    p=quote.get('provenance',{})
    if p.get('dataset')=='QuoteKG v1.2':return 2022
    match=re.match(r'^(20\d\d)',p.get('snapshotDate',''))
    return min(YEAR,int(match[1])) if match else YEAR

def author_facts(quote,authors):
    author=authors.get(normalize(quote['author']),{})
    facts=author.get('facts',[])
    if len(facts)>1:
        title=urllib.parse.unquote(urllib.parse.urlparse(quote.get('provenance',{}).get('wikiquote','')).path.removeprefix('/wiki/')).replace('_',' ')
        entity=next((p.get('entity') for p in author.get('pageMatches',[]) if p.get('requestedTitle')==title),None)
        facts=[f for f in facts if f.get('source','').endswith('/'+str(entity))] if entity else []
    if len(facts)!=1:return {}
    raw=facts[0]
    result={**{key:years(raw.get(key),raw.get('timeNumbering')=='historical') for key in ['birth','death','start','end','floruit','publication','inception']},'sources':[raw['source']],'human':'http://www.wikidata.org/entity/Q5' in raw.get('instance',[])}
    for key in ['birth','death']:
        bounds=raw.get(key+'Bounds')
        if bounds is not None:bounds=[b for b in bounds if b[1]-b[0]<=1000 and b[0]>-10000 and b[1]<=YEAR]
        if bounds is not None:
            result[key+'Bounds']=bounds
            result[key]=[midpoint(pair) for pair in bounds]
    # A coarse, incompatible birth must not erase a well-supported death era.
    birth=midpoint(result['birth']);death=midpoint(result['death'])
    if birth and death and birth>=death:
        bb=result.get('birthBounds');db=result.get('deathBounds')
        if bb and db and min(b[0] for b in bb)<max(d[1] for d in db):
            end=max(d[1] for d in db);start=max(min(b[0] for b in bb),end-60)
            result['birth']=[start];result['death']=[end]
        elif bb:result['birth']=[]
        elif db:result['death']=[]
        else:result['birth']=[]
    birth=midpoint(result['birth']);death=midpoint(result['death'])
    if birth and death and death-birth>150:result['birth']=[]
    return result

def plausible(date,facts):
    a,b=date['startYear'],date['endYear']
    birth=min((p[0] for p in facts.get('birthBounds',[])),default=midpoint(facts.get('birth',[])));death=max((p[1] for p in facts.get('deathBounds',[])),default=midpoint(facts.get('death',[])))
    if birth and b<birth+5:return False
    if death and a>death+20:return False
    if birth and death and a==birth and b==death:return False
    return True

def citation_dates(label):
    """Attestation date in a citation; never a year from the quotation text."""
    text=re.sub(r'https?://\S+','',label)
    text=re.sub(r'\([^()]*(?:accessed|retrieved|archived|archive\.org)[^()]*\)','',text,flags=re.I)
    text=re.sub(r'\b(?:p|pp|page|pages|vol|volume|chapter|ch)\.?\s*\d+(?:\s*[-–]\s*\d+)?','',text,flags=re.I)
    carrier=CARRIER.search(text)
    if carrier:text=text[:carrier.start()]
    if not text.strip():return []
    result=[]
    for expression in re.findall(r'\(([^()]*)\)',text):
        parsed=parse_expression(expression)
        if parsed:result.append((parsed,4,label))
    for match in DATE.finditer(text):
        parsed=parse_expression(match.group(0))
        if parsed:result.append((parsed,5,label))
    # A dated letter/speech/interview takes precedence over a later carrier.
    for match in re.finditer(r'\b(?:written|delivered|spoken|conducted|recorded|dated|letter|speech|interview)\b[^;()]{0,70}?\b((?:1\d{3}|20[0-2]\d))\b',text,re.I):
        year=int(match[1])
        if year<=YEAR:result.append(({'startYear':year,'endYear':year,'approximate':False,'label':str(year)},6,label))
    if not result:
        # Multiple independent years and historic years in titles are ambiguous.
        found=set()
        for match in re.finditer(r'(?<!\d)(1\d{3}|20[0-2]\d)(?!\d)',text):
            if text[match.end():].lstrip().startswith(':'):continue
            if re.search(r'\b(?:born|died|birth|death)\s*[:=]?\s*$',text[:match.start()],re.I):continue
            year=int(match[1])
            if year<=YEAR:found.add(year)
        if len(found)==1:
            year=found.pop();result.append(({'startYear':year,'endYear':year,'approximate':False,'label':str(year)},2,label))
    return result

def from_rule(rule,evidence):
    a=rule['startYear'];b=rule.get('endYear',a)
    date={'version':VERSION,'kind':'work','startYear':a,'endYear':b,'approximate':bool(rule.get('approximate')),'label':rule.get('label') or date_label(a,b,rule.get('approximate',False)),'evidence':rule.get('evidence',evidence)[:900],'sourceUrls':rule.get('sourceUrls',[])[:8],'note':rule.get('basis',rule.get('note','Date of the cited work.'))[:1900],'reviewed':True,'referenceId':rule['id']}
    if rule.get('disputed'):date['disputed']=True
    return date

def source_date(quote,legacy,references,authors,work_dates):
    for rule in references.get('quoteMappings',[]):
        if quote['id'] in rule.get('quoteIds',[]) and re.search(rule['authorPattern'],quote['author'],re.I) and (not rule.get('textPattern') or re.search(rule['textPattern'],quote['text'],re.I)):
            return from_rule(rule,quote.get('source',''))
    p=quote.get('provenance',{})
    labels=[quote.get('source','')]+p.get('descriptions',[])+p.get('citations',[])
    context=' | '.join(labels)
    for rule in references.get('mappings',[]):
        if re.search(rule['authorPattern'],quote['author'],re.I) and re.search(rule['workPattern'],context,re.I):return from_rule(rule,context[:900])
    original=classify(quote,legacy)
    if original.get('reviewed') and original['kind']!='unknown':return {**original,'version':VERSION}
    if original['kind']=='unknown' and original.get('referenceId'):return None
    # Exact linked work+author matches, if the optional bibliographic pass found one.
    for date in work_dates.get(quote['id'],[]):
        
        if -3000<=date['startYear']<=date['endYear']<=cutoff(quote) and date['startYear'] and date['endYear']:return {**date,'version':VERSION}
    facts=author_facts(quote,authors)
    candidates=[]
    if original['kind']!='unknown' and plausible(original,facts):candidates.append((original,4,original.get('evidence','')))
    for label in labels:
        candidates.extend((date,score,evidence) for date,score,evidence in citation_dates(label) if plausible(date,facts))
    if not candidates:return None
    score=max(row[1] for row in candidates);best=[row for row in candidates if row[1]==score]
    if len({(row[0]['startYear'],row[0]['endYear']) for row in best})!=1:return None
    date,_,evidence=best[0]
    return {'version':VERSION,'kind':'source-context','startYear':date['startYear'],'endYear':date['endYear'],'approximate':date.get('approximate',False),'label':date.get('label') or date_label(date['startYear'],date['endYear']),'evidence':evidence[:900],'sourceUrls':[u for u in [quote.get('sourceUrl'),*p.get('citationUrls',[])] if u][:8],'note':'Date stated in the linked source/citation; may describe publication or attestation rather than first utterance.','reviewed':False}

def estimate(quote,authors,activity,prior,references=None):
    facts=author_facts(quote,authors);birth=midpoint(facts.get('birth',[]));death=midpoint(facts.get('death',[]));upper=cutoff(quote);sources=facts.get('sources',[])
    if birth and death and death<birth:birth=death=None
    method='';year=None;confidence='low'
    anchor=next((rule for rule in (references or {}).get('authorEstimates',[]) if re.search(rule['authorPattern'],quote['author'],re.I)),None)
    if anchor:
        year=anchor['year'];method='reviewed-author-era';confidence=anchor.get('confidence','low');note=anchor['basis']+' '+anchor.get('note','');sources=anchor.get('sourceUrls',[])
    elif birth and death and 10<=death-birth<=130:
        # Historical signed years skip zero; one-year BCE/CE adjustment is explicit.
        a=birth+1 if birth<0 else birth;b=death+1 if death<0 else death
        point=round(a+.75*(b-a));year=point-1 if point<=0 else point
        method='author-lifespan-75-percent';confidence='medium' if facts.get('human') else 'low'
        note=f'Estimated at75%of the author lifespan from{birth}to{death}; not a sourced quotation date.'
    elif activity.get(normalize(quote['author'])):
        year=midpoint(activity[normalize(quote['author'])]);method='author-sourced-activity-median';note='Estimated from the median dated work/source contexts for the same attributed author.'
    elif facts.get('start') or facts.get('end') or facts.get('floruit'):
        year=midpoint(facts.get('start',[])+facts.get('end',[])+facts.get('floruit',[]));method='author-work-period';note='Estimated from the attributed author work/activity period in Wikidata.'
    elif birth and birth<=upper:
        year=round(birth+.75*min(80,max(0,upper-birth)));method='author-birth-and-observed-lifespan';note=f'Estimated from birth{birth},75%of elapsed years through corpus cutoff{upper}, capped at60years after birth; not an assumed death date.'
    elif death:
        year=death-20;method='author-death-minus-20';note=f'Estimated20years before death{death}, corresponding to75%of a nominal80year lifespan; no birth year is invented.'
    elif facts.get('publication') or facts.get('inception'):
        year=min(facts.get('publication',[])+facts.get('inception',[]));method='attributed-entity-work-date';note='Estimated from publication/inception of the attributed entity when no human lifespan was available.'
    else:
        year=prior;method='corpus-date-prior';confidence='very-low';note='Low-confidence fallback to the median source-supported corpus date. Author/source dates could not be resolved; not evidence for this quotation.'
    year=max(-3000,min(upper,int(year or prior))) or 1
    if birth and birth<=upper:year=max(year,birth)
    if death and death>=-3000:year=min(year,death)
    year=max(-3000,min(YEAR,year)) or 1
    return {'version':VERSION,'kind':'estimate','startYear':year,'endYear':year,'approximate':True,'label':date_label(year,year),'evidence':method,'sourceUrls':sources[:8],'note':note,'reviewed':False,'method':method,'confidence':confidence,'anchors':{k:v for k,v in {'birthYear':birth,'deathYear':death,'cutoffYear':upper}.items() if v is not None}}

def records():
    for file in sorted((DATA/'records').glob('*.json')):yield file,json.loads(file.read_text())

def complete(apply=False):
    legacy=json.loads((ROOT/'work/date-audit/reference-dates.json').read_text())
    references=json.loads((WORK/'references.json').read_text()) if (WORK/'references.json').exists() else {}
    authors=json.loads((WORK/'authors.json').read_text()) if (WORK/'authors.json').exists() else {}
    if apply and not authors:raise RuntimeError('Fetch author metadata before applying estimates.')
    work_dates=json.loads((WORK/'work-dates.json').read_text()) if (WORK/'work-dates.json').exists() else {}
    manifest=json.loads((DATA/'manifest.json').read_text());catalog=bytearray((DATA/manifest['catalog']).read_bytes());baseline=bytes(catalog)
    activity=collections.defaultdict(list);source_counts=collections.Counter()
    for _,rows in records():
        for quote in rows:
            date=source_date(quote,legacy,references,authors,work_dates)
            if date:activity[normalize(quote['author'])].append(midpoint([date['startYear'],date['endYear']]));source_counts[date['kind']]+=1
    pool=[year for values in activity.values() for year in values];prior=midpoint(pool) or 1900
    audit_id=hashlib.sha256(Path(__file__).read_bytes()+json.dumps([legacy,references,authors,work_dates],sort_keys=True).encode()).hexdigest()[:16]
    seed_rows=json.loads((ROOT/'dist/quotes.json').read_text());seed_ids={q['id'] for q in seed_rows+manifest['initial']};seed={};counts=collections.Counter();methods=collections.Counter();weakest=collections.Counter();examples=collections.defaultdict(list);postings=collections.defaultdict(dict);fingerprint=hashlib.sha256();checksum=hashlib.sha256();ordinal=0
    for file,rows in records():
        for quote in rows:
            untouched={k:v for k,v in quote.items() if k!='chronology'};before=json.dumps(untouched,ensure_ascii=False,sort_keys=True);fingerprint.update(before.encode())
            date=source_date(quote,legacy,references,authors,work_dates) or estimate(quote,authors,activity,prior,references);date['auditId']=audit_id;quote['chronology']=date
            assert -3000<=date['startYear']<=date['endYear']<=YEAR and date['startYear']!=0,(quote['id'],date)
            struct.pack_into('<h',catalog,ordinal*32+22,date['startYear']);counts[date['kind']]+=1;counts['total']+=1;counts['bce']+=date['startYear']<0
            if date['kind']=='estimate':
                methods[date['method']]+=1
                if date['method']=='corpus-date-prior':weakest[quote['author']]+=1
            if len(examples[date.get('method',date['kind'])])<3:examples[date.get('method',date['kind'])].append({'id':quote['id'],'author':quote['author'],'date':date})
            # Rebuild from source fields, rather than accumulating obsolete date tokens.
            searchable=' '.join([quote['text'],quote['author'],*quote['topics'],quote['source'],str(quote.get('year') or ''),date['label'],str(date['startYear']),str(date['endYear'])])
            for token in tokens(searchable):postings[token[:2]].setdefault(token,array('I')).append(ordinal)
            assert json.dumps({k:v for k,v in quote.items() if k!='chronology'},ensure_ascii=False,sort_keys=True)==before
            checksum.update(json.dumps(quote,ensure_ascii=False,sort_keys=True).encode())
            if quote['id'] in seed_ids:seed[quote['id']]=quote
            ordinal+=1
        if apply:file.write_text(json.dumps(rows,ensure_ascii=False,separators=(',',':')))
    assert ordinal==manifest['total']
    for n in range(ordinal):assert baseline[n*32:n*32+22]==catalog[n*32:n*32+22] and baseline[n*32+24:(n+1)*32]==catalog[n*32+24:(n+1)*32]
    report={'version':VERSION,'applied':apply,'counts':dict(counts),'methods':dict(methods),'weakestAuthors':dict(weakest.most_common()),'sourceCounts':dict(source_counts),'corpusPrior':prior,'unchangedContentFingerprint':fingerprint.hexdigest(),'auditId':audit_id,'release':checksum.hexdigest()[:16],'examples':dict(examples),'policy':'Evidence first; estimates explicitly retained internally. Only quote cards display the estimate marker.'}
    if apply:
        (DATA/manifest['catalog']).write_bytes(catalog)
        for prefix,dictionary in sorted(postings.items()):(DATA/'search'/f'{prefix}.json').write_text(json.dumps({token:list(values) for token,values in sorted(dictionary.items())},separators=(',',':')))
        for prefix in set(manifest['searchPrefixes'])-postings.keys():(DATA/'search'/f'{prefix}.json').unlink(missing_ok=True)
        (ROOT/'dist/quotes.json').write_text(json.dumps([seed.get(q['id'],q) for q in seed_rows],ensure_ascii=False,separators=(',',':')))
        manifest.update(release=report['release'],hasChronologyDates=True,dateAuditVersion=VERSION,dateAuditId=audit_id,chronology={'version':VERSION,'audited':ordinal,'dated':ordinal,'sourceDated':counts['work']+counts['source-context'],'estimated':counts['estimate'],'unknown':0,'bce':counts['bce']},searchPrefixes=sorted(postings),initial=[seed.get(q['id'],q) for q in manifest['initial']])
        (DATA/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,separators=(',',':')))
        (WORK/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    report=complete(args.apply);print(json.dumps({k:v for k,v in report.items() if k!='examples'},indent=2))
