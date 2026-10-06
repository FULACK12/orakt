import {DatabaseSync} from "node:sqlite";
import {readFileSync,readdirSync} from "node:fs";
export function memberDatabase(){
 const sql=new DatabaseSync(":memory:");
 for(const f of readdirSync(new URL("../drizzle/",import.meta.url)).filter(f=>f.endsWith(".sql")).sort())sql.exec(readFileSync(new URL("../drizzle/"+f,import.meta.url),"utf8"));
 let queue=Promise.resolve();
 const DB={prepare(query){return{bind(...args){const s=sql.prepare(query);return{first:async()=>s.get(...args)??null,all:async()=>({results:s.all(...args)}),run:async()=>({meta:{changes:s.run(...args).changes}})};}};},batch(queries){const execute=async()=>{sql.exec("BEGIN");try{const out=[];for(const q of queries)out.push(await q.run());sql.exec("COMMIT");return out;}catch(e){sql.exec("ROLLBACK");throw e;}};const result=queue.then(execute);queue=result.catch(()=>{});return result;}};
 return{sql,DB};
}
