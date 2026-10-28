'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm'), path = require('node:path');
const {createEngine, tokens, LRU} = require('../dist/library-worker.js');
function fixture() {
  const records = Array.from({length: 20}, (_, n) => ({id: n === 0 ? 'legacy-first' : 'cq-' + n.toString(16).padStart(16, '0'), text: ['Café curiosity opens the mind.', 'Courage brings discoveries.', 'Learning starts with curiosity.', 'Friendship and courage.', 'Learning a longer lesson about nature.', 'A short thought.'][n % 6], author: ['Ada', 'Zoe', 'Marie'][n % 3], year: n === 0 ? null : n === 2 ? -20 : 1900 + n, topics: [n % 2 ? 'Courage' : 'Learning'], minAge: n % 3 * 4, importance: n % 5 + 1, likes: null, source: 'A notebook', sourceUrl: 'https://example.com/', verified: false}));
  records[4].topics.push('High bit');
  const topics = [{name:'Learning'}, {name:'Courage'}, ...Array.from({length:31}, (_, n) => ({name:'Unused '+n})), {name:'High bit'}];
  const manifest = {version:2, release:'fixture-v2', total:records.length, authors:3, authorNames:['Ada','Marie','Zoe'], topics, legacyIds:['legacy-first'], aliases:{'removed-old':'legacy-first'}, chunkSize:2, initial:[records[0]], catalog:'catalog.bin'};
  const buffer = new ArrayBuffer(records.length * 32), view = new DataView(buffer), postings = {};
  records.forEach((q,n) => { const hex = n.toString(16).padStart(16,'0'); for(let b=0;b<8;b++) view.setUint8(n*32+b,parseInt(hex.slice(b*2,b*2+2),16)); for(const topic of q.topics) {const i=topics.findIndex(t=>t.name===topic), p=n*32+(i<32?8:12); view.setUint32(p,view.getUint32(p,true)|(1<<(i%32)),true);} view.setUint32(n*32+16,manifest.authorNames.indexOf(q.author),true); view.setUint16(n*32+20,q.text.length,true); view.setInt16(n*32+22,q.year??32767,true); view.setUint8(n*32+24,q.minAge); view.setUint8(n*32+25,q.importance);
    for(const t of tokens([q.text,q.author,...q.topics,q.source,q.year??''].join(' '))) { const prefix=t.slice(0,2); (postings[prefix] ||= {}); (postings[prefix][t] ||= []).push(n); }
  });
  manifest.searchPrefixes=Object.keys(postings);
  const calls=[], fail = new Set();
  async function fetcher(url) { const u=new URL(url), key=u.pathname.split('/data/')[1]; calls.push({key,version:u.searchParams.get('v')}); if(fail.has(key)) return {ok:false}; if(key==='manifest.json')return {ok:true,json:async()=>manifest}; if(key==='catalog.bin')return {ok:true,arrayBuffer:async()=>buffer}; if(key.startsWith('search/')) {const p=key.slice(7,-5);return {ok:!!postings[p],json:async()=>postings[p]};} if(key.startsWith('records/')) {const n=Number(key.slice(8,-5));return {ok:true,json:async()=>records.slice(n*2,n*2+2)};} throw Error('Unexpected URL '+url); }
  return {records, manifest, buffer, postings, fetcher, calls, fail};
}
async function run() {
  const f=fixture(), engine=createEngine({manifest:f.manifest,base:'https://example.com/data/',fetch:f.fetcher});
  assert.deepEqual(tokens(' CÁFÉ, curiosity  a CAFE '),['cafe','curiosity']);
  assert.equal(f.calls.length,0,'catalog loads lazily');
  const initial=await engine.query({pageSize:3}); assert.equal(initial.total,20);assert.deepEqual(initial.refs.map(r=>r.ordinal),[0,1,2]);
  let r=await engine.query({search:'cafe curi'});assert.deepEqual(r.refs.map(q=>q.ordinal),[0,6,12,18]);
  r=await engine.query({search:'curi learn',topic:'Learning',age:8});assert.deepEqual(r.refs.map(q=>q.ordinal),[0,2,6,8,12,14,18]);
  r=await engine.query({topic:'High bit'});assert.equal(r.total,1);assert.equal(r.refs[0].ordinal,4);
  assert.equal((await engine.query({topic:'Absent'})).total,0);
  const before=f.calls.length;r=await engine.query({search:'a'});assert.equal(r.total,0);assert.ok(r.message);assert.equal(f.calls.length,before);
  r=await engine.query({collection:'favorites',favorites:['removed-old',f.records[3].id]});assert.deepEqual(r.refs.map(x=>x.ordinal),[0,3]);
  const own={...f.records[0],id:'own-one',text:'Curiosity courage with café.',author:'Bob',topics:['Courage'],importance:2,likes:500,year:1800};
  assert.equal((await engine.query({collection:'mine',custom:[own]})).refs[0].record.id,'own-one');
  r=await engine.query({sort:'likes',custom:[own]});assert.equal(r.refs[0].record.id,'own-one');
  r=await engine.query({sort:'importance',custom:[own],ratings:{'own-one':5,'removed-old':5},pageSize:2});assert.equal(r.refs[0].record.id,'own-one');assert.equal(r.refs[1].id,'legacy-first');
  r=await engine.query({sort:'oldest',pageSize:1});assert.equal(r.refs[0].ordinal,2);
  r=await engine.query({sort:'short',pageSize:1});assert.equal(r.refs[0].ordinal,5);
  r=await engine.query({sort:'author',custom:[own],pageSize:20});assert.equal(r.refs.findIndex(x=>x.record),7,'Bob follows all seven Ada quotes');
  r=await engine.query({page:999,pageSize:3});assert.equal(r.page,7);assert.equal(r.refs.length,2);
  assert.deepEqual(await engine.resolve(['removed-old',f.records[3].id,'missing']),[{id:'legacy-first',ordinal:0},{id:f.records[3].id,ordinal:3},null]);
  f.fail.add('search/fr.json');await assert.rejects(engine.query({search:'friend'}),/Search could/);f.fail.delete('search/fr.json');assert.equal((await engine.query({search:'friend'})).total,3);
  for(const prefix of f.manifest.searchPrefixes.slice(0,12))await engine.dictionary(prefix);assert.ok(engine.dictionaries.values.size<=8);
  const retry=fixture(), retryEngine=createEngine({manifest:retry.manifest,base:'https://example.com/data/',fetch:retry.fetcher});retry.fail.add('catalog.bin');await assert.rejects(retryEngine.query({}),/catalog/);retry.fail.delete('catalog.bin');assert.equal((await retryEngine.query({})).total,20);
  const lf=fixture(), lv=new DataView(lf.buffer);for(let n=0;n<lf.manifest.total;n++)lv.setUint32(n*32+28,0xffffffff,true);lv.setUint32(28,100,true);lv.setUint32(32+28,5,true);lv.setUint32(3*32+28,100,true);lv.setUint32(4*32+28,0,true);
  // Old catalogs ignore these formerly reserved bytes unless explicitly version-gated.
  const oldLikes=createEngine({manifest:{...lf.manifest,hasLikeCounts:false},base:'https://example.com/data/',fetch:lf.fetcher});assert.deepEqual((await oldLikes.query({sort:'likes',pageSize:5})).refs.map(x=>x.ordinal),[0,1,2,3,4]);
  lf.manifest.hasLikeCounts=true;const likesEngine=createEngine({manifest:lf.manifest,base:'https://example.com/data/',fetch:lf.fetcher});
  r=await likesEngine.query({sort:'likes',pageSize:6});assert.deepEqual(r.refs.map(x=>x.ordinal),[0,3,1,4,2,5],'known counts descending, zero before missing, curated order for ties');
  r=await likesEngine.query({sort:'likes',topic:'Courage',pageSize:3});assert.deepEqual(r.refs.map(x=>x.ordinal),[3,1,5]);
  r=await likesEngine.query({sort:'likes',age:0,pageSize:3});assert.deepEqual(r.refs.map(x=>x.ordinal),[0,3,6]);
  r=await likesEngine.query({sort:'likes',collection:'favorites',favorites:[lf.records[1].id,lf.records[2].id],ratings:{[lf.records[2].id]:5}});assert.deepEqual(r.refs.map(x=>x.ordinal),[1,2]);
  r=await likesEngine.query({sort:'likes',custom:[own],pageSize:3});assert.equal(r.refs[0].record.id,'own-one');assert.deepEqual(r.refs.slice(1).map(x=>x.ordinal),[0,3]);
  r=await likesEngine.query({sort:'likes',custom:[{...own,likes:100}],pageSize:3});assert.equal(r.refs[0].record.id,'own-one');assert.deepEqual(r.refs.slice(1).map(x=>x.ordinal),[0,3]);
  r=await likesEngine.query({collection:'goodreads',sort:'likes',custom:[own]});assert.deepEqual(r.refs.map(x=>x.ordinal),[0,3,1,4],'Goodreads collection includes known zero and excludes unsourced personal likes');
  r=await likesEngine.query({collection:'goodreads',sort:'likes',custom:[{...own,popularity:{source:'Goodreads'}}]});assert.equal(r.refs[0].record.id,'own-one');assert.equal(r.total,5);
  assert.equal((await oldLikes.query({collection:'goodreads'})).total,0,'old catalogs do not infer Goodreads counts from reserved bytes');
  r=await likesEngine.query({sort:'importance',ratings:{[lf.records[2].id]:5},pageSize:1});assert.equal(r.refs[0].ordinal,2,'personal importance overrides remain independent of likes');
  for(const sort of ['curated','author','short','oldest']){const withoutLikes=await oldLikes.query({sort,pageSize:20}),withLikes=await likesEngine.query({sort,pageSize:20});assert.deepEqual(withLikes.refs,withoutLikes.refs,sort+' unaffected by catalog likes');}
  const lru=new LRU(2);lru.set('a',1);lru.set('b',2);lru.get('a');lru.set('c',3);assert.equal(lru.get('b'),undefined);

  const cf=fixture();let workers=0;
  class FakeWorker { constructor(){workers++;this.engine=null;} postMessage({id,type,payload}){const delay=type==='query'&&payload.page===1?8:0;setTimeout(async()=>{try{let result;if(type==='init'){this.engine=createEngine({...payload,fetch:cf.fetcher});result=true;}else result=await this.engine[type](payload);this.onmessage({data:{id,result}});}catch(e){this.onmessage({data:{id,error:e.message}});}},delay);}terminate(){} }
  const context={URL,Map,Set,Promise,Array,Error,Number,Object,String,Worker:FakeWorker,fetch:cf.fetcher,location:{href:'https://example.com/index.html'},document:{currentScript:{src:'https://example.com/library-client.js'}}};context.window=context;vm.createContext(context);vm.runInContext(fs.readFileSync(path.join(__dirname,'../dist/library-client.js'),'utf8'),context);
  const client=new context.CommonplaceLibrary();await client.init();assert.equal(workers,0);assert.equal(client.getCached('removed-old').id,'legacy-first');assert.equal(cf.calls.length,1);
  const concurrent=await Promise.all([client.query({page:1,pageSize:2}),client.query({page:2,pageSize:2})]);assert.equal(workers,1);assert.equal(concurrent[0].items[0].id,'legacy-first');assert.equal(concurrent[1].items[0].id,cf.records[2].id);assert.equal(cf.calls.filter(x=>x.key==='catalog.bin').length,1);
  cf.fail.add('search/fr.json');await assert.rejects(client.query({search:'friend'}),/Search could/);cf.fail.delete('search/fr.json');assert.equal((await client.query({search:'friend'})).total,3);assert.equal(client.pending.size,0);
  const resolved=await client.resolve([cf.records[5].id,'missing','removed-old']);assert.equal(resolved[0].id,cf.records[5].id);assert.equal(resolved[1],null);assert.equal(resolved[2].id,'legacy-first');assert.deepEqual(Array.from(await client.hasIds(['removed-old','missing'])),['missing']);
  cf.fail.add('records/00006.json');await assert.rejects(client.resolve([cf.records[12].id]),/page of quotes/);cf.fail.delete('records/00006.json');assert.equal((await client.resolve([cf.records[12].id]))[0].id,cf.records[12].id);
  await client.resolve(cf.records.map(q=>q.id));assert.equal(client.chunks.values.size,8);assert.ok(cf.calls.filter(x=>x.key!=='manifest.json').every(x=>x.version==='fixture-v2'));
  cf.fail.add('manifest.json');const manifestRetry=new context.CommonplaceLibrary();await assert.rejects(manifestRetry.init(),/could not be opened/);cf.fail.delete('manifest.json');assert.equal((await manifestRetry.init()).total,20);manifestRetry.close();
  client.close();
  console.log('PASS: real metadata worker filters, normalized prefix AND search, high topic bits, aliases, personal ratings, custom quotes, stable paging, indexed Goodreads likes/collection and version guards, bounded LRUs, lazy client, concurrent request IDs, ordered resolves, release URLs, and failed-fetch retries.');
}
run().catch(e=>{console.error(e);process.exitCode=1;});
