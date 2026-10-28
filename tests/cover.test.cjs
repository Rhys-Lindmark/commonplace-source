'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const {jsPDF}=require('../dist/vendor/jspdf.umd.min.js');global.jspdf={jsPDF};
vm.runInThisContext(fs.readFileSync('dist/dates.js','utf8'));vm.runInThisContext(fs.readFileSync('dist/cover.js','utf8'));
vm.runInThisContext(fs.readFileSync('dist/pdf.js','utf8'));
const C=CommonplaceCover;
assert.equal(Object.keys(C.themes).length,10);
assert.equal(C.normalize({format:'6x9'}).format,'5x8');
assert.equal(C.normalize({titleSize:100,titleFont:'untrusted'}).titleSize,40);
assert.equal(C.normalize({titleFont:'untrusted'}).titleFont,'serif');
assert.equal(C.palette({coverColor:'#ffffff'}).ink,'#263a2e');
assert.equal(C.palette({coverColor:'#000000'}).ink,'#f0e4bd');
assert.equal(C.palette({coverColor:'url(javascript:1)'}).background,C.themes.forest.color);
const measure=(text,size)=>text.length*size*.65;
for(const [title,size] of [['Commonplace Book',40],['A library for the life that lies ahead',40],['A'.repeat(80),40]]){
 const layout=C.titleLayout(title,size,measure);
 assert.equal(layout.lines.join(' '),title.toUpperCase());
 assert.ok(layout.height<=130);
 assert.ok(layout.lines.every(line=>measure(line,layout.size)<=268+.001));
}
const font={primary:fs.readFileSync('dist/assets/book-serif.ttf').toString('base64'),fallback:fs.readFileSync('dist/assets/book-fallback.ttf').toString('base64'),italic:fs.readFileSync('dist/assets/book-italic.ttf').toString('base64'),sans:fs.readFileSync('dist/assets/sans.ttf').toString('base64')};
const q={text:'A thought worth keeping.',author:'A Reader',year:2026,sourceUrl:''};
const image='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAIAAAABCAIAAAB7QOjdAAAAD0lEQVR4nGPQ8bT+8GQvAAi9A0KLS5Q3AAAAAElFTkSuQmCC';
assert.ok(C.isImage(image));
assert.equal(C.isImage('data:image/svg+xml;base64,PHN2Zz4='),false);
for(const titleFont of ['serif','italic','sans']){
 const b={title:'COMMONPLACE BOOK',author:'A Reader',titleFont,titleSize:40,format:'6x9',theme:'plum',coverColor:'#20334d',coverImage:image,sources:true};
 const doc=CommonplacePDF.generate('reading',b,[q],font);
 assert.equal(doc.internal.pageSize.getWidth(),360);assert.equal(doc.internal.pageSize.getHeight(),576);
 const data=doc.output();assert.ok(data.includes('/Subtype /Image'),'uploaded artwork embedded');
 const fontName=C.fonts[titleFont].pdf;
 assert.ok(Object.values(doc.getFontList()).length>=4);
 const chosen=doc.internal.getFont(fontName);
 assert.ok(doc.internal.pages[1].some(command=>command.includes('/'+chosen.id+' ')),'selected title font used on cover');
 assert.equal(doc.getFont().fontName,'BookSerif','quote/body font restored after cover');
}
const n=CommonplacePDF.generate('cover',{title:'A'.repeat(80),author:'',theme:'ivory',titleSize:40,titleFont:'sans'},[q],font);
assert.equal(n.getNumberOfPages(),1);
console.log('PASS: whole-word cover fitting, long single words, ten palettes/custom contrast, three embedded fonts, uploaded image embedding, fixed 5x8 and body font restoration.');
