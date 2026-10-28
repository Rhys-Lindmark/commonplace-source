import json,re,collections
from pathlib import Path
import urllib.request
for fname in ['quotes','authors']:
 cache=Path('/tmp/commonplace-'+fname+'.json')
 if not cache.exists():
  urllib.request.urlretrieve('https://raw.githubusercontent.com/quotable-io/data/master/data/'+fname+'.json',cache)
raw=json.load(open('/tmp/commonplace-quotes.json'))
authors={a['name']:a for a in json.load(open('/tmp/commonplace-authors.json'))}
patterns={
'Science':r'\b(science|scientific|experiment|discovery|universe|physics|astronom|curiosity)\w*',
'Biology':r'\b(evolution|species|organism|biology|biological|darwin|nature|natural|flower|tree|seed|garden)\w*',
'History':r'\b(history|historical|civilization|past|revolution|democracy|war|peace|politic)\w*',
'Technology':r'\b(technology|computer|software|machine|internet|digital|invention|engineer)\w*',
'Parenting':r'\b(parent|child|children|mother|father|family|upbringing)\w*',
'Habits':r'\b(habit|practice|discipline|routine|effort|persist|persever|daily|work|action)\w*',
'Learning':r'\b(learn|teach|knowledge|education|school|question|understand|wisdom|read|book)\w*',
'Courage':r'\b(courage|brave|fear|risk|doubt|difficult|failure|strength)\w*',
'Friendship':r'\b(friend|kind|love|compassion|generosity|gratitude)\w*',
'Life & meaning':r'\b(life|happiness|purpose|meaning|time|living|dream|hope|joy)\w*'}
seen=set();out=[]
for q in raw:
 text=q['content'].strip();key=re.sub(r'\W','',text.lower())
 if not q['author'] or key in seen:continue
 seen.add(key)
 hay=text+' '+q['author']+' '+' '.join(q['tags'])
 topics=[t for t,p in patterns.items() if re.search(p,hay,re.I)]
 if not topics:topics=['Life & meaning']
 words=re.findall(r'\b\w+\b',text);avg=sum(map(len,words))/max(1,len(words))
 age=5 if len(words)<13 and avg<4.8 else 8 if len(words)<22 and avg<5 else 12 if len(words)<40 else 15
 if re.search(r'\b(death|sex|war|violence|suicide|religion|god|marriage)\b',text,re.I):age=max(age,15)
 if re.search(r'\b(fuck|shit|bitch)\b',text,re.I):age=18
 out.append({'id':q['_id'],'text':text,'author':q['author'],'year':None,'topics':topics,'minAge':age,'importance':3,'likes':None,'source':'Quotable community collection','sourceUrl':'https://github.com/quotable-io/data','verified':False,'authorInfo':authors.get(q['author'],{}).get('description','')})
featured=['er8h8dsPVIc6','r3wAKE9N-Nei','iDSY05hYTVIU','pOAcy5-yW-3','kgypq-6zX6Kb']
for q in out:
 if q['id'] in featured:q['importance']=5
out.sort(key=lambda q: featured.index(q['id']) if q['id'] in featured else 100)
curated=json.loads(Path('data-curated.json').read_text())
out=out[:1]+curated[:1]+out[1:3]+curated[1:]+out[3:]
young={'oPdH3snIjkes','OdjtBvZuDQA','f6PUk-AOBm','1YkUWV_0wT','0KzOsnrddItt','nYm8bumyc0E','GtLeN2MCTvH','4iwVD9jYPBp','Iyw6zzbLWhh','Rq20ZnWwEfZs','trKnEw-ZVY'}
for quote in out:
 if quote['minAge']==5:quote['minAge']=8
 if quote['id'] in young:quote['minAge']=5
Path('dist/quotes.json').write_text(json.dumps(out,ensure_ascii=False,separators=(',',':')))
print('Prepared',len(out),'unique quotes from',len(set(q['author'] for q in out)),'authors')
print('Topics:',dict(collections.Counter(t for q in out for t in q['topics'])))
