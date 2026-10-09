const returnPaths = new Set(["/platform/assets","/account/billing","/platform/markets","/platform/alpha","/platform/personal","/platform/intelligence","/account", "/platform", "/platform/chains", "/platform/research", "/platform/data", "/platform/filings", "/platform/publish", "/platform/news", "/platform/portfolio", "/admin/users"]);
export const accessMethods = ["chatgpt", "google", "phantom", "login", "register", "recover"];
export const accessPagePaths = new Set(["/access", ...accessMethods.map(method => `/access/${method}`)]);

export function safeAccessReturnTo(value) {
  if (typeof value !== "string" || !value.startsWith("/") || value.startsWith("//") || /[\\\u0000-\u0020]/.test(value)) return "/account";
  try {
    const url = new URL(value, "https://orakt.invalid");
    return url.origin === "https://orakt.invalid" && returnPaths.has(url.pathname) ? url.pathname + url.search : "/account";
  } catch { return "/account"; }
}

export function accessHref(method, returnTo) {
  const path = accessMethods.includes(method) ? `/access/${method}` : "/access";
  return `${path}?return_to=${encodeURIComponent(safeAccessReturnTo(returnTo))}`;
}
