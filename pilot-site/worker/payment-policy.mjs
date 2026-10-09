// Merchant-confirmed public recipient. Never use a provenance/devnet address for billing.
export const MERCHANT='9WLRmvq8a86A6q9JwrzKqyVoUXDJoXC14SKNix3xZ79Z';
export const MINTS=Object.freeze({USDC:'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',USDT:'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB'});
export const PRICES=Object.freeze({signal:'19',research:'79'});
export const PAYMENT_MODE='solana_monthly';
export function catalogFor(env={}){return {mode:PAYMENT_MODE,enabled:env.ORAKT_SOLANA_PAYMENTS_ENABLED==='true',network:'solana:mainnet-beta',networkConfirmed:true,currencies:Object.keys(MINTS),mints:MINTS,recipient:MERCHANT,autoRenew:false,term:'one_calendar_month_utc',plans:[{key:'explorer',price:'0'},...Object.entries(PRICES).map(([key,price])=>({key,price}))]};}
export const paymentCatalog=catalogFor();
export function addCalendarMonth(timestamp){const date=new Date(timestamp),day=date.getUTCDate();date.setUTCDate(1);date.setUTCMonth(date.getUTCMonth()+1);const last=new Date(Date.UTC(date.getUTCFullYear(),date.getUTCMonth()+1,0)).getUTCDate();date.setUTCDate(Math.min(day,last));return date.getTime();}
// Pure settlement check, to be wired to durable orders after merchant configuration.
// RPC status must be fetched server-side, never accepted from a client payload.
export function verifyStablecoinReceipt(order,tx,status,now=Date.now()){
 if(!order||order.network!=='solana:mainnet-beta'||MINTS[order.currency]!==order.mint||!order.reference||!order.payer||order.recipient!==MERCHANT||order.payer===order.recipient||!/^\d+$/.test(order.amountUnits)||BigInt(order.amountUnits)<=0n||!Number.isSafeInteger(order.createdAt)||!Number.isSafeInteger(order.expiresAt)||order.expiresAt<=order.createdAt)return {ok:false,reason:'invalid_order'};
 if(!status||status.confirmationStatus!=='finalized'||status.err!==null||!tx||!tx.meta||tx.meta.err!==null)return {ok:false,reason:'not_finalized_or_failed'};
 if(!Number.isSafeInteger(tx.blockTime)||tx.blockTime*1000<order.createdAt||tx.blockTime*1000>order.expiresAt||tx.blockTime*1000>now)return {ok:false,reason:'outside_order_window'};
 const keys=tx.transaction?.message?.accountKeys||[];
 if(!keys.some(k=>k.pubkey===order.reference)||!keys.some(k=>k.pubkey===order.payer&&k.signer===true))return {ok:false,reason:'reference_or_signer_mismatch'};
 const sum=(rows,owner)=>rows.filter(b=>b.owner===owner&&b.mint===order.mint).reduce((n,b)=>{if(b.uiTokenAmount?.decimals!==6||!/^\d+$/.test(b.uiTokenAmount.amount))throw Error('invalid_balance');return n+BigInt(b.uiTokenAmount.amount);},0n);
 try{const pre=tx.meta.preTokenBalances,post=tx.meta.postTokenBalances;if(!Array.isArray(pre)||!Array.isArray(post))throw Error('missing');const amount=BigInt(order.amountUnits);if(sum(post,order.recipient)-sum(pre,order.recipient)!==amount||sum(pre,order.payer)-sum(post,order.payer)!==amount)return {ok:false,reason:'mint_recipient_or_amount_mismatch'};}
 catch{return {ok:false,reason:'invalid_token_balances'};}
 return {ok:true,amountUnits:order.amountUnits,network:order.network};
}
