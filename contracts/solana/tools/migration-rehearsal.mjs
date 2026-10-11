// Input is anonymized and local. Refuses production snapshots; never writes a file.
import {readFileSync,statSync} from 'node:fs';
import {migrationPreflight} from './migration-preflight.mjs';
try {
  if(process.argv.length!==3)throw Error('Usage: node migration-rehearsal.mjs <local-anonymized-devnet-snapshot.json>');
  const file=process.argv[2];if(!statSync(file).isFile()||statSync(file).size>1000000)throw Error('input_not_bounded_file');
  const raw=readFileSync(file);if(raw.length>1000000)throw Error('input_not_bounded_file');
  const input=JSON.parse(raw.toString('utf8'));
  const report=migrationPreflight(input,Date.now());
  console.log(JSON.stringify(report,null,2));if(report.blocked)process.exitCode=2;
}catch(e){console.error(JSON.stringify({status:'unverified',error:e.message,changesApplied:0,productionReady:false}));process.exitCode=1;}
