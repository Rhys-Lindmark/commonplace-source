'use strict';
const fs=require('fs'),vm=require('vm'),path=require('path'),assert=require('node:assert/strict');
const {jsPDF}=require('../dist/vendor/jspdf.umd.min.js');global.jspdf={jsPDF};vm.runInThisContext(fs.readFileSync('dist/dates.js','utf8'));vm.runInThisContext(fs.readFileSync('dist/cover.js','utf8'));vm.runInThisContext(fs.readFileSync('dist/pdf.js','utf8'));
const primaryPoints=new Set(JSON.parse(fs.readFileSync('work/expansion/font-codepoints.json')));let first,alternate;
for(const file of fs.readdirSync('dist/data/records').sort()){for(const q of JSON.parse(fs.readFileSync(path.join('dist/data/records',file)))){if(q.provenance?.dataset==='QuoteKG v1.2'){first=first||q;if(Array.from(q.text+q.author).some(c=>!primaryPoints.has(c.codePointAt(0))&&!/\s/u.test(c)))alternate=q}if(first&&alternate)break}if(first&&alternate)break}
assert.ok(first&&alternate,'real corpus exercises expanded print glyph coverage');
const font={primary:fs.readFileSync('dist/assets/book-serif.ttf').toString('base64'),fallback:fs.readFileSync('dist/assets/book-fallback.ttf').toString('base64')};
const book={title:'A Wider World of Words',author:'The Commonplace Reader',dedication:'A collection for a curious life.',theme:'forest',format:'6x9',sources:false,pad:true,spine:.054};
const goodreads=JSON.parse(fs.readFileSync('dist/data/records/00500.json')).find(q=>q.provenance?.dataset==='Goodreads CC0 collection');assert.ok(goodreads);const doc=CommonplacePDF.generate('reading',book,[first,alternate,goodreads],font);assert.equal(doc.getNumberOfPages(),7);assert.equal(doc.getFont().fontName,'BookFallback');fs.writeFileSync('output/pdf/commonplace-expanded-sample.pdf',Buffer.from(doc.output('arraybuffer')));
const count=Array.from(doc.internal.pages).filter(Boolean).flat().filter(x=>typeof x==='string'&&x.includes('/Annots')).length;
assert.throws(()=>CommonplacePDF.generate('reading',book,[{...first,text:'A passage with an unsupported character: 文'}],font),/not covered/);
console.log('PASS: real imported quotes export with embedded international serif fallback;7pages; unsupportedcustomglyphs fail explicitly.');
