export function inventoryPage(data,url){
 const q=(url.searchParams.get('q')||'').slice(0,100).trim().toLowerCase(),market=url.searchParams.get('market')||'all';
 const n=Number(url.searchParams.get('page')||1),page=Number.isFinite(n)?Math.max(1,Math.floor(n)):1,size=25;
 const rows=data.companies.filter(c=>(market==='all'||c.market===market)&&(!q||(c.ticker+' '+c.companyName).toLowerCase().includes(q)));
 const actual=Math.min(page,Math.max(1,Math.ceil(rows.length/size)));
 return {...data,companies:rows.slice((actual-1)*size,actual*size),page:actual,totalPages:Math.max(1,Math.ceil(rows.length/size)),matched:rows.length};
}
