// U.S. symbols without a known exchange use provider search instead of guessing an exchange.
const nasdaq=new Set(['AAPL','NVDA','AMD','MSFT','AMZN','LULU','QQQ','META','GOOGL','GOOG','TSLA','AVGO','MU','INTC','COST','NFLX']);
export function tradingSymbol(ticker,market){if(market==='china')return (ticker.startsWith('6')?'SSE:':'SZSE:')+ticker;return nasdaq.has(ticker)?'NASDAQ:'+ticker:ticker==='SPY'?'AMEX:SPY':ticker;}
