// Values absent from evidence are not zero. Units are part of the measurement.
export const finiteNumber = value => typeof value === 'number' && Number.isFinite(value);
export function metricCount(value) { return finiteNumber(value) ? new Intl.NumberFormat('en-US').format(value) : '—'; }
export function economicValue(value, unit) {
 if (!finiteNumber(value)) return '—';
 if (unit === '%') return `${value.toFixed(1)}%`;
 if (unit === 'USD') return new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',notation:Math.abs(value)>=1e6?'compact':'standard',maximumFractionDigits:2}).format(value);
 return `${new Intl.NumberFormat('en-US',{maximumFractionDigits:2}).format(value)}${unit ? ` ${unit}` : ''}`;
}
export function reportFilterDate(item, basis) { return basis === 'evidence' ? (item.historical?.asOf || item.dataCutoff || item.tradingScenario?.observedOn || '').slice(0,10) : (item.createdAt || '').slice(0,10); }
// Fiscal dates are civil dates, not UTC instants. Do not move them to yesterday
// for readers west of UTC. Actual timestamps retain the reader's local zone.
export function reportDisplayDate(value, language = 'zh') {
 if (typeof value !== 'string' || !value) return '—';
 const civil = /^\d{4}-\d{2}-\d{2}$/.test(value);
 const date = new Date(value);
 if (!Number.isFinite(date.getTime())) return '—';
 if (civil && date.toISOString().slice(0,10) !== value) return '—';
 return date.toLocaleDateString(language === 'zh' ? 'zh-CN' : 'en-CA', civil ? {timeZone:'UTC'} : undefined);
}
