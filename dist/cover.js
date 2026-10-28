(function(root){
 'use strict';
 const themes={forest:{label:'Botanical green',color:'#2c493b'},rust:{label:'Printer’s red',color:'#8b4437'},ivory:{label:'Natural linen',color:'#e8e0ce'},navy:{label:'Midnight blue',color:'#253c59'},burgundy:{label:'Oxblood',color:'#652d3b'},teal:{label:'Verdigris',color:'#286362'},plum:{label:'Aubergine',color:'#593c58'},ochre:{label:'Golden ochre',color:'#b38635'},slate:{label:'Slate blue',color:'#54616c'},black:{label:'Carbon black',color:'#252927'}};
 const fonts={serif:{label:'Baskerville',css:'Libre, Georgia, serif',pdf:'BookSerif'},italic:{label:'Baskerville Italic',css:'Libre, Georgia, serif',style:'italic',pdf:'BookItalic'},sans:{label:'Modern Sans',css:'DM, Arial, sans-serif',pdf:'BookSans'}};
 const isColor=value=>typeof value==='string'&&/^#[a-f\d]{6}$/i.test(value);
 const isImage=value=>typeof value==='string'&&value.length<=1500000&&/^data:image\/(?:png|jpeg);base64,[a-zA-Z0-9+/]+=*$/.test(value);
 function normalize(book={}){return{...book,format:'5x8',theme:Object.hasOwn(themes,book.theme)?book.theme:'forest',coverColor:isColor(book.coverColor)?book.coverColor.toLowerCase():null,titleFont:Object.hasOwn(fonts,book.titleFont)?book.titleFont:'serif',titleSize:Number.isFinite(book.titleSize)?Math.max(12,Math.min(40,book.titleSize)):28,coverImage:isImage(book.coverImage)?book.coverImage:null}}
 const rgb=hex=>[1,3,5].map(i=>parseInt(hex.slice(i,i+2),16));
 function luminance(color){return rgb(color).map(n=>{const s=n/255;return s<=.04045?s/12.92:((s+.055)/1.055)**2.4}).reduce((s,n,i)=>s+n*[.2126,.7152,.0722][i],0)}
 function palette(book){const b=normalize(book),background=b.coverColor||themes[b.theme].color,light='#f0e4bd',dark='#263a2e',l=luminance(background),a=(Math.max(l,luminance(light))+.05)/(Math.min(l,luminance(light))+.05),d=(Math.max(l,luminance(dark))+.05)/(Math.min(l,luminance(dark))+.05),ink=a>=d?light:dark;return{background,ink,bg:rgb(background),inkRgb:rgb(ink)}}
 // The same word wrapping is used by SVG previews and the print cover.
 // measure(text, pointSize) returns width in the cover's 360 x 576 coordinates.
 function titleLayout(title,requestedSize,measure,width=268,height=130){
  const words=String(title||'Commonplace Book').trim().toUpperCase().split(/\s+/),start=Number.isFinite(requestedSize)?Math.max(12,Math.min(40,requestedSize)):28,lineHeight=1.25;
  let size=start,lines=[];
  for(;;){lines=[];let current='';for(const word of words){const candidate=current?current+' '+word:word;if(current&&measure(candidate,size)>width){lines.push(current);current=word}else current=candidate}if(current)lines.push(current);if(lines.every(line=>measure(line,size)<=width+.001)&&lines.length*size*lineHeight<=height+.001)break;size-=.25;if(size<=.25){size=.25;break}}
  return{lines,size,height:lines.length*size*lineHeight,lineHeight};
 }
 root.CommonplaceCover={themes,fonts,normalize,palette,titleLayout,isColor,isImage,size:[360,576],illustration:{x:73,y:246,width:214,height:190}};
})(typeof window!=='undefined'?window:globalThis);
