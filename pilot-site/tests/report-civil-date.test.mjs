import test from 'node:test';
import assert from 'node:assert/strict';
import {reportDisplayDate} from '../app/metric-format.mjs';

test('fiscal report labels do not shift a day across reader timezones',()=>{
 const old=process.env.TZ;
 try {
  for(const zone of ['America/Toronto','America/Los_Angeles','Asia/Shanghai']){
   process.env.TZ=zone;
   assert.equal(reportDisplayDate('2026-06-30','en'),'2026-06-30');
   assert.equal(reportDisplayDate('2026-07-26','zh'),'2026/7/26');
  }
  process.env.TZ='America/Toronto';
  assert.equal(reportDisplayDate('2026-07-01T00:00:00Z','en'),'2026-06-30');
 } finally {if(old===undefined)delete process.env.TZ;else process.env.TZ=old;}
});
test('missing and invalid dates are not invented',()=>{
 for(const value of [null,'','not-a-date','2026-02-30'])assert.equal(reportDisplayDate(value),'—');
});
