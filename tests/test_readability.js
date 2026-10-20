const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(path.join(__dirname,'../web/app.js'),'utf8');
const context={};vm.runInNewContext(source.slice(source.indexOf('function readingParagraphs('),source.indexOf('function readingText(')),context);
const parse=text=>JSON.parse(JSON.stringify(context.recipeReadingSegments(text)));
const compact=text=>text.replace(/\s/gu,'');
const flatten=segments=>segments.map(s=>s.kind==='list'?s.items.map(i=>i.marker+i.text).join(''):s.text).join('');
const cases=[
 '步骤1熬制汤料1.取骨料1200克，加入清水2.5升煮开。2.放入盐12克，熬煮30分钟。3.过滤后保留汤料。',
 '步骤2调制卤水将香料放入汤中，加入盐30克，再煮15分钟。',
 '应用方法1.用浓度0.5%的盐水处理原料。2.清洗后焯水。3.放入汤中煮熟。4.捞出晾凉。制作味汁取红油20克，加入酱油5克。',
 '步骤1取香料21.5克，加入汤中。',
 '先称取1.5千克原料，再加入0.5%的盐水。',
 '按照步骤1处理原料，再继续烹调。',
 '1.准备食材。\n2.按顺序处理。',
 '2.放入配料。3.改小火。',
 '原料：鸡肉1500克。\n调料：盐10克。',
 '应用方法1.加入1.5升水。2.保持浓度0.5%。'
];
for(const text of cases)assert.equal(compact(flatten(parse(text))),compact(context.readingParagraphs(text).join('')),text);
let sections=parse(cases[0]);assert.equal(sections[0].kind,'heading');assert.equal(sections[0].text,'步骤1熬制汤料');assert.equal(sections[1].items.length,3);assert.ok(sections[1].items[0].text.includes('2.5升'));
sections=parse(cases[1]);assert.equal(sections[0].text,'步骤2调制卤水');assert.ok(sections[1].text.startsWith('将香料'));
sections=parse(cases[2]);assert.equal(sections[0].text,'应用方法');assert.equal(sections[1].items.length,4);assert.equal(sections[2].text,'制作味汁');assert.ok(sections[1].items[0].text.includes('0.5%'));
sections=parse(cases[3]);assert.equal(sections[0].text,'步骤1');assert.ok(sections[1].text.includes('21.5克'));
assert.ok(parse(cases[4]).every(s=>s.kind==='paragraph'));assert.ok(parse(cases[5]).every(s=>s.kind==='paragraph'));
assert.equal(parse(cases[6])[0].items.length,2);assert.equal(parse(cases[7])[0].items[0].marker,'2.');
// Vary quantities and wrapping to ensure decimal numbers and all recognized characters survive.
for(let i=1;i<=80;i++){
 const text=`步骤1加工原料1.取食材${i}.5克，加水0.5升。2.煮${i}分钟。3.加入${i*10}毫升汤料。`;
 assert.equal(compact(flatten(parse(text))),compact(text));assert.equal(parse(text)[1].items.length,3);
}
console.log('PASS reading sections, inline enumerations, decimals, original-character preservation and 80 quantity cases');
