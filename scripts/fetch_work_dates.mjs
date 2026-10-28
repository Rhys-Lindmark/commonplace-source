#!/usr/bin/env node
// Resolve cited work titles; require the catalog's author to be a credited author.
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),work=path.join(root,'work/date-estimates'),cache=path.join(work,'cache');
const input=JSON.parse(fs.readFileSync(path.join(work,'work-input.json'))),authors=JSON.parse(fs.readFileSync(path.join(work,'authors.json'))),agent='CommonplaceDateAudit/1.0 (https://github.com/Rhys-Lindmark/commonplace)';
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
function load(name){const file=path.join(cache,name+'.jsonl');return new Map(fs.existsSync(file)?fs.readFileSync(file,'utf8').trim().split('\n').filter(Boolean).map(line=>{const r=JSON.parse(line);return[r.key,r.value]}):[])}
function save(name,map,key,value){map.set(key,value);fs.appendFileSync(path.join(cache,name+'.jsonl'),JSON.stringify({key,value})+'\n')}
async function request(url){for(let n=0;n<3;n++){let r;try{r=await fetch(url,{headers:{'User-Agent':agent,Accept:'application/json'},signal:AbortSignal.timeout(45000)});const data=await r.json();if(r.ok&&!data.error){await sleep(120);return data}if(![429,500,502,503,504].includes(r.status)&&data.error?.code!=='maxlag')throw Error('HTTP '+r.status)}catch(e){if(n===2)throw e}await sleep(Math.min(30000,Number(r?.headers.get('retry-after')||5)*(n+1)*1000))}throw Error('Request failed after bounded retries')}
function batches(values,max=40){const chunks=[];let b=[];for(const v of values){if(b.length&&(b.length>=max||encodeURIComponent([...b,v].join('|')).length>5500)){chunks.push(b);b=[]}b.push(v)}if(b.length)chunks.push(b);return chunks}
const pages=load('work-pages'),facts=load('work-facts'),pending=Object.keys(input).filter(t=>!pages.has(t)),chunks=batches(pending);
for(let n=0;n<chunks.length;n++){
 const chunk=chunks[n],url=new URL('https://en.wikipedia.org/w/api.php');Object.entries({action:'query',titles:chunk.join('|'),redirects:'1',prop:'pageprops',ppprop:'wikibase_item',format:'json',formatversion:'2',maxlag:'5'}).forEach(([k,v])=>url.searchParams.set(k,v));const data=await request(url.href),links=new Map([...(data.query?.normalized||[]),...(data.query?.redirects||[])].map(r=>[r.from.replaceAll('_',' '),r.to.replaceAll('_',' ')])),found=new Map((data.query?.pages||[]).map(p=>[p.title,p.pageprops?.wikibase_item||null]));
 for(const title of chunk){let t=title.replaceAll('_',' '),seen=new Set();while(links.has(t)&&!seen.has(t)){seen.add(t);t=links.get(t)}save('work-pages',pages,title,{entity:found.get(t)||null,title:t})}
 if(n%10===0||n===chunks.length-1)console.log(JSON.stringify({stage:'work-pages',batch:n+1,batches:chunks.length,cached:pages.size}));
}
const ids=[...new Set([...pages.values()].map(p=>p.entity).filter(Boolean))],groups=batches(ids.filter(id=>!facts.has(id)),100);
for(let n=0;n<groups.length;n++){
 const chunk=groups[n],query='SELECT ?item ?author ?publication ?inception WHERE { VALUES ?item { '+chunk.map(id=>'wd:'+id).join(' ')+' } OPTIONAL { ?item wdt:P50 ?author } OPTIONAL { ?item wdt:P577 ?publication } OPTIONAL { ?item wdt:P571 ?inception } }',data=await request('https://query.wikidata.org/sparql?query='+encodeURIComponent(query)+'&format=json'),rows=new Map(chunk.map(id=>[id,{}]));
 for(const b of data.results?.bindings||[]){const row=rows.get(b.item.value.split('/').pop());if(row)for(const key of ['author','publication','inception'])if(b[key]?.value)(row[key]??=new Set()).add(b[key].value)}
 for(const [id,row] of rows)save('work-facts',facts,id,{...Object.fromEntries(Object.entries(row).map(([k,v])=>[k,[...v].sort()])),source:'https://www.wikidata.org/wiki/'+id,checkedAt:new Date().toISOString()});
 if(n%5===0||n===groups.length-1)console.log(JSON.stringify({stage:'work-facts',batch:n+1,batches:groups.length,cached:facts.size}));
}
const year=v=>Number(/^([+-]?\d+)/.exec(v)?.[1]),result={},candidates=new Map();let matched=0;
for(const [title,quotes] of Object.entries(input)){
 const id=pages.get(title)?.entity,record=facts.get(id);if(!record?.author?.length)continue;
 const dates=(record.publication?.length?record.publication:record.inception||[]).map(year).filter(y=>Number.isInteger(y)&&y>=-3000&&y<=2026&&y!==0);if(!dates.length)continue;const date=Math.min(...dates);
 for(const quote of quotes){const person=authors[quote.author];if(!person?.entities.some(id=>record.author.includes('http://www.wikidata.org/entity/'+id)))continue;const birth=person.facts.flatMap(f=>f.birth||[]).map(year),death=person.facts.flatMap(f=>f.death||[]).map(year);if(birth.length&&date<Math.min(...birth)||death.length&&date>Math.max(...death)+20)continue;
  const value={kind:'source-context',startYear:date,endYear:date,approximate:false,label:date<0?(-date)+' BCE':String(date),evidence:'Cited work: '+title,sourceUrls:[record.source],note:'Earliest listed publication/composition date for the cited work in Wikidata, matched by exact page title and credited author. This does not independently authenticate the quoted wording.',reviewed:false,referenceId:'wikidata-work-'+id};(candidates.get(quote.id)||candidates.set(quote.id,[]).get(quote.id)).push(value);matched++;
 }
}
for(const [id,values] of candidates)if(new Set(values.map(v=>v.startYear)).size===1)result[id]=[values[0]];
fs.writeFileSync(path.join(work,'work-dates.json'),JSON.stringify(result)+'\n');fs.writeFileSync(path.join(work,'work-fetch-report.json'),JSON.stringify({at:new Date().toISOString(),titles:Object.keys(input).length,identifiedWorks:ids.length,authorAndDateMatches:matched,unambiguousQuoteMatches:Object.keys(result).length,policy:'Exact Wikipedia title plus Wikidata credited-author identity; exclude dates outside known author lifetime with20year posthumous-publication allowance.'},null,2)+'\n');console.log(JSON.stringify({status:'complete',titles:Object.keys(input).length,identifiedWorks:ids.length,matchedQuotes:Object.keys(result).length}));
