import {writeFile} from 'node:fs/promises';
const indicators=['FP.CPI.TOTL.ZG','NY.GDP.MKTP.KD.ZG','SL.UEM.TOTL.ZS','NY.GDP.MKTP.CD','NV.IND.TOTL.ZS','NV.AGR.TOTL.ZS'];
const countries='USA;CHN;JPN;DEU;IND;CAN;GBR;SAU;BRA;ZAF;MEX;ISR;UKR';
const series={};
for(const indicator of indicators){
 const url=`https://api.worldbank.org/v2/country/${countries}/indicator/${indicator}?format=json&date=1960:${new Date().getUTCFullYear()}&per_page=20000`;
 const response=await fetch(url,{signal:AbortSignal.timeout(45000)});
 if(!response.ok)throw new Error(`${indicator}: ${response.status}`);
 const [meta,rows]=await response.json();
 if(!Array.isArray(rows)||Number(meta.pages)!==1)throw new Error(`${indicator}: incomplete response`);
 series[indicator]={sourceUrl:url,providerUpdatedAt:meta.lastupdated,rows:rows.filter(r=>typeof r.value==='number'&&Number.isFinite(r.value)).map(r=>({country:r.country,countryiso3code:r.countryiso3code,date:r.date,value:r.value}))};
 console.log(indicator,series[indicator].rows.length);
}
await writeFile(new URL('../snapshot/economic-cache.json',import.meta.url),JSON.stringify({provider:'World Bank',retrievedAt:new Date().toISOString(),series}));
