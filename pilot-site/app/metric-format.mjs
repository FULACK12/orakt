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
