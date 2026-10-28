#!/usr/bin/env node
// Public Wikimedia metadata only. Sequential, small batches and resumable caches.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),work=path.join(root,'work/date-estimates'),cache=path.join(work,'cache');
fs.mkdirSync(cache,{recursive:true});fs.writeFileSync(path.join(cache,'.gitignore'),'*\n!.gitignore\n');
const input=JSON.parse(fs.readFileSync(path.join(work,'author-input.json'),'utf8')),userAgent='CommonplaceDateAudit/1.0 (https://github.com/Rhys-Lindmark/commonplace)';
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
function load(name){const file=path.join(cache,name+'.jsonl');return new Map(fs.existsSync(file)?fs.readFileSync(file,'utf8').trim().split('\n').filter(Boolean).map(line=>{const r=JSON.parse(line);return[r.key,r.value]}):[])}
function save(name,map,key,value){map.set(key,value);fs.appendFileSync(path.join(cache,name+'.jsonl'),JSON.stringify({key,value})+'\n')}
async function request(url){
 for(let attempt=0;attempt<3;attempt++){
  let response;
  try{response=await fetch(url,{headers:{'User-Agent':userAgent,Accept:'application/json'},signal:AbortSignal.timeout(45000)});const data=await response.json();
   if(response.ok&&!data.error){await pause(120);return data}
   if(![429,500,502,503,504].includes(response.status)&&data.error?.code!=='maxlag')throw Error('HTTP '+response.status+' '+(data.error?.code||''));
  }catch(error){if(attempt===2)throw error}
  await pause(Math.min(30000,Number(response?.headers.get('retry-after')||5)*(attempt+1)*1000));
 }
 throw Error('Wikimedia request failed after bounded retries');
}
function batches(values,max=40){const out=[];let batch=[];for(const value of values){if(batch.length&&(batch.length>=max||encodeURIComponent([...batch,value].join('|')).length>5500)){out.push(batch);batch=[]}batch.push(value)}if(batch.length)out.push(batch);return out}
const normalize=value=>value.replaceAll('_',' '),pages=load('wikiquote-pages'),wiki=load('wikipedia-pages'),facts=load('entity-facts');
async function resolvePages(host,titles,name,map){
 const pending=[...new Set(titles)].filter(t=>!map.has(t)),chunks=batches(pending);
 for(let n=0;n<chunks.length;n++){
  const chunk=chunks[n],url=new URL('https://'+host+'/w/api.php');Object.entries({action:'query',titles:chunk.join('|'),redirects:'1',prop:'pageprops',ppprop:'wikibase_item',format:'json',formatversion:'2',maxlag:'5'}).forEach(([k,v])=>url.searchParams.set(k,v));
  const data=await request(url.href),redirects=new Map([...(data.query?.normalized||[]),...(data.query?.redirects||[])].map(r=>[normalize(r.from),normalize(r.to)])),found=new Map((data.query?.pages||[]).map(p=>[normalize(p.title),p.pageprops?.wikibase_item||null]));
  for(const title of chunk){let canonical=normalize(title),seen=new Set();while(redirects.has(canonical)&&!seen.has(canonical)){seen.add(canonical);canonical=redirects.get(canonical)}save(name,map,title,{entity:found.get(canonical)||null,title:canonical,source:'https://'+host+'/wiki/'+encodeURIComponent(canonical.replaceAll(' ','_')),checkedAt:new Date().toISOString()})}
  if(n%10===0||n===chunks.length-1)console.log(JSON.stringify({stage:name,batch:n+1,batches:chunks.length,cached:map.size}));
 }
}
await resolvePages('en.wikiquote.org',Object.values(input).flatMap(g=>g.pages),'wikiquote-pages',pages);
function entitiesFor(group){return[...new Set(group.pages.map(t=>pages.get(t)?.entity).filter(Boolean))]}
const missing=Object.values(input).filter(g=>!entitiesFor(g).length);
await resolvePages('en.wikipedia.org',missing.map(g=>g.name),'wikipedia-pages',wiki);
const ids=[...new Set(Object.values(input).flatMap(g=>{const exact=entitiesFor(g);return exact.length?exact:[wiki.get(g.name)?.entity].filter(Boolean)}))];
const pending=ids.filter(id=>!facts.has(id)),chunks=batches(pending,100);
const properties={birth:'P569',death:'P570',start:'P2031',end:'P2032',floruit:'P1317',publication:'P577',inception:'P571',instance:'P31'};
for(let n=0;n<chunks.length;n++){
 const chunk=chunks[n],query='SELECT ?person '+Object.keys(properties).map(k=>'?'+k).join(' ')+' WHERE { VALUES ?person { '+chunk.map(id=>'wd:'+id).join(' ')+' } '+Object.entries(properties).map(([k,p])=>'OPTIONAL { ?person wdt:'+p+' ?'+k+' }').join(' ')+' }',url='https://query.wikidata.org/sparql?query='+encodeURIComponent(query)+'&format=json',data=await request(url),rows=new Map(chunk.map(id=>[id,{}]));
 for(const binding of data.results?.bindings||[]){const id=binding.person.value.split('/').pop(),row=rows.get(id);if(!row)continue;for(const key of Object.keys(properties)){const value=binding[key]?.value;if(value)(row[key]??=new Set()).add(value)}}
 for(const [id,row] of rows)save('entity-facts',facts,id,{...Object.fromEntries(Object.entries(row).map(([k,v])=>[k,[...v].sort()])),source:'https://www.wikidata.org/wiki/'+id,checkedAt:new Date().toISOString()});
 if(n%5===0||n===chunks.length-1)console.log(JSON.stringify({stage:'entity-facts',batch:n+1,batches:chunks.length,cached:facts.size}));
}
const result={},counts={authors:0,identified:0,withBirth:0,withDeath:0,withActivity:0,missing:0,ambiguous:0};
for(const [key,group] of Object.entries(input)){
 const exact=entitiesFor(group),entities=exact.length?exact:[wiki.get(group.name)?.entity].filter(Boolean),entityFacts=entities.map(id=>facts.get(id)).filter(Boolean),value={name:group.name,aliases:group.aliases,entities,match:exact.length?'wikiquote-page':entities.length?'wikipedia-page':'unresolved',pageMatches:group.pages.map(title=>({requestedTitle:title,...pages.get(title)})),facts:entityFacts};
 result[key]=value;counts.authors++;counts.identified+=!!entities.length;counts.missing+=!entities.length;counts.ambiguous+=entities.length>1;counts.withBirth+=entityFacts.some(f=>f.birth?.length);counts.withDeath+=entityFacts.some(f=>f.death?.length);counts.withActivity+=entityFacts.some(f=>f.start?.length||f.end?.length||f.floruit?.length);
}
fs.writeFileSync(path.join(work,'authors.json'),JSON.stringify(result)+'\n');fs.writeFileSync(path.join(work,'author-fetch-report.json'),JSON.stringify({counts,at:new Date().toISOString(),requests:'Sequential public MediaWiki pageprops and Wikidata SPARQL; exact page-title matches, no fuzzy name inference.',sources:['https://www.mediawiki.org/wiki/API:Etiquette','https://www.wikidata.org/wiki/Wikidata:Data_access','https://www.wikidata.org/wiki/Property:P569','https://www.wikidata.org/wiki/Property:P570']},null,2)+'\n');console.log(JSON.stringify({status:'complete',counts}));
