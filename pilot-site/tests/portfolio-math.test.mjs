import test from 'node:test';
import assert from 'node:assert/strict';
import {portfolioStats} from '../app/portfolio-math.mjs';
test('portfolio scenario is transparent weighted arithmetic, not a backtest',()=>{
 const p=portfolioStats([{symbol:'AAPL',weight:50,shock:-10},{symbol:'CASH:USD',weight:50,shock:0}]);
 assert.equal(p.scenario,-5);assert.equal(p.effectivePositions,2);assert.equal(p.ready,true);
});
test('invalid allocation cannot produce a scenario',()=>{
 for(const rows of [[],[{symbol:'A',weight:99,shock:0}],[{symbol:'A',weight:50,shock:0},{symbol:'A',weight:50,shock:0}],[{symbol:'',weight:100,shock:0}],[{symbol:'A',weight:100,shock:NaN}]])assert.equal(portfolioStats(rows).scenario,null);
});
