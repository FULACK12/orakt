// Mechanical, reproducible extraction from the MIT-licensed official SDK IDL.
// SDK is dev-only; hosted code imports this bounded layout, never transaction builders.
import {DynamicBondingCurveIdl as idl} from '@meteora-ag/dynamic-bonding-curve-sdk';
import {writeFileSync} from 'node:fs';
const types=new Map(idl.types.map(t=>[t.name,t.type]));
export function layout(name){
 const fields=[];let offset=8;
 function visit(type,path){
  if(typeof type==='string'){
   const size={u8:1,u16:2,u32:4,u64:8,u128:16,pubkey:32}[type];
   if(!size)throw Error('Unsupported IDL primitive '+type);
   fields.push({path,offset,type,size});offset+=size;return;
  }
  if(type.array){for(let i=0;i<type.array[1];i++)visit(type.array[0],path+'.'+i);return;}
  const structure=types.get(type.defined?.name);if(structure?.kind!=='struct')throw Error('Unsupported IDL type');
  for(const f of structure.fields)visit(f.type,path?path+'.'+f.name:f.name);
 }
 visit({defined:{name}},'');return {discriminator:idl.accounts.find(a=>a.name===name).discriminator,size:offset,fields};
}
export const layouts=Object.fromEntries(['VirtualPool','PoolConfig'].map(n=>[n,layout(n)]));
if(process.argv.includes('--write'))writeFileSync(new URL('../worker/meteora-layout.mjs',import.meta.url),'// Generated from @meteora-ag/dynamic-bonding-curve-sdk 1.5.13, MIT. See meteora-NOTICE.md.\nexport default '+JSON.stringify(layouts)+';\n');
