// Explicit user clicks only. No custody, asset transfers or automatic signing.
export async function sendProvenance(){
 const wallets=new Set<any>(),api={register:(...ws:any[])=>{ws.forEach(w=>wallets.add(w));return()=>ws.forEach(w=>wallets.delete(w));}},listener=(e:any)=>e.detail(api);
 window.addEventListener('wallet-standard:register-wallet',listener);
 try{
  window.dispatchEvent(new CustomEvent('wallet-standard:app-ready',{detail:api}));
  const wallet=[...wallets].find(w=>w.name==='Phantom'&&w.features['solana:signAndSendTransaction']);if(!wallet)throw Error('请安装 Phantom 扩展或在钱包浏览器打开 / Phantom is required.');
  const result=await wallet.features['standard:connect'].connect(),account=result.accounts.find((a:any)=>a.chains.includes('solana:mainnet'));
  if(!account)throw Error('Phantom 未提供主网账号 / Mainnet account unavailable.');
  return {address:account.address,sign:async(bytes:number[])=>{const [result]=await wallet.features['solana:signAndSendTransaction'].signAndSendTransaction({account,chain:'solana:mainnet',transaction:new Uint8Array(bytes),options:{preflightCommitment:'confirmed'}});let n=0n;for(const b of result.signature)n=n*256n+BigInt(b);const abc='123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz';let out='';while(n){out=abc[Number(n%58n)]+out;n/=58n;}for(const b of result.signature){if(b)break;out='1'+out;}return out;}};
 }finally{window.removeEventListener('wallet-standard:register-wallet',listener);}
}
