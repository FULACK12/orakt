import fs from 'node:fs';
import ts from 'typescript';
const output=[];
for(const name of ['AccessPortal','GoogleLogin','LocalLogin','WalletLogin']){
 const path='app/access/'+name+'.tsx',source=fs.readFileSync(path,'utf8'),file=ts.createSourceFile(path,source,99,true,4);
 if(source.includes('auth-copy.mjs'))continue; // Safe to rerun; never nest translated calls.
 const transformed=ts.transform(file,[context=>root=>{
  const f=context.factory;
  const tr=text=>f.createCallExpression(f.createIdentifier('tr'),undefined,[f.createStringLiteral(text)]);
  function visit(n){
   if(ts.isJsxAttribute(n)&&n.initializer&&ts.isStringLiteral(n.initializer)&&/[\u3400-\u9fff]/.test(n.initializer.text))return f.updateJsxAttribute(n,n.name,f.createJsxExpression(undefined,tr(n.initializer.text)));
   if(ts.isJsxText(n)&&/[\u3400-\u9fff]/.test(n.text))return f.createJsxExpression(undefined,tr(n.text.trim()));
   if(ts.isStringLiteral(n)&&/[\u3400-\u9fff]/.test(n.text))return tr(n.text);
   return ts.visitEachChild(n,visit,context);
  }
  return f.updateSourceFile(root,root.statements.map(n=>{
   if(!ts.isFunctionDeclaration(n)||n.name?.text!==name||!n.body)return n;
   const body=ts.visitEachChild(n.body,visit,context);
   const init=ts.createSourceFile('init.ts',"const [language,setLanguage]=useDisplayLanguage();const tr=(text:string)=>authText(language,text);",99,true).statements;
   return f.updateFunctionDeclaration(n,n.modifiers,n.asteriskToken,n.name,n.typeParameters,n.parameters,n.type,n.body&&f.updateBlock(body,[...init,...body.statements]));
  }));
 }]).transformed[0];
 let result=ts.createPrinter().printFile(transformed).replace('"use client";','"use client";\nimport useDisplayLanguage from "../useDisplayLanguage";\nimport {authText} from "./auth-copy.mjs";');
 output.push({path,source:result});
}
console.log(JSON.stringify(output));
