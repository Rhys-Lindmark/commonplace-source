'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {createEngine}=require('../dist/library-worker.js');
const root=path.resolve('dist/data'),manifest=JSON.parse(fs.readFileSync(root+'/manifest.json')),buffer=fs.readFileSync(root+'/catalog.bin'),view=new DataView(buffer.buffer,buffer.byteOffset,buffer.byteLength),calls=[],fail=new Set();
async function fetcher(url){const key=new URL(url).pathname.split('/data/')[1];calls.push(key);if(fail.has(key))return{ok:false};const b=fs.readFileSync(root+'/'+key);return{ok:true,json:async()=>JSON.parse(b),arrayBuffer:async()=>b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength)}}
const engine=createEngine({manifest,base:'https://example.com/data/',fetch:fetcher});
(async()=>{
 assert.equal(calls.length,0);assert.equal(manifest.sectionLimit,10000);assert.equal(manifest.browseGroups.length,4);
 const leaves=[],all=new Map();
 for(const group of manifest.browseGroups){const topicIndex=manifest.topics.findIndex(t=>t.name===group.topic),seen=new Set();
  for(const section of group.sections){const ords=JSON.parse(fs.readFileSync(root+'/'+section.file));assert.equal(ords.length,section.count);assert.ok(ords.length>0&&ords.length<=10000);for(let i=0;i<ords.length;i++){const n=ords[i];assert.ok(n>=0&&n<manifest.total);assert.ok(i===0||n>ords[i-1]);assert.ok(!seen.has(n),'No duplicate quote inside parent group');seen.add(n);assert.ok(view.getUint32(n*32+(topicIndex<32?8:12),true)&(1<<(topicIndex%32)),'Every member belongs to its parent topic')}all.set(section.id,new Set(ords));leaves.push({group,section});}
  assert.equal(seen.size,manifest.topics[topicIndex].count);for(let n=0;n<manifest.total;n++)assert.equal(seen.has(n),!!(view.getUint32(n*32+(topicIndex<32?8:12),true)&(1<<(topicIndex%32))),'Exact parent coverage');
 }
 for(const topic of manifest.topics)if(!manifest.browseGroups.some(g=>g.topic===topic.name))assert.ok(topic.count<=10000);
 for(const {group,section} of leaves){const r=await engine.query({topic:group.topic,section:section.id,pageSize:100,sort:'likes'});assert.equal(r.total,section.count);assert.ok(r.refs.every(ref=>all.get(section.id).has(ref.ordinal)));const last=await engine.query({topic:group.topic,section:section.id,pageSize:100,page:Math.ceil(section.count/100)});assert.equal(last.refs.length,(section.count-1)%100+1)}
 assert.ok(engine.sectionCache.values.size<=8,'Bound section cache');
 const {group,section}=leaves.find(x=>x.section.name==='Purpose & values'),options={topic:group.topic,section:section.id};
 let r=await engine.query({...options,search:'purpose',age:15,pageSize:100});assert.ok(r.total>0);assert.ok(r.refs.every(ref=>all.get(section.id).has(ref.ordinal)&&view.getUint8(ref.ordinal*32+24)<=15));
 r=await engine.query({...options,collection:'goodreads',pageSize:100});assert.ok(r.refs.every(ref=>view.getUint32(ref.ordinal*32+28,true)!==0xffffffff));
 const first=await engine.query({...options,pageSize:2}),favorites=first.refs.map(ref=>ref.id);r=await engine.query({...options,collection:'favorites',favorites});assert.equal(r.total,2);
 assert.equal((await engine.query({...options,section:'not-a-section'})).total,0);assert.equal((await engine.query({...options,topic:'Science'})).total,0);assert.equal((await engine.query({topic:'Life & meaning',section:'library:Life & meaning'})).total,0,'Do not expose oversized library leaves');
 const own={id:'own-section',text:'Purpose and learning.',author:'A Reader',topics:['Life & meaning','Science'],minAge:8,importance:3,year:null,likes:null,source:'My notebook'};
 assert.equal((await engine.query({...options,custom:[own]})).total,section.count,'Curated section cap excludes personal overflow');
 r=await engine.query({topic:'Life & meaning',section:'custom:Life & meaning',custom:[own]});assert.equal(r.total,1);assert.equal(r.refs[0].record.id,own.id);
 assert.equal((await engine.query({topic:'Life & meaning',section:'custom:Life & meaning',custom:[own],age:5})).total,0);
 assert.equal((await engine.query({topic:'Science',section:'library:Science',custom:[own]})).total,manifest.topics.find(t=>t.name==='Science').count);
 const retry=createEngine({manifest,base:'https://example.com/data/',fetch:fetcher});fail.add(section.file);await assert.rejects(retry.query(options),/section could not/);fail.delete(section.file);assert.equal((await retry.query(options)).total,section.count);
 const file=section.file,valid=JSON.parse(fs.readFileSync(root+'/'+file));const malformed=createEngine({manifest,base:'https://example.com/data/',fetch:async url=>new URL(url).pathname.endsWith(file)?{ok:true,json:async()=>[valid[0],valid[0]]}:fetcher(url)});await assert.rejects(malformed.query(options),/incomplete/);
 console.log(JSON.stringify({status:'PASS',groups:manifest.browseGroups.length,children:leaves.length,largest:Math.max(...leaves.map(x=>x.section.count),...manifest.topics.filter(t=>!manifest.browseGroups.some(g=>g.topic===t.name)).map(t=>t.count)),checks:['every parent quote covered exactly once','all leaves <=10000','paging/search/age/likes/favorites intersections','personal additions separate','invalid sections and retry','bounded lazy cache']}));
})().catch(e=>{console.error(e);process.exitCode=1});
