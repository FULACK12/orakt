import test from 'node:test';
import assert from 'node:assert/strict';
import {reportChartMetrics} from '../app/report-chart-data.mjs';
test('report charts exclude future filings and future periods without mutating source',()=>{
 const metrics={revenue:[{end:'2009-06-30',filedAt:'2009-08-01',value:1},{end:'2009-06-30',filedAt:'2010-08-01',value:2},{end:'2009-09-30',filedAt:'2009-08-01',value:3},{end:'2009-06-30',value:4}]};
 assert.deepEqual(reportChartMetrics(metrics,{asOf:'2009-08-20',periodEnd:'2009-06-30'}).revenue,[metrics.revenue[0]]);
 assert.equal(metrics.revenue.length,4);
 assert.deepEqual(reportChartMetrics(metrics,{asOf:'2008-01-01'}).revenue,[]);
});
