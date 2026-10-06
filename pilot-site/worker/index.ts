/** Cloudflare Worker entry point for the vinext-starter template. */
import { handleImageOptimization, DEFAULT_DEVICE_SIZES, DEFAULT_IMAGE_SIZES } from "vinext/server/image-optimization";
import handler from "vinext/server/app-router-entry";
import { walletAuthResponse, readWalletSession, clearWalletCookies, revokeWalletSession } from "./wallet-auth.mjs";
import {googleAuthResponse, readGoogleSession, revokeGoogleSession, clearGoogleCookies} from "./google-auth.mjs";
import {localAuthResponse, readLocalSession, revokeLocalSession, clearLocalCookies} from "./local-auth.mjs";
import {createHmac} from "node:crypto";
import {gunzipSync} from "node:zlib";
import {Buffer} from "node:buffer";
import privateReports from "../generated/private-reports.mjs";
import {memberFor,publicMember,memberAdminResponse} from "./membership.mjs";
import {publicationResponse} from "./publication.mjs";
import {newsPublicationResponse} from "./news-publication.mjs";
import {intelligenceResponse} from './intelligence-market.mjs';
import researchOperations from "../snapshot/orakt-research-ops.json";
import usHistoryCoverage from "../private-data/us-history-coverage.json";
import secBulkImport from "../private-data/sec-bulk-import.json";
import alphaLab from "../private-data/alpha-lab.json";
import macroEvents from "../private-data/macro-events.json";
import disclosureReviews from "../private-data/disclosure-reviews.json";
import {accessPagePaths} from "../app/access/access-navigation.mjs";
import conflictSnapshot from "../snapshot/conflicts.json";
import entryBacktestStatus from "../snapshot/entry-backtest-status.json";
import equityReportCatalog from "../snapshot/equity-report-catalog.json";
import researchReportIndexSnapshot from "../snapshot/research-report-index.json";
import semiconductorComparisonSnapshot from "../snapshot/semiconductor-comparison.json";
import snapshotManifest from "../snapshot/snapshot-manifest.json";
import secEvidenceSnapshot from "../snapshot/sec-evidence.json";
import supplyChainSitesSnapshot from "../snapshot/supply-chain-sites.json";

const researchReportIds = new Set(
  researchReportIndexSnapshot.reports.map((report) => report.id),
);

interface Env {
  ORAKT_ADMIN_ACCOUNT_ID?: string;
  ORAKT_ADMIN_REFERENCE?: string;
  LOCAL_AUTH_ENABLED?: string;
  LOCAL_AUTH_PEPPER?: string;
  GOOGLE_CLIENT_ID?: string;
  GOOGLE_AUTH_ORIGIN?: string;
  DB?: D1Database;
  BUCKET?: R2Bucket;
  ASSETS: Fetcher;
  PILOT_ACCESS_PASSWORD?: string;
  PILOT_SESSION_SECRET?: string;
  IMAGES: {
    input(stream: ReadableStream): {
      transform(options: Record<string, unknown>): {
        output(options: { format: string; quality: number }): Promise<{ response(): Response }>;
      };
    };
  };
}

interface ExecutionContext {
  waitUntil(promise: Promise<unknown>): void;
  passThroughOnException(): void;
}

// Image security config. SVG sources with .svg extension auto-skip the
// optimization endpoint on the client side (served directly, no proxy).
// To route SVGs through the optimizer (with security headers), set
// dangerouslyAllowSVG: true in next.config.js and uncomment below:
// const imageConfig: ImageConfig = { dangerouslyAllowSVG: true };

const worker = {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);

    if (url.pathname === "/api/app-version" && request.method === "GET") {
      return publicApiResponse(jsonResponse({version: "82"}));
    }
    if (["/api/auth/local/config", "/api/auth/local/challenge", "/api/auth/local/register", "/api/auth/local/login", "/api/auth/local/recover"].includes(url.pathname)) return publicApiResponse(await localAuthResponse(request,env));
    if (["/api/auth/google/config", "/api/auth/google/challenge", "/api/auth/google/verify"].includes(url.pathname)) {
      return publicApiResponse(await googleAuthResponse(request,env));
    }
    if (["/api/wallet/challenge", "/api/wallet/verify"].includes(url.pathname)) {
      return publicApiResponse(await walletAuthResponse(request, env));
    }

    // Only these non-sensitive brand assets are public. Report snapshots and
    // other JSON stay behind the existing read-only access boundary.
    if (["GET", "HEAD"].includes(request.method) && /^\/brand\/(orakt-line\.svg|apple-touch-line\.png|orakt-icon\.webp|favicon-64\.png|apple-touch-icon\.png|world-land-points\.json)$/.test(url.pathname)) {
      return env.ASSETS.fetch(request);
    }

    if (url.pathname === "/api/access/session") {
      return accessSessionResponse(request, env, url);
    }

    if (isPublicWebsiteRequest(request, url)) {
      return publicWebsiteResponse(await handler.fetch(request, env, ctx), url);
    }
    // Provider identities are verified server-side; Sites strips and supplies SIWC headers.
    const identity = await accountIdentity(request,env);
    if (!identity) {
      if (wantsProtectedPage(request,url)) return protectedResponse(new Response(null,{status:302,headers:{Location:`/access?return_to=${encodeURIComponent(sanitizeReturnTo(url.pathname+url.search))}`}}));
      return protectedResponse(jsonResponse({error:"account_required"},401));
    }
    let member;
    try { member=await memberFor(env,identity,!url.pathname.startsWith("/api/account/")&&!url.pathname.startsWith("/api/admin/")); }
    catch { return protectedResponse(jsonResponse({error:"membership_service_unavailable"},503)); }
    if(url.pathname.startsWith("/snapshot/"))return protectedResponse(jsonResponse({error:"not_found"},404));
    if(url.pathname.startsWith("/api/admin/"))return protectedResponse(await memberAdminResponse(request,env,member));
    if(url.pathname.startsWith("/admin/")&&!member.access.permissions.manageUsers)return protectedResponse(new Response("Administrator access required. Return to /account to find your account reference.",{status:403}));
    if (url.pathname === "/api/account/overview" && request.method === "GET") {
      return protectedResponse(jsonResponse({
        account:publicMember(member,identity), checkedAt:new Date().toISOString(), scope:"published_read_only", subscription:"manual_entitlements_only",
        platform:{
          reports:researchReportIndexSnapshot.reports.length,
          companies:equityReportCatalog.companies.length,
          chinaCompanies:snapshotManifest.remoteSnapshot.activeChinaSectorLeaders,
          usCompanies:snapshotManifest.remoteSnapshot.activeUsSectorLeaders,
          newsRecords:snapshotManifest.remoteSnapshot.newsIndexRecords,
          fullTextArticles:snapshotManifest.remoteSnapshot.contentReadyArticles,
          conflictRecords:conflictSnapshot.length,
          snapshotAt:snapshotManifest.generatedAt,
          newsFrom:snapshotManifest.remoteSnapshot.newsStartsAt,
          newsTo:snapshotManifest.remoteSnapshot.newsEndsAt,
          conflictFrom:snapshotManifest.remoteSnapshot.conflictStartsAt,
          conflictTo:snapshotManifest.remoteSnapshot.conflictEndsAt,
        },
      }));
    }

    if(member.access.status!=="active")return protectedResponse(jsonResponse({error:"account_suspended"},403));
    if(url.pathname==='/api/intelligence'||url.pathname==='/api/intelligence/asset')return protectedResponse(await intelligenceResponse(request,env,member));
    if(url.pathname==="/api/news-publication")return protectedResponse(await newsPublicationResponse(request,env,member));
    if(url.pathname==="/api/publication/requests")return protectedResponse(await publicationResponse(request,env,member,researchOperations.provenance));
    if(url.pathname==="/api/publication/status"&&request.method==="GET")return protectedResponse(member.access.permissions.reports?jsonResponse({generatedAt:researchOperations.generatedAt,records:researchOperations.provenance,canSubmit:member.access.permissions.manageUsers,broadcastEnabled:false}):jsonResponse({error:"plan_required"},403));
    if(url.pathname==="/api/alpha-lab"&&request.method==="GET")return protectedResponse(member.access.permissions.research?jsonResponse(alphaLab):jsonResponse({error:"plan_required"},403));
    if(url.pathname==="/api/macro-event-reports"&&request.method==="GET")return protectedResponse(member.access.permissions.research?jsonResponse(macroEvents):jsonResponse({error:"plan_required"},403));
    if(url.pathname==="/api/disclosure-reviews"&&request.method==="GET")return protectedResponse(member.access.permissions.research?jsonResponse(disclosureReviews):jsonResponse({error:"plan_required"},403));
    if(url.pathname==="/api/research-operations"&&request.method==="GET")return protectedResponse(member.access.permissions.research?jsonResponse({...researchOperations,usHistoryCoverage,secBulkImport}):jsonResponse({error:"plan_required"},403));
    const reportRoutes=new Set(["/api/research-report","/api/sec-evidence"]);
    const researchRoutes=new Set(["/api/entry-backtest-status","/api/semiconductor-comparison","/api/supply-chain-sites"]);
    if((reportRoutes.has(url.pathname)&&!member.access.permissions.reports)||(researchRoutes.has(url.pathname)&&!member.access.permissions.research))return protectedResponse(jsonResponse({error:"plan_required",requiredPlan:researchRoutes.has(url.pathname)?"research":"signal"},403));

    if (url.pathname === "/api/economics" && request.method === "GET") {
      return protectedResponse(await economicIndicatorResponse(url));
    }

    if (url.pathname === "/api/conflicts" && request.method === "GET") {
      const requestedDays = url.searchParams.get("days") ?? "90";
      if (requestedDays === "all")
        return protectedResponse(jsonResponse(conflictSnapshot));
      const days = Math.max(1, Math.min(90, Number(requestedDays) || 90));
      const cutoff = new Date(
        `${snapshotManifest.remoteSnapshot.conflictEndsAt}T00:00:00Z`,
      );
      cutoff.setUTCDate(cutoff.getUTCDate() - days);
      const cutoffDate = cutoff.toISOString().slice(0, 10);
      return protectedResponse(
        jsonResponse(conflictSnapshot.filter((item) => item.date >= cutoffDate)),
      );
    }

    if (url.pathname === "/api/snapshot" && request.method === "GET") {
      return protectedResponse(jsonResponse(snapshotManifest));
    }

    if (url.pathname === "/api/sec-evidence" && request.method === "GET") {
      return protectedResponse(jsonResponse(secEvidenceSnapshot));
    }

    if (url.pathname === "/api/research-reports" && request.method === "GET") {
      return protectedResponse(jsonResponse(member.access.permissions.reports?researchReportIndexSnapshot:freeReportCatalog()));
    }

    if (url.pathname === "/api/research-report-index" && request.method === "GET") {
      return protectedResponse(jsonResponse(member.access.permissions.reports?researchReportIndexSnapshot:freeReportCatalog()));
    }

    if (url.pathname === "/api/research-report" && request.method === "GET") {
      const reportId = url.searchParams.get("id") ?? "";
      if (!researchReportIds.has(reportId))
        return protectedResponse(jsonResponse({ error: "report not found" }, 404));
      const packed=(privateReports as Record<string,string>)[reportId];
      if(!packed)return protectedResponse(jsonResponse({error:"report body unavailable"},503));
      const body=JSON.parse(gunzipSync(Buffer.from(packed,"base64")).toString("utf8"));
      if(!member.access.permissions.research&&body.report?.competitorComparison){
        delete body.report.competitorComparison;
        body.restrictedSections=["competitorComparison"];
      }
      return protectedResponse(jsonResponse(body));
    }

    if (url.pathname === "/api/equity-report-catalog" && request.method === "GET") {
      return protectedResponse(jsonResponse(equityReportCatalog));
    }

    if (url.pathname === "/api/entry-backtest-status" && request.method === "GET") {
      return protectedResponse(jsonResponse(entryBacktestStatus));
    }

    if (url.pathname === "/api/semiconductor-comparison" && request.method === "GET") {
      return protectedResponse(jsonResponse(semiconductorComparisonSnapshot));
    }

    if (url.pathname === "/api/supply-chain-sites" && request.method === "GET") {
      return protectedResponse(jsonResponse(supplyChainSitesSnapshot));
    }

    if (
      !["GET", "HEAD", "OPTIONS"].includes(request.method)
    ) {
      return protectedResponse(
        jsonResponse(
          {
            error: "public_read_only",
            detail: "This public release can only read published reports.",
          },
          405,
        ),
      );
    }

    if (url.pathname === "/_vinext/image") {
      const allowedWidths = [...DEFAULT_DEVICE_SIZES, ...DEFAULT_IMAGE_SIZES];
      const response = await handleImageOptimization(request, {
        fetchAsset: (path) => env.ASSETS.fetch(new Request(new URL(path, request.url))),
        transformImage: async (body, { width, format, quality }) => {
          const result = await env.IMAGES.input(body).transform(width > 0 ? { width } : {}).output({ format, quality });
          return result.response();
        },
      }, allowedWidths);
      return protectedResponse(response);
    }

    return protectedResponse(await handler.fetch(request, env, ctx));
  },
};

const ECONOMIC_INDICATORS: Record<string, { unit: string }> = {
  "FP.CPI.TOTL.ZG": { unit: "%" },
  "NY.GDP.MKTP.KD.ZG": { unit: "%" },
  "SL.UEM.TOTL.ZS": { unit: "%" },
  "NY.GDP.MKTP.CD": { unit: "USD" },
  "NV.IND.TOTL.ZS": { unit: "%" },
  "NV.AGR.TOTL.ZS": { unit: "%" },
};

const ECONOMIC_COUNTRIES: Record<string, { iso2: string; coordinates: [number, number] }> = {
  USA: { iso2: "US", coordinates: [-77.0369, 38.9072] },
  CHN: { iso2: "CN", coordinates: [116.4074, 39.9042] },
  JPN: { iso2: "JP", coordinates: [139.6917, 35.6895] },
  DEU: { iso2: "DE", coordinates: [13.405, 52.52] },
  IND: { iso2: "IN", coordinates: [77.209, 28.6139] },
  CAN: { iso2: "CA", coordinates: [-75.6972, 45.4215] },
  GBR: { iso2: "GB", coordinates: [-0.1276, 51.5072] },
  SAU: { iso2: "SA", coordinates: [46.6753, 24.7136] },
  BRA: { iso2: "BR", coordinates: [-47.8825, -15.7942] },
  ZAF: { iso2: "ZA", coordinates: [28.2293, -25.7479] },
  MEX: { iso2: "MX", coordinates: [-99.1332, 19.4326] },
  ISR: { iso2: "IL", coordinates: [35.2137, 31.7683] },
  UKR: { iso2: "UA", coordinates: [30.5234, 50.4501] },
};

async function economicIndicatorResponse(url: URL): Promise<Response> {
  const indicator = url.searchParams.get("indicator") ?? "FP.CPI.TOTL.ZG";
  const config = ECONOMIC_INDICATORS[indicator];
  if (!config) return jsonResponse({ error: "unsupported indicator" }, 422);
  const countries = Object.keys(ECONOMIC_COUNTRIES).join(";");
  const endpoint = `https://api.worldbank.org/v2/country/${countries}/indicator/${encodeURIComponent(indicator)}?format=json&mrv=5&per_page=200`;
  try {
    const upstream = await fetch(endpoint, { headers: { "User-Agent": "NEWS-Map-Pilot/1.0" } });
    if (!upstream.ok) throw new Error(`World Bank ${upstream.status}`);
    const payload = await upstream.json() as [unknown, Array<{ country: { value: string }; countryiso3code: string; date: string; value: number | null }>];
    const rows = Array.isArray(payload?.[1]) ? payload[1] : [];
    const latest = new Map<string, (typeof rows)[number]>();
    for (const row of rows) {
      if (row.value == null || latest.has(row.countryiso3code) || !ECONOMIC_COUNTRIES[row.countryiso3code]) continue;
      latest.set(row.countryiso3code, row);
    }
    const observations = [...latest.values()].map((row) => ({
      country: row.country.value,
      iso2: ECONOMIC_COUNTRIES[row.countryiso3code].iso2,
      date: row.date,
      value: row.value,
      unit: config.unit,
      indicator,
      coordinates: ECONOMIC_COUNTRIES[row.countryiso3code].coordinates,
    }));
    return jsonResponse({ indicator, provider: "World Bank", observations });
  } catch {
    return jsonResponse({ error: "economic provider unavailable", observations: [] }, 502);
  }
}

function jsonResponse(
  payload: unknown,
  status = 200,
  extraHeaders?: HeadersInit,
): Response {
  const headers = new Headers(extraHeaders);
  headers.set("Content-Type", "application/json; charset=utf-8");
  return new Response(JSON.stringify(payload), { status, headers });
}

const allowedReturnPaths = new Set(["/platform","/platform/research","/platform/filings","/platform/data","/platform/publish","/platform/news","/platform/portfolio","/account","/admin/users"]);
async function accountIdentity(request:Request,env:Env) {
  const local=await readLocalSession(request,env);
  if(local)return {subject:local.accountId,provider:"local",displayName:local.username,accountId:local.accountId.slice(0,16),expiresAt:new Date(local.expiresAt).toISOString(),createdAt:new Date(local.createdAt).toISOString()};
  const google=await readGoogleSession(request,env);
  if(google)return {subject:google.subject,provider:"google",displayName:"Google",accountId:createHmac("sha256",env.PILOT_SESSION_SECRET!).update("google:"+google.subject).digest("hex").slice(0,16),expiresAt:new Date(google.expiresAt).toISOString(),createdAt:null};
  const wallet=await readWalletSession(request,env.PILOT_SESSION_SECRET,env.DB);
  if(wallet)return {subject:wallet.address,provider:"phantom",displayName:"Phantom",accountId:wallet.address,walletAddress:wallet.address,expiresAt:new Date(wallet.expiresAt).toISOString(),createdAt:null};
  const subject=request.headers.get("oai-authenticated-user-id"),email=request.headers.get("oai-authenticated-user-email");
  if(subject&&email)return {subject,provider:"chatgpt",displayName:"ChatGPT",accountId:createHmac("sha256",env.PILOT_SESSION_SECRET!).update("chatgpt:"+subject).digest("hex").slice(0,16),expiresAt:null,createdAt:null};
  return null;
}
function freeReportCatalog(){return {access:"catalog_only",reports:researchReportIndexSnapshot.reports.map(({id,ticker,marketRegion,createdAt,companyName,sector}:any)=>({id,ticker,marketRegion,createdAt,companyName,sector}))};}
async function accessSessionResponse(request:Request,env:Env,url:URL):Promise<Response>{
  if(request.method==="GET"){
    const identity=await accountIdentity(request,env);
    try{if(identity)await memberFor(env,identity,false);}catch{return publicApiResponse(jsonResponse({error:"membership_service_unavailable"},503));}
    return publicApiResponse(jsonResponse({authorized:Boolean(identity),expiresAt:identity?.expiresAt??null,scope:identity?"published_read_only":null,provider:identity?.provider??null,walletAddress:identity?.provider==="phantom"?identity.accountId:null}));
  }
  if(request.method!=="DELETE")return publicApiResponse(jsonResponse({error:"method_not_allowed"},405));
  if(request.headers.get("Origin")!==url.origin)return publicApiResponse(jsonResponse({error:"cross_origin_request"},403));
  try{await revokeLocalSession(request,env);await revokeGoogleSession(request,env);await revokeWalletSession(request,env);}
  catch{return publicApiResponse(jsonResponse({error:"logout_unavailable"},503));}
  const headers=new Headers({"Set-Cookie":"orakt_pilot_session=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Lax"});
  clearLocalCookies(headers);clearGoogleCookies(headers);clearWalletCookies(headers);
  return publicApiResponse(Response.json({ok:true,signOutHref:request.headers.get("oai-authenticated-user-id")&&request.headers.get("oai-authenticated-user-email")?"/signout-with-chatgpt?return_to=%2Faccess":"/access"},{headers}));
}
function sanitizeReturnTo(value:string):string{
  try{const parsed=new URL(value,"https://orakt.invalid");return parsed.origin==="https://orakt.invalid"&&allowedReturnPaths.has(parsed.pathname)?parsed.pathname+parsed.search:"/account";}catch{return "/account";}
}

function protectedResponse(response: Response): Response {
  const headers = new Headers(response.headers);
  headers.set("Cache-Control", "private, no-store");
  headers.set("Referrer-Policy", "no-referrer");
  headers.set("X-Content-Type-Options", "nosniff");
  headers.set("X-Frame-Options", "DENY");
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

function isPublicWebsiteRequest(request: Request, url: URL): boolean {
  if (!["GET", "HEAD"].includes(request.method)) return false;
  return (
    ["/","/lab","/company","/research","/roadmap","/membership","/plans"].includes(url.pathname) ||
    accessPagePaths.has(url.pathname) ||
    url.pathname === "/favicon.svg" ||
    url.pathname.startsWith("/_next/static/")
  );
}

function publicWebsiteResponse(response: Response, url: URL): Response {
  const headers = new Headers(response.headers);
  if (accessPagePaths.has(url.pathname)) {
    headers.set("Cross-Origin-Opener-Policy","same-origin-allow-popups");
    headers.set("Cache-Control","no-store");
  } else if (!headers.has("Cache-Control")) headers.set("Cache-Control","public, max-age=300");
  headers.set("Referrer-Policy", "strict-origin-when-cross-origin");
  headers.set("X-Content-Type-Options", "nosniff");
  headers.set("X-Frame-Options", "DENY");
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

function wantsProtectedPage(request: Request, url: URL): boolean {
  return (
    ["GET", "HEAD"].includes(request.method) &&
    request.headers.get("Accept")?.includes("text/html") === true &&
    !url.pathname.startsWith("/api/") &&
    !url.pathname.startsWith("/snapshot/")
  );
}

function publicApiResponse(response: Response): Response {
  const headers = new Headers(response.headers);
  headers.set("Cache-Control", "no-store");
  headers.set("Referrer-Policy", "no-referrer");
  headers.set("X-Content-Type-Options", "nosniff");
  headers.set("X-Frame-Options", "DENY");
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

export default worker;
