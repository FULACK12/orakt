import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {annualObservations} from '../worker/economic-observations.mjs';
test('MapLibre v6 worker is bundled independently before map construction',()=>{
 const source=readFileSync('app/PilotDashboard.tsx','utf8');
 assert.match(source,/maplibre-gl-worker\.mjs\?worker&url/);
 assert.ok(source.indexOf('setWorkerUrl(mapWorkerUrl)')<source.indexOf('new maplibregl.Map('));
});
test('annual data never leaks future years or fills missing with zero',()=>{
 const countries={USA:{iso2:'US',coordinates:[-77,38]}};
 const row=(date,value)=>({country:{value:'United States'},countryiso3code:'USA',date:String(date),value});
 assert.deepEqual(annualObservations([row(2025,3),row(2009,2),row(2010,null),row(2008,4)],countries,'CPI','%',2010).map(x=>[x.date,x.value]),[['2009',2]]);
 assert.deepEqual(annualObservations([row(2025,3)],countries,'CPI','%',2009),[]);
});
test('archived chain URLs are not redirected to themselves by company-report deep links',()=>{
 const source=readFileSync('app/PilotDashboard.tsx','utf8');
 const redirect=source.indexOf('window.location.replace(reportHref(match))');
 const effect=source.slice(source.lastIndexOf('useEffect(',redirect),redirect);
 assert.match(effect,/if\(tab !== 'evidence'\)return/);
});
test('all six economic series retain provenance and finite observations',()=>{
 const cache=JSON.parse(readFileSync('snapshot/economic-cache.json','utf8'));
 assert.equal(Object.keys(cache.series).length,6);
 assert.ok(Number.isFinite(Date.parse(cache.retrievedAt)));
 for(const series of Object.values(cache.series)){assert.match(series.sourceUrl,/^https:\/\/api.worldbank.org\//);assert.ok(series.rows.length>0);assert.ok(series.rows.every(r=>Number.isFinite(r.value)));}
});
