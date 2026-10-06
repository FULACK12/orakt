import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import {createHash} from "node:crypto";
import {memberDatabase} from "./member-fixture.mjs";
import {memberFor} from "../worker/membership.mjs";
import {safeAccessReturnTo,accessHref} from "../app/access/access-navigation.mjs";
const fixture=memberDatabase();
const testGoogleToken="a".repeat(64);
const testGoogleHash=createHash("sha256").update(testGoogleToken).digest("hex");

const testPassword = "local-test-password";
const testSessionSecret = "local-test-session-secret-that-is-independent";

async function worker() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}-${Math.random()}`);
  return (await import(workerUrl.href)).default;
}

const env = {
  PILOT_ACCESS_PASSWORD: testPassword,
  DB:fixture.DB,
  PILOT_SESSION_SECRET: testSessionSecret,
  ASSETS: {
    fetch: async (request) => {
      const pathname = new URL(request.url).pathname;
      if (!/^\/snapshot\/research-reports\/[A-Za-z0-9_-]+\.json$/.test(pathname))
        return new Response("Not found", { status: 404 });
      try {
        const body = await readFile(
          new URL(`../private-data/research-reports/${pathname.split("/").at(-1)}`, import.meta.url),
        );
        return new Response(body, {
          status: 200,
          headers: { "content-type": "application/json; charset=utf-8" },
        });
      } catch {
        return new Response("Not found", { status: 404 });
      }
    },
  },
};

fixture.sql.prepare("INSERT INTO google_auth_sessions (id,browser,subject,origin,expires_at) VALUES (?,?,?,?,?)").run(testGoogleHash,"test-browser","test-google-subject","http://localhost",Date.now()+3600000);
const paid=await memberFor(env,{provider:"google",subject:"test-google-subject",displayName:"Google",accountId:"oldref",createdAt:null,expiresAt:null});
fixture.sql.prepare("UPDATE member_accounts SET plan='research',grant_kind='complimentary',expires_at=? WHERE id=?").run(Date.now()+86400000,paid.row.id);
const ctx = { waitUntil() {}, passThroughOnException() {} };

test('new research datasets require access and remain explicitly exploratory',async()=>{
 const app=await worker();
 for(const path of ['/api/alpha-lab','/api/macro-event-reports','/api/disclosure-reviews','/api/lab-expansion','/api/company-charts']){
  assert.equal((await app.fetch(new Request('http://localhost'+path),env,ctx)).status,401);
  assert.equal((await app.fetch(authorizedRequest(path),env,ctx)).status,200);
 }
 const alpha=await (await app.fetch(authorizedRequest('/api/alpha-lab'),env,ctx)).json();
 const catalog=await (await app.fetch(authorizedRequest('/api/company-charts'),env,ctx)).json();
 assert.ok(catalog.companies.length>=100);assert.ok(catalog.companies.every(c=>!c.metrics));
 const charts=await (await app.fetch(authorizedRequest('/api/company-charts?ticker=LULU'),env,ctx)).json();
 assert.ok(charts.company.metrics.revenue.length);assert.equal(charts.company.consensus,null);
 const unknown=await (await app.fetch(authorizedRequest('/api/company-charts?ticker=__proto__'),env,ctx)).json();assert.equal(unknown.company,null);
 const labs=await (await app.fetch(authorizedRequest('/api/lab-expansion'),env,ctx)).json();
 assert.equal(labs.factors.length,6);assert.ok(labs.factors.every(f=>!f.validatedAlpha));assert.equal(labs.baskets.length,3);
 assert.equal(alpha.experiments.length,3);
 for(const e of alpha.experiments){assert.equal(e.validatedAlpha,false);assert.ok(e.points.length>100);assert.ok(e.points.every(p=>Number.isFinite(p.strategy)&&Number.isFinite(p.market)&&Number.isFinite(p.industry)));}
 const reviews=await (await app.fetch(authorizedRequest('/api/disclosure-reviews'),env,ctx)).json();
 assert.ok(reviews.reports.length>=12);assert.equal(reviews.fullDossierCount,0);
 assert.ok(reviews.reports.every(r=>r.predictiveConfidence===null&&r.summary.en&&r.summary.zh&&r.comparisons.length));
});

test("ORAKT research operations and publication remain protected and read-only for members",async()=>{
 const app=await worker();
 for(const path of ['/api/research-operations','/api/publication/status','/api/publication/requests'])assert.equal((await app.fetch(new Request('http://localhost'+path),env,ctx)).status,401);
 const ops=await app.fetch(authorizedRequest('/api/research-operations'),env,ctx);
 assert.equal(ops.status,200);const data=await ops.json();assert.ok(data.history.companies.length>=239);assert.equal(data.alpha.validatedAlphaCount,null);
 const provenance=await (await app.fetch(authorizedRequest('/api/publication/status'),env,ctx)).json();assert.equal(provenance.canSubmit,false);assert.equal(provenance.broadcastEnabled,false);
 assert.ok(provenance.records.some(r=>r.reportId==='local-707'));
 assert.equal((await app.fetch(authorizedRequest('/api/publication/requests',{method:'POST',body:'{}'}),env,ctx)).status,403);
 const report=await (await app.fetch(authorizedRequest('/api/research-report?id=local-707'),env,ctx)).json();assert.equal(report.report.historical.eligibleForPredictiveBacktest,false);assert.equal(report.report.tradingScenario,null);
 const html=await (await app.fetch(authorizedRequest('/platform/publish'),env,ctx)).text();assert.match(html,/ORAKT/);assert.match(html,/发布与存证中心/);
});

test("research workspace exposes appearance controls and five separate modules", async () => {
  const app = await worker();
  const response = await app.fetch(authorizedRequest("/platform/research"), env, ctx);
  assert.equal(response.status,200);
  const html = await response.text();
  assert.match(html,/正在核对账号权限与报告目录/);
  const source=await readFile(new URL("../app/PilotDashboard.tsx",import.meta.url),"utf8");
  for (const label of ["浅色阅读", "深色阅读", "单公司报告", "宏观事件横向报告", "建仓观察", "组合实验室", "加密市场", "Alpha 因子", "专属研究"]) assert.ok(source.includes(label));
  assert.match(html,/data-report-theme="light"/);
  assert.doesNotMatch(html,/class="entry-watchlist"/); // not mixed into the default report panel
});

test("brand uses the original thicker line mark and only advertises real login availability", async () => {
  const app = await worker();
  const home = await (await app.fetch(new Request("http://localhost/"),env,ctx)).text();
  assert.doesNotMatch(home,/<img[^>]+orakt-icon.webp/);
  assert.match(home,/stroke-width:2.6/);
  const access = await (await app.fetch(new Request("http://localhost/access"),env,ctx)).text();
  assert.match(access,/Google/); assert.match(access,/注册 ORAKT 账号/); assert.doesNotMatch(access,/Apple|微信网站登录/);
  assert.doesNotMatch(access,/href="\/api\/auth\/(google|apple|wechat)/);
});

function authorizedRequest(path = "/", init = {}) {

  return new Request(`http://localhost${path}`, {
    ...init,
    headers: {
      accept: "application/json, text/html",
      cookie: `__Host-orakt_google=${testGoogleToken}`,
      ...(init.headers ?? {}),
    },
  });
}

test("serves the official homepage publicly without exposing the pilot", async () => {
  const app = await worker();
  const response = await app.fetch(new Request("http://localhost/"), env, ctx);
  assert.equal(response.status, 200);
  const html = await response.text();
  assert.match(html, /ORAKT/);
  assert.match(html, /href="\/access\?plan=explorer&amp;return_to=%2Fplatform"/);
  assert.doesNotMatch(html, /加沙地带|AI 证据核验/);
});

test("rejects anonymous visitors before rendering pilot data", async () => {
  const app = await worker();
  const response = await app.fetch(
    new Request("http://localhost/platform", { headers: { accept: "text/html" } }),
    env,
    ctx,
  );
  assert.equal(response.status, 302);
  assert.equal(response.headers.get("location"), "/access?return_to=%2Fplatform");
  assert.equal(response.headers.get("cache-control"), "private, no-store");
  const html = await response.text();
  assert.doesNotMatch(html, /418,935|加沙地带|AI 证据核验/);
});

test("Basic passwords and incomplete identity headers never authorize the product", async()=>{
 const app=await worker();
 for(const headers of [
  {"oai-authenticated-user-id":"incomplete-user"},
  {authorization:"Basic "+Buffer.from("pilot:"+testPassword).toString("base64")},
 ])assert.equal((await app.fetch(new Request("http://localhost/api/research-report-index",{headers}),env,ctx)).status,401);
 assert.equal((await app.fetch(new Request("http://localhost/api/access/session",{method:"POST"}),env,ctx)).status,405);
});
test("renders exactly the requested public login choices without secrets", async()=>{
 const app=await worker(),r=await app.fetch(new Request("http://localhost/access"),env,ctx),html=await r.text();
 assert.equal(r.status,200);assert.match(html,/Google/);assert.match(html,/Phantom/);assert.match(html,/注册 ORAKT 账号/);
 assert.doesNotMatch(html,/邀请访问码|微信网站登录|Apple/);
 assert.equal(r.headers.get("cross-origin-opener-policy"),"same-origin-allow-popups");
 assert.doesNotMatch(html,new RegExp(testPassword));assert.doesNotMatch(html,new RegExp(testSessionSecret));
});

test("compact login chooser links to isolated provider pages without embedding forms",async()=>{
 const app=await worker();
 const destination="/platform/research?report=325";
 const suffix=`?return_to=${encodeURIComponent(destination)}`;
 const response=await app.fetch(new Request(`http://localhost/access${suffix}`),env,ctx);
 const html=await response.text();
 assert.equal(response.status,200);
 assert.match(html,/data-access-method="choose"/);
 assert.doesNotMatch(html,/<form\b|<input\b|aria-label="Google 账户登录"|aria-label="Solana 钱包登录"/);
 for(const method of ["google","chatgpt","phantom","login","register"])
   assert.ok(html.includes(`href="/access/${method}${suffix}"`),`missing ${method} destination`);
 for(const method of ["google","chatgpt","phantom","login","register","recover"]){
   const page=await app.fetch(new Request(`http://localhost/access/${method}${suffix}`),env,ctx),body=await page.text();
   assert.equal(page.status,200,method);
   assert.equal(page.headers.get("cache-control"),"no-store");
   assert.equal(page.headers.get("cross-origin-opener-policy"),"same-origin-allow-popups");
   assert.ok(body.includes(`data-access-method="${method}"`));
   assert.ok(body.includes(`href="/access${suffix}"`));
   assert.match(body,/返回官网/);
   // Identity must settle before mounting interactive forms, so a delayed
   // session response cannot unmount registration and lose its recovery key.
   assert.match(body,/正在检查登录状态/);
   assert.doesNotMatch(body,/<form\b|id="confirm-password"|id="recovery-key"/);
   if(method!=="google")assert.doesNotMatch(body,/aria-label="Google 账户登录"/);
   if(method!=="phantom")assert.doesNotMatch(body,/aria-label="Solana 钱包登录"/);
   if(method==="chatgpt")assert.ok(body.includes(`href="/signin-with-chatgpt${suffix}" target="_top"`));
 }
 const unknown=await app.fetch(new Request("http://localhost/access/private"),env,ctx);
 assert.equal(unknown.status,401);
 const post=await app.fetch(new Request("http://localhost/access/login",{method:"POST"}),env,ctx);
 assert.equal(post.status,401);
});

test("interactive auth forms wait for the bounded session check",async()=>{
 const source=await readFile(new URL("../app/access/AccessPortal.tsx",import.meta.url),"utf8");
 assert.match(source,/authJsonGet\("\/api\/access\/session",\{signal:controller.signal,timeoutMs:8000\}\)/);
 assert.match(source,/sessionState==="ready"&&method==="google"/);
 assert.match(source,/sessionState==="ready"&&method==="phantom"/);
 assert.match(source,/sessionState==="ready"&&\(method==="login"/);
 assert.match(source,/重新检查登录状态/);
});

test("login destinations retain approved report queries and reject external or auth-loop paths",async()=>{
 for(const value of [undefined, ["/platform"], "https://outside.example", "//outside.example", "/\\outside.example", "/access/google", "/signin-with-chatgpt", "/platform/../access", "/api/research-report", "/platform\n"])
   assert.equal(safeAccessReturnTo(value),"/account");
 assert.equal(safeAccessReturnTo("/platform/research?report=325"),"/platform/research?report=325");
 assert.equal(accessHref("login","//outside.example"),"/access/login?return_to=%2Faccount");
 const app=await worker();
 const r=await app.fetch(new Request("http://localhost/access/chatgpt?return_to=https%3A%2F%2Foutside.example"),env,ctx);
 assert.match(await r.text(),/href="\/signin-with-chatgpt\?return_to=%2Faccount"/);
});
test("account center is protected and its totals come from the published snapshot",async()=>{
 const app=await worker(),anon=await app.fetch(new Request("http://localhost/account",{headers:{accept:"text/html"}}),env,ctx);
 assert.equal(anon.status,302);assert.equal(anon.headers.get("location"),"/access?return_to=%2Faccount");
 const page=await app.fetch(authorizedRequest("/account"),env,ctx);assert.equal(page.status,200);assert.match(await page.text(),/账号中心/);
 const data=await app.fetch(authorizedRequest("/api/account/overview"),env,ctx),body=await data.json();
 assert.equal(body.account.provider,"google");assert.equal(body.scope,"published_read_only");
 assert.equal(body.platform.reports,406);assert.ok(body.platform.companies>200);assert.equal(body.platform.snapshotAt,"2026-09-19T09:55:12.606832+00:00");
 assert.doesNotMatch(JSON.stringify(body),/test-google-subject|password|recovery_hash/);
});
test("missing auth configuration never opens protected data",async()=>{
 const app=await worker();assert.equal((await app.fetch(new Request("http://localhost/api/research-report-index"),{ASSETS:env.ASSETS},ctx)).status,401);
});

test("renders the ORAKT official homepage before entering the product", async () => {
  const app = await worker();
  const response = await app.fetch(authorizedRequest("/"), env, ctx);
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);
  assert.equal(response.headers.get("cache-control"), "public, max-age=300");
  const html = await response.text();
  assert.match(html, /<title>ORAKT · 观因 by INSOLVE TECH \| See what moves the world<\/title>/i);
  assert.match(html, /aria-label="See what moves the world"/);
  assert.match(html, /ORAKT WORLD/);
  assert.match(html, /ORAKT CHAINS/);
  assert.match(html, /ORAKT MARKETS/);
  for(const id of ["lab","company","direction","access","plans"])assert.doesNotMatch(html,new RegExp(`(?:section|article|div) id="${id}"`));
  for(const path of ["/lab","/company","/research","/roadmap","/membership","/plans"])assert.ok(html.includes(`href="${path}"`));
  assert.match(html, /href="\/access\?plan=explorer&amp;return_to=%2Fplatform"/);
  assert.doesNotMatch(html, /微信网站登录|Google · Apple|ChatGPT 账户/);
});

test("renders the read-only product only after explicit platform navigation", async () => {
  const app = await worker();
  const response = await app.fetch(authorizedRequest("/platform"), env, ctx);
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);
  assert.equal(response.headers.get("cache-control"), "private, no-store");
  const html = await response.text();
  assert.match(html, /<title>ORAKT World · Event map<\/title>/i);
  assert.match(html, /事件地图/);
  assert.match(html, /证据报告/);
  assert.match(html, /情报市场/);
  assert.match(html, /组合实验室/);
  assert.doesNotMatch(html, />SEC 审核</);
  assert.match(html, /地图指标/);
  assert.match(html, /战争与冲突点位/);
  assert.match(html, /国家经济指标/);
  assert.match(html, /供应商工厂与制造区域/);
  assert.match(html, /事件回放/);
  assert.match(html, /aria-label="Map tools"/);
  assert.match(html, /研究工具 · 非投资建议/);
});

test("ships a measured conflict and news-discovery snapshot", async () => {
  const manifestUrl = new URL("../snapshot/snapshot-manifest.json", import.meta.url);
  const manifest = JSON.parse(await readFile(manifestUrl, "utf8"));
  assert.ok(manifest.remoteSnapshot.conflictRecords > 25_000);
  assert.ok(manifest.remoteSnapshot.newsIndexRecords > 39_000);
  assert.ok(manifest.remoteSnapshot.contentReadyArticles > 3_500);
  assert.ok(manifest.evidencePolicy.headlineOnlyExcluded > 35_000);
  assert.equal(manifest.evidencePolicy.minimumBodyCharacters, 100);
  assert.ok(manifest.remoteSnapshot.secEvidenceCandidates > 0);
  assert.ok(manifest.remoteSnapshot.localResearchReports >= 10);
  assert.ok(manifest.remoteSnapshot.activeChinaSectorLeaders >= 100);
  assert.ok(manifest.remoteSnapshot.activeChinaSectors >= 10);
  assert.equal(manifest.remoteSnapshot.localResearchAuditVersion, "local_report_audit_v12_a_share_confidence_gate");
  assert.equal(manifest.remoteSnapshot.supplyChainSites, 500);
  assert.equal(manifest.remoteSnapshot.supplyChainExactFacilities, 20);
  assert.equal(manifest.remoteSnapshot.supplyChainTickers, 4);
  assert.equal(manifest.remoteSnapshot.semiconductorComparisonCompanies, 4);
});

test("serves a mobile-sized conflict window by default", async () => {
  const app = await worker();
  const response = await app.fetch(authorizedRequest("/api/conflicts"), env, ctx);
  assert.equal(response.status, 200);
  const text = await response.text();
  const events = JSON.parse(text);
  assert.ok(events.length > 0);
  assert.ok(events.length < 2_000);
  assert.ok(Buffer.byteLength(text) < 1_000_000);
});

test("serves the same-cutoff semiconductor comparison report", async () => {
  const app = await worker();
  const response = await app.fetch(
    authorizedRequest("/api/semiconductor-comparison"),
    env,
    ctx,
  );
  assert.equal(response.status, 200);
  assert.equal(response.headers.get("cache-control"), "private, no-store");
  const payload = await response.json();
  assert.equal(payload.version, "semiconductor_comparison_v1");
  assert.equal(payload.openaiUsed, false);
  assert.match(payload.marketDataCutoff, /^\d{4}-\d{2}-\d{2}$/);
  assert.deepEqual(payload.companies.map((item) => item.ticker), ["MU", "NVDA", "AMD", "MSFT"]);
  assert.ok(payload.companies.every((item) => item.market.historyEnd === payload.marketDataCutoff));
  assert.ok(payload.companies.every((item) => item.market.completeOhlcv));
  assert.ok(payload.companies.every((item) => item.market.barCount > 6_000));
  assert.ok(payload.companies.every((item) => item.fundamentals.periodEnd >= "2025-01-01"));
  const nvidia = payload.companies.find((item) => item.ticker === "NVDA");
  assert.equal(nvidia.fundamentals.periodEnd, "2026-01-25");
  assert.ok(nvidia.fundamentals.netMargin > 0 && nvidia.fundamentals.netMargin < 1);
  const micron = payload.companies.find((item) => item.ticker === "MU");
  assert.equal(micron.evidence.verifiedSupplyChainEdges, 3);
  assert.equal(micron.evidence.unnamedVerifiedSupplyChainEdges, 3);
});

test("exports audited local Ollama reports as individually loadable bodies", async () => {
  const payload = JSON.parse(
    await readFile(
      new URL("../snapshot/research-reports.json", import.meta.url),
      "utf8",
    ),
  );
  assert.ok(payload.total >= 10);
  assert.ok(payload.reports.every((item) => item.origin === "local_ollama"));
  assert.ok(payload.reports.some((item) => item.audit?.version === "local_report_audit_v12_a_share_confidence_gate"));
  assert.ok(payload.reports.every((item) => ["local_report_audit_v2", "local_report_audit_v3", "local_report_audit_v4", "local_report_audit_v5", "local_report_audit_v6", "local_report_audit_v7", "local_report_audit_v8", "local_report_audit_v9", "local_report_audit_v10", "local_report_audit_v11_product_chain_gate", "local_report_audit_v12_a_share_confidence_gate"].includes(item.audit?.version)));
  assert.ok(payload.reports.every((item) => item.audit?.openaiUsed === false));
  const latestReportForTicker = (ticker) => payload.reports
    .filter((item) => item.tradingScenario?.ticker === ticker)
    .sort((left, right) => right.createdAt.localeCompare(left.createdAt))[0];
  const semiconductorReports = ["MU", "NVDA", "AMD", "MSFT"].map(
    latestReportForTicker,
  );
  assert.ok(semiconductorReports.every(Boolean));
  assert.ok(semiconductorReports.every((item) => ["local_report_audit_v10", "local_report_audit_v11_product_chain_gate", "local_report_audit_v12_a_share_confidence_gate"].includes(item.audit?.version)));
  assert.ok(semiconductorReports.every((item) => item.audit?.status === "repaired_and_bounded"));
  assert.ok(semiconductorReports.every((item) => item.audit?.missingReferences === 0));
  assert.ok(semiconductorReports.every((item) => item.audit?.headlineOnlyReferences === 0));
  assert.ok(semiconductorReports.every((item) => item.audit?.futureDatedReferences === 0));
  assert.ok(semiconductorReports.every((item) => item.audit?.foreignSubjects === 0));
  assert.ok(semiconductorReports.every((item) => item.dataReadiness?.status === "full_research_ready"));
  assert.ok(semiconductorReports.every((item) => item.dataReadiness?.score >= 90));
  assert.ok(semiconductorReports.every((item) => item.dataReadiness?.missingRequired.length === 0));
  const productEvidenceReports = ["MU", "MSFT"].map(latestReportForTicker);
  assert.ok(productEvidenceReports.every((item) => ["local_report_audit_v11_product_chain_gate", "local_report_audit_v12_a_share_confidence_gate"].includes(item.audit?.version)));
  assert.ok(productEvidenceReports.every((item) => item.dataReadiness?.components.some((component) => (
    component.key === "product_operating_evidence" && component.score === 100
  ))));
  assert.ok(productEvidenceReports.every((item) => item.evidence.some((evidence) => (
    /已报告实际/.test(evidence.title)
  ))));
  const structuredChinaReport = payload.reports.find((item) => (
    item.marketRegion === "china" && item.disclosureCoverage?.financialMetrics > 0
  ));
  assert.ok(structuredChinaReport);
  assert.equal(structuredChinaReport.audit?.version, "local_report_audit_v12_a_share_confidence_gate");
  assert.ok(structuredChinaReport.confidenceDetail);
  assert.ok(structuredChinaReport.dataReadiness?.version === "a_share_data_readiness_v1");
  assert.ok(structuredChinaReport.dataReadiness?.score > 0);
  assert.ok(structuredChinaReport.dataReadiness?.components.length >= 8);
  assert.ok(structuredChinaReport.disclosureCoverage.shareholderExcerpts > 0);
  assert.ok(structuredChinaReport.disclosureCoverage.supplyChainExcerpts > 0);
  assert.ok(structuredChinaReport.disclosureCoverage.periodStart <= "2024-01-01");
  const quarterlyProductReports = ["AAPL", "NVDA", "AMD"].map(
    latestReportForTicker,
  );
  assert.ok(quarterlyProductReports.every(Boolean));
  assert.ok(quarterlyProductReports.every((item) => item.marketRegion === "us"));
  assert.deepEqual(quarterlyProductReports.map((item) => item.ticker), ["AAPL", "NVDA", "AMD"]);
  assert.ok(quarterlyProductReports.every((item) => item.canslim?.criteria.length === 7));
  assert.ok(quarterlyProductReports.every((item) => (
    item.canslim.overallScore >= 0 && item.canslim.overallScore <= 100
  )));
  assert.ok(quarterlyProductReports.every((item) => (
    item.competitorComparison?.rows.length >= 4
  )));
  assert.ok(quarterlyProductReports.every((item) => (
    item.competitorComparison?.productDisclosures.some((disclosure) => (
      disclosure.filingForm === "10-Q"
    ))
  )));
  assert.ok(semiconductorReports.every((item) => item.tradingScenario?.barDataStatus === "complete_ohlcv"));
  assert.ok(semiconductorReports.every((item) => item.tradingScenario?.chart.length === 90));
  assert.ok(semiconductorReports.every((item) => item.tradingScenario?.chart.every((bar) => (
    bar.open != null && bar.high != null && bar.low != null && bar.volume != null
  ))));
  assert.ok(semiconductorReports.every((item) => item.tradingScenario?.atr14 > 0));
  assert.ok(semiconductorReports.every((item) => item.tradingScenario?.volumeRatio20 > 0));
  assert.ok(semiconductorReports.every((item) => (
    item.tradingScenario?.horizonModels?.version === "entry_horizon_walk_forward_v1"
  )));
  assert.ok(semiconductorReports.every((item) => (
    item.tradingScenario?.horizonModels?.models.length === 4
  )));
  assert.ok(semiconductorReports.every((item) => (
    item.tradingScenario?.horizonModels?.models.every((model) => (
      model.validation.leakageGuard.includes("close t+1")
      && model.parameters.transactionCostBps === 10
    ))
  )));
  assert.ok(semiconductorReports.every((item) => (
    item.dataCutoff.includes(`market ${item.tradingScenario.observedOn}`)
  )));
});

test("serves historical-report entry calibration without claiming automatic retraining", async () => {
  const app = await worker();
  const response = await app.fetch(
    authorizedRequest("/api/entry-backtest-status"),
    env,
    ctx,
  );
  assert.equal(response.status, 200);
  assert.equal(response.headers.get("cache-control"), "private, no-store");
  const payload = await response.json();
  assert.equal(payload.modelVersion, "entry_horizon_walk_forward_v1");
  assert.ok(payload.historicalReportsEvaluated >= 200);
  assert.deepEqual(
    payload.horizons.map((item) => item.key),
    ["ultra_short", "swing", "medium", "long_value"],
  );
  assert.ok(payload.horizons.every((item) => item.minimumSignalsForUpgradeReview === 30));
  assert.equal(payload.productionModelChanged, false);
  assert.ok(["snapshot_replay_fallback", "append_only_database_ledger"].includes(payload.ledgerMode));
  assert.equal(
    payload.outcomesSettled + payload.pendingForecasts,
    payload.forecastsTotal,
  );
  assert.ok(payload.horizons.every((item) => item.candidateStatus === "collecting"));
  assert.equal(payload.evaluationVersion, "benchmark_relative_path_v2_dual");
  assert.match(payload.benchmarkPolicy.us, /SPY/);
  assert.match(payload.benchmarkPolicy.china, /MCHI/);
  assert.match(payload.benchmarkPolicy.usSector, /Sector SPDR/);
  assert.match(payload.benchmarkPolicy.chinaSector, /equal-weight sector/);
  assert.equal(payload.dailyCompanyUniverse, 239);
  assert.ok(payload.dailyCompanySnapshotsCreated >= 0);
  assert.equal(payload.dailyCompanySnapshotsCovered, 239);
  assert.equal(payload.dailyCompanySnapshotGpuUsed, false);
  assert.equal(payload.horizons[0].rawMaturedSignals, 6);
  assert.equal(payload.horizons[0].maturedSignals, 1);
  assert.equal(payload.horizons[0].benchmarkCoverageRate, 1);
  assert.ok(payload.horizons[0].meanExcessReturn > 0);
  assert.equal(payload.horizons[0].sectorBenchmarkCoverageRate, 1);
  assert.ok(payload.horizons[0].meanSectorExcessReturn > 0);
  assert.ok(payload.horizons[0].hitRateConfidenceInterval95[0] < 0.25);
  assert.equal(payload.candidateReview[0].rawMaturedBaseSignals, 6);
  assert.equal(payload.candidateReview[0].maturedBaseSignals, 1);
  assert.equal(payload.horizons[0].marketRegimes.riskOn, 6);
  assert.match(payload.parameterUpgradePolicy, /human review/);
});

test("serves a compact mobile report index and one full report on demand", async () => {
  const app = await worker();
  const indexResponse = await app.fetch(
    authorizedRequest("/api/research-report-index"),
    env,
    ctx,
  );
  assert.equal(indexResponse.status, 200);
  const indexText = await indexResponse.text();
  assert.ok(Buffer.byteLength(indexText) < 1_500_000);
  const index = JSON.parse(indexText);
  assert.equal(index.reports.length, index.total);
  assert.ok(index.reports.length >= 200);
  assert.equal(index.detailEndpoint, "/api/research-report?id=");
  assert.ok(index.reports.every((item) => typeof item.hasCompetitorComparison === "boolean"));
  assert.ok(index.reports.every((item) => !item.tradingScenario || item.tradingScenario.chart.length === 0));

  const legacyResponse = await app.fetch(
    authorizedRequest("/api/research-reports"),
    env,
    ctx,
  );
  const legacyText = await legacyResponse.text();
  assert.ok(Buffer.byteLength(legacyText) < 1_500_000);
  assert.deepEqual(JSON.parse(legacyText), index);

  const reportId = index.reports.find((item) => item.hasCompetitorComparison)?.id ?? index.reports[0].id;
  const detailResponse = await app.fetch(
    authorizedRequest(`/api/research-report?id=${encodeURIComponent(reportId)}`),
    env,
    ctx,
  );
  assert.equal(detailResponse.status, 200);
  assert.equal(detailResponse.headers.get("cache-control"), "private, no-store");
  const detail = await detailResponse.json();
  assert.equal(detail.report.id, reportId);
  assert.ok(detail.report.chain.length > 0);
  assert.ok(detail.report.evidence.length > 0);
});

test("serves the active A-share and U.S. sector-leader catalog", async () => {
  const app = await worker();
  const response = await app.fetch(
    authorizedRequest("/api/equity-report-catalog"),
    env,
    ctx,
  );
  assert.equal(response.status, 200);
  assert.equal(response.headers.get("cache-control"), "private, no-store");
  const payload = await response.json();
  assert.equal(payload.universe, "CSI 800 proxy leaders + reviewed U.S. cross-sector leaders");
  assert.ok(payload.companies.length >= 238);
  assert.ok(new Set(payload.companies.map((item) => item.sector)).size >= 10);
  assert.deepEqual(new Set(payload.companies.map((item) => item.marketRegion)), new Set(["china", "us"]));
  const china = payload.companies.filter((item) => item.marketRegion === "china");
  const us = payload.companies.filter((item) => item.marketRegion === "us");
  assert.equal(china.length, 131);
  assert.equal(us.length, 108);
  const lululemon = us.find((item) => item.ticker === "LULU");
  assert.ok(lululemon);
  assert.equal(lululemon.companyName, "lululemon athletica inc.");
  assert.ok(lululemon.reportIds.length > 0);
  assert.ok(china.every((item) => /^\d{6}$/.test(item.ticker)));
  assert.ok(china.every((item) => item.observationCount > 0));
  assert.ok(payload.generation.targetCount >= 229);
  assert.equal(payload.generation.dailyPolicy.rotationBudget, 12);
  assert.equal(payload.generation.dailyPolicy.eventBudget, 4);
  assert.equal(payload.generation.dailyPolicy.gpuConcurrency, 1);
  assert.equal(payload.generation.dailyPolicy.snapshotGpuUsed, false);
  assert.ok(payload.generation.triggeredTargets >= 0);
  assert.ok(payload.generation.batches.length >= 11);
  assert.ok(payload.generation.batches.some((item) => (
    /结构化证据增强重建/.test(item.name) && item.targetCount === 38
  )));
});

test("serves the protected supply-chain facility snapshot", async () => {
  const app = await worker();
  const response = await app.fetch(authorizedRequest("/api/supply-chain-sites"), env, ctx);
  assert.equal(response.status, 200);
  assert.equal(response.headers.get("cache-control"), "private, no-store");
  const payload = await response.json();
  assert.equal(payload.sites.length, 500);
  assert.deepEqual(payload.summaries.map((item) => item.ticker), ["AAPL", "INTC", "MU", "TSM"]);
  assert.equal(payload.summaries.find((item) => item.ticker === "AAPL").siteCount, 724);
  assert.equal(payload.summaries.find((item) => item.ticker === "AAPL").supplierLocationCount, 724);
  assert.equal(payload.summaries.find((item) => item.ticker === "MU").companyFacilityCount, 8);
  assert.equal(payload.summaries.find((item) => item.ticker === "INTC").companyFacilityCount, 4);
  assert.equal(payload.summaries.find((item) => item.ticker === "TSM").companyFacilityCount, 8);
  assert.ok(payload.sites.some((item) => item.coordinatePrecision === "exact_facility"));
  assert.ok(payload.sites.some((item) => item.facilityRole === "company_facility"));
  assert.ok(payload.sites.some((item) => item.contextTickers.includes("MU")));
  assert.ok(payload.sites.every((item) => Array.isArray(item.coordinates)));
});

test("serves the protected SEC evidence review snapshot", async () => {
  const app = await worker();
  const response = await app.fetch(authorizedRequest("/api/sec-evidence"), env, ctx);
  assert.equal(response.status, 200);
  const payload = await response.json();
  assert.ok(payload.metrics.valueCandidates > 0);
  assert.equal(payload.metrics.valueCandidates, payload.candidates.length);
  assert.ok(payload.candidates.some((item) => item.evidenceType === "cash_consideration_per_share"));
  assert.ok(payload.candidates.every((item) => item.sourceUrl.startsWith("https://www.sec.gov/")));
});

test("keeps published evidence reports while making the public UI read-only", async () => {
  const dashboardUrl = new URL("../app/PilotDashboard.tsx", import.meta.url);
  const source = await readFile(dashboardUrl, "utf8");
  assert.match(source, /新闻优先/);
  assert.match(source, /假设优先/);
  assert.match(source, /新闻理解报告/);
  assert.match(source, /本地 AI 报告库/);
  assert.match(source, /api\/research-report-index/);
  assert.match(source, /api\/research-report\?id=/);
  assert.match(source, /尚未载入报告正文/);
  assert.match(source, /stageLocalReport/);
  assert.doesNotMatch(
    source,
    /reports\[0\]\.id[\s\S]{0,400}api\/research-report\?id=/,
  );
  assert.match(source, /本地确定性审计/);
  assert.match(source, /公众只读报告库/);
  assert.match(source, /在线 AI 生成与反馈写入已关闭/);
  assert.doesNotMatch(source, /fetch\("\/api\/research"/);
  assert.doesNotMatch(source, /fetch\("\/api\/feedback"/);
  assert.match(source, /secEvidence/);
  assert.match(source, /SEC 退市与并购证据审核/);
  assert.match(source, /当前价风险收益与技术结构图/);
  assert.match(source, /真实成本不可得/);
  assert.match(source, /90 日K线、成交量、均线与波段结构/);
  assert.match(source, /SemiconductorComparisonPanel/);
  assert.match(source, /api\/semiconductor-comparison/);
  assert.match(source, /七项成长筛选与交易纪律审计/);
  assert.match(source, /同口径竞争比较/);
  assert.match(source, /941%/);
  assert.match(source, /按时间、市场与公司查找报告/);
  assert.match(source, /api\/equity-report-catalog/);
  assert.match(source, /报告起始日期/);
  assert.match(source, /报告结束日期/);
  assert.match(source, /报告时间与版本/);
  assert.match(source, /确定并查看/);
  assert.match(source, /修改市场、公司或时间不会立即清空下面的报告/);
  assert.match(source, /宏观事件横向报告/);
  assert.match(source, /className="cross-report-workspace"/);
  assert.match(source, /comparisonDetail\.competitorComparison/);
  assert.match(source, /尚无已发布报告/);
  assert.match(source, /localReports\.length\s*>\s*0/);
  assert.match(source, /className="report-paper"/);
  assert.match(source, /className="desktop-report-shell"/);
  assert.match(source, /className="desktop-report-browser"/);
  assert.match(source, /className="desktop-report-reader"/);
  assert.match(source, /深度报告工作台/);
  assert.match(source, /正文、证据链、评分拆解与数据限制集中在同一阅读区/);
  assert.doesNotMatch(source, /import \* as maplibregl/);
  assert.match(source, /import\("maplibre-gl"\)/);
  assert.match(source, /正在分阶段加载地图/);
  assert.match(source, /重试地图/);
  assert.match(source, /function VirtualList/);
  assert.match(source, /Virtualized list/);
  assert.match(source, /mapListItems/);
  assert.doesNotMatch(source, /visibleEvents\.slice\(0, 200\)/);
  assert.match(source, /DataLibrary language=/);
  assert.match(source, /readJsonWithSize/);
  assert.match(source, /clientLoadMetrics/);
  assert.match(source, /\['portfolio',Layers3/);
  assert.match(source, /\['intelligence',Newspaper/);
  assert.doesNotMatch(source, /saveCandidateReview/);
  assert.match(source, /SEC 证据审核/);
  assert.match(source, /localizeReport/);
  assert.match(source, /查看可回测参数与防未来函数规则/);
  assert.match(source, /api\/entry-backtest-status/);
});

test("keeps the heavy map engine outside the initial dashboard chunk", async () => {
  const manifest = JSON.parse(
    await readFile(
      new URL("../dist/client/.vite/manifest.json", import.meta.url),
      "utf8",
    ),
  );
  const dashboard = manifest["app/PilotDashboard.tsx"];
  assert.ok(dashboard);
  assert.ok(
    dashboard.dynamicImports.includes(
      "node_modules/maplibre-gl/dist/maplibre-gl.mjs",
    ),
  );
  const dashboardChunk = await readFile(
    new URL(`../dist/client/${dashboard.file}`, import.meta.url),
  );
  assert.ok(dashboardChunk.byteLength < 250_000);

  const platformPageSource = await readFile(
    new URL("../app/platform/page.tsx", import.meta.url),
    "utf8",
  );
  assert.match(platformPageSource, /ClientErrorBoundary/);
  const landingPageSource = await readFile(
    new URL("../app/page.tsx", import.meta.url),
    "utf8",
  );
  assert.doesNotMatch(landingPageSource, /PilotDashboard/);
});

test("rejects public AI generation with a read-only boundary", async () => {
  const app = await worker();
  const response = await app.fetch(
    authorizedRequest("/api/research", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ question: "Will higher yields pressure technology valuations?" }),
    }),
    env,
    ctx,
  );
  assert.equal(response.status, 405);
  assert.match(await response.text(), /public_read_only/);
});

test("rejects reviewer feedback writes in the public release", async () => {
  const app = await worker();
  const response = await app.fetch(
    authorizedRequest("/api/feedback", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        reportId: "report-1",
        question: "Test causal chain?",
        decision: "revise",
        comment: "Add the missing yield evidence.",
        confidence: 61,
      }),
    }),
    env,
    ctx,
  );
  assert.equal(response.status, 405);
  assert.match(await response.text(), /public_read_only/);
});

test("does not expose private reviewer history in the public release", async () => {
  const app = await worker();
  const response = await app.fetch(
    authorizedRequest(
      "/api/feedback-history?reportId=entry-candidate%3Av1%3Av2-ultra",
    ),
    env,
    ctx,
  );
  assert.equal(response.status, 404);
});
test("six standalone marketing pages are public and contain only their own moved section",async()=>{
 const app=await worker();
 const expected={lab:"FACTOR / OOS MATRIX",company:"INSOLVE TECH · COMPANY",research:"CAUSAL AUDIT",roadmap:"PRODUCT DIRECTION",membership:"Phantom · Solana 钱包",plans:"尚未开放在线订阅与自动扣费"};
 for(const [page,marker] of Object.entries(expected)){
  const response=await app.fetch(new Request("http://localhost/"+page),env,ctx);assert.equal(response.status,200,page);
  const html=await response.text();assert.ok(html.includes(marker),page);assert.ok(html.includes('data-marketing-page="'+page+'"'));
  assert.ok(html.includes('href="/"'));assert.doesNotMatch(html,/id="world"|id="chains"|id="markets"/);
  assert.equal((await app.fetch(new Request("http://localhost/"+page,{method:"HEAD"}),env,ctx)).status,200,page+" HEAD");
 }
});
test("navigation links to new pages while product and account data remain protected",async()=>{
 const source=await readFile(new URL("../app/OraktMegaNav.tsx",import.meta.url),"utf8");
 assert.doesNotMatch(source,/href: "#(?:lab|company|direction|plans|access|world|chains|markets)"/);
 assert.match(source,/className={styles.sectionLink} href={sectionHref\[section\]}/);
 const app=await worker();
 for(const path of ["/account","/platform/research","/admin/users"])assert.equal((await app.fetch(new Request("http://localhost"+path,{headers:{accept:"text/html"}}),env,ctx)).status,302);
 assert.equal((await app.fetch(new Request("http://localhost/api/research-report?id=local-566"),env,ctx)).status,401);
});
