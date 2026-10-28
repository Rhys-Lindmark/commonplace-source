const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const {jsPDF}=require(path.join(root,'dist/vendor/jspdf.umd.min.js'));
global.jspdf={jsPDF};
vm.runInThisContext(fs.readFileSync(path.join(root,'dist/dates.js'),'utf8'));
vm.runInThisContext(fs.readFileSync(path.join(root,'dist/cover.js'),'utf8'));
vm.runInThisContext(fs.readFileSync(path.join(root,'dist/pdf.js'),'utf8'));
const font=fs.readFileSync(path.join(root,'dist/assets/book-serif.ttf')).toString('base64');
const quotes=JSON.parse(fs.readFileSync(path.join(root,'dist/quotes.json')));
const book={title:'A Book for a Curious Mind',author:'The Commonplace Reader',dedication:'For the questions that lead us somewhere new.',theme:'forest',format:'6x9',sources:true,pad:true,spine:.054};
for(const kind of ['interior','reading','cover']){
 const doc=CommonplacePDF.generate(kind,book,quotes.slice(0,6),font);
 assert.equal(doc.getNumberOfPages(),kind==='cover'?1:kind==='reading'?9:8);
 const w=doc.internal.pageSize.getWidth(),h=doc.internal.pageSize.getHeight();
 assert.ok(Math.abs(w-(kind==='cover'?(2*360+18+(8/444+.06)*72):360))<.01);
 assert.ok(Math.abs(h-(kind==='cover'?594:576))<.01);
 fs.writeFileSync(path.join(root,'output/pdf',`commonplace-sample-${kind}.pdf`),Buffer.from(doc.output('arraybuffer')));
}
for(const format of ['5x8','a5','6x9']){
 const doc=CommonplacePDF.generate('interior',{...book,format,pad:false,title:'A'.repeat(80)},quotes.slice(0,21),font);
 assert.equal(doc.getNumberOfPages(),24);
 assert.ok(Math.abs(doc.internal.pageSize.getWidth()-360)<.01);
}
const long={...quotes[0],text:'Curiosity opens a door to understanding. '.repeat(30)};
const doc=CommonplacePDF.generate('interior',{...book,pad:false,format:'5x8'},[long],font);
assert.equal(doc.getNumberOfPages(),4);
assert.throws(()=>CommonplacePDF.generate('interior',{...book,format:'5x8'},[{...long,text:'Curiosity opens a door to understanding. '.repeat(75)}],font),/too long to fit/);
assert.throws(()=>CommonplacePDF.generate('interior',book,[],font),/Choose at least/);
assert.equal(new Set(quotes.map(q=>q.id)).size,quotes.length);
assert.ok(quotes.length>=2000);
console.log('PASS: PDF page counts, fixed 5x8 trim for legacy formats, wrap dimensions, long passage fit, empty selection, library uniqueness.');
