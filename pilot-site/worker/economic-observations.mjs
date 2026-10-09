export function annualObservations(rows,countries,indicator,unit,year){
 const latest=new Map();
 for(const row of rows||[]){
  const date=Number(row.date);
  if(typeof row.value!=='number'||!Number.isFinite(row.value)||!Number.isInteger(date)||date>year||date<Math.max(1960,year-9)||!countries[row.countryiso3code])continue;
  if(latest.has(row.countryiso3code)&&Number(latest.get(row.countryiso3code).date)>=date)continue;
  latest.set(row.countryiso3code,row);
 }
 return [...latest.values()].map(r=>({country:r.country.value,iso2:countries[r.countryiso3code].iso2,date:r.date,value:r.value,unit,indicator,coordinates:countries[r.countryiso3code].coordinates}));
}
