import {readFileSync,writeFileSync} from 'node:fs';
const data=JSON.parse(readFileSync(process.argv[2],'utf8'));
if(data.version!=='company-report-inventory/v1'||data.complete!==false||!Array.isArray(data.companies))throw Error('Unexpected inventory');
if(data.totals.companies!==data.companies.length||new Set(data.companies.map(c=>c.market+':'+c.ticker)).size!==data.companies.length)throw Error('Inventory count/identity mismatch');
if(data.companies.some(c=>c.complete||c.market==='us'&&(c.publishedPeriods>c.indexedPeriods||c.missingPeriods!==c.indexedPeriods-c.publishedPeriods)))throw Error('Invalid period coverage');
const raw=JSON.stringify(data);if(/F:[/\\]|completion.sqlite3|sourcePath|api[_-]?key/i.test(raw))throw Error('Private runtime detail in export');
writeFileSync(new URL('../private-data/company-report-inventory.json',import.meta.url),raw+'\n');
console.log(JSON.stringify(data.totals));
