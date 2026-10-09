export function resolveDisplayLanguage(saved,languages=[]){
 if(saved==='zh'||saved==='en')return saved;
 for(const value of languages){const base=String(value).toLowerCase().split(/[-_]/)[0];if(base==='zh'||base==='en')return base;}
 return 'en';
}
