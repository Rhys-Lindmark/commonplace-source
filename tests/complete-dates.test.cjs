'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
vm.runInThisContext(fs.readFileSync('dist/dates.js','utf8'));
const D=CommonplaceDates,manifest=JSON.parse(fs.readFileSync('dist/data/manifest.json')),report=JSON.parse(fs.readFileSync('work/date-estimates/report.json')),bytes=fs.readFileSync('dist/data/catalog.bin'),catalog=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength);
let total=0,estimated=0,sourced=0,originalYears=0,sample;const methods={};
for(const file of fs.readdirSync('dist/data/records').sort())for(const q of JSON.parse(fs.readFileSync('dist/data/records/'+file))){
 const c=q.chronology;assert.equal(c.version,2,q.id);assert.equal(c.auditId,manifest.dateAuditId);assert.equal(D.valid(c),true,q.id);assert.equal(D.known(q),true,q.id);assert.equal(catalog.getInt16(total*32+22,true),D.sortYear(q));assert.notEqual(D.sortYear(q),32767);if(q.year!==null)originalYears++;
 if(c.kind==='estimate'){
  estimated++;sample??=q;methods[c.method]=(methods[c.method]||0)+1;assert.equal(c.startYear,c.endYear);assert.ok(c.method&&c.confidence&&c.note);assert.ok(D.label(q,{estimateSuffix:true}).endsWith(' · estimate'));
  assert.ok(!D.label(q).includes('estimate'));assert.ok(!D.label(q,{detailed:true}).includes('estimate'));assert.equal(D.description(q),'');assert.deepEqual(D.links(q),[]);assert.ok(c.sourceUrls.every(u=>/^https?:/.test(u)));
  const a=c.anchors||{};if(a.deathYear>1000)assert.ok(c.startYear>0,'Modern death anchor must not yield a BCE estimate: '+q.id);if(a.birthYear&&a.deathYear)assert.ok(a.deathYear-a.birthYear<=150,'Impossible lifespan cannot anchor an estimate: '+q.id);assert.ok(c.startYear<=(a.cutoffYear||2026));if(a.birthYear>=-3000&&a.birthYear<=(a.cutoffYear||2026))assert.ok(c.startYear>=a.birthYear,q.id);if(a.deathYear>=-3000)assert.ok(c.startYear<=a.deathYear,q.id);
 }else sourced++;
 total++;
}
assert.equal(report.unchangedContentFingerprint,'cfa21964d8e4a4d18b1565f4e5043568ea5b4804681da4aada590a514946b970','Every original record field except chronology is preserved');assert.equal(total,102444);assert.equal(originalYears,7,'Original year fields remain unchanged');assert.equal(estimated,report.counts.estimate);assert.equal(sourced,report.counts.work+report.counts['source-context']);assert.equal(estimated+sourced,manifest.chronology.dated);assert.equal(manifest.chronology.unknown,0);assert.ok(sourced>60000&&estimated>20000);
assert.equal(D.valid({...sample.chronology,version:1}),false);assert.equal(D.valid({version:1,kind:'unknown',reason:'legacy'}),true);
const app=fs.readFileSync('dist/app.js','utf8'),html=fs.readFileSync('dist/index.html','utf8');assert.ok(app.includes('CommonplaceDates.label(q,{estimateSuffix:true})'));assert.ok(!html.includes('date-sort-note'));assert.ok(!app.includes('date-sort-note'));
const {jsPDF}=require('../dist/vendor/jspdf.umd.min.js');global.jspdf={jsPDF};vm.runInThisContext(fs.readFileSync('dist/cover.js','utf8'));vm.runInThisContext(fs.readFileSync('dist/pdf.js','utf8'));const font={primary:fs.readFileSync('dist/assets/book-serif.ttf').toString('base64'),fallback:fs.readFileSync('dist/assets/book-fallback.ttf').toString('base64')},book={title:'Dates',author:'A Reader',format:'5x8',theme:'forest',sources:false},q={...sample,text:'Words carry through time.',author:'Date Author'};
const doc=CommonplacePDF.generate('interior',book,[q],font);fs.writeFileSync('/tmp/commonplace-estimated-date-test.pdf',Buffer.from(doc.output('arraybuffer')));fs.writeFileSync('/tmp/commonplace-estimated-date-label.txt',D.label(q));
console.log(JSON.stringify({status:'PASS',total,sourced,estimated,methods,checks:['every quote has a valid sortable date','original year fields preserved','estimates bounded by lifespan/corpus cutoff','estimate labels only on cards','old chronology schema retained','estimated-date PDF generated']}));
