import {test} from 'node:test';
import assert from 'node:assert/strict';
import {comparableYoY,ratioPoints} from '../app/financial-chart-math.mjs';
const prior={start:'2023-01-01',end:'2023-03-31',basis:'quarter',unit:'USD',value:100};
const current={...prior,start:'2024-01-01',end:'2024-03-31',value:120};
test('YoY matches comparable quarter only',()=>{assert.ok(Math.abs(comparableYoY(current,[prior,current])-20)<1e-9);assert.equal(comparableYoY(current,[{...prior,basis:'ytd'},current]),null);});
test('missing, conflicting and nonpositive bases omitted',()=>{assert.equal(comparableYoY(current,[current]),null);assert.equal(comparableYoY(current,[prior,{...prior,value:90}]),null);assert.equal(comparableYoY(current,[{...prior,value:-100}]),null);});
test('ratio keeps source and denominator',()=>{const r=ratioPoints([{...prior,value:20,sourceUrl:'a'}],[{...prior,sourceUrl:'b'}]);assert.equal(r[0].value,20);assert.equal(r[0].denominatorSource,'b');assert.deepEqual(ratioPoints([prior],[{...prior,value:0}]),[]);});
