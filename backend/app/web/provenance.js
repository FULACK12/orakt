// node_modules/@wallet-standard/app/lib/esm/wallets.js
var __classPrivateFieldGet = function(receiver, state, kind, f) {
  if (kind === "a" && !f) throw new TypeError("Private accessor was defined without a getter");
  if (typeof state === "function" ? receiver !== state || !f : !state.has(receiver)) throw new TypeError("Cannot read private member from an object whose class did not declare it");
  return kind === "m" ? f : kind === "a" ? f.call(receiver) : f ? f.value : state.get(receiver);
};
var __classPrivateFieldSet = function(receiver, state, value, kind, f) {
  if (kind === "m") throw new TypeError("Private method is not writable");
  if (kind === "a" && !f) throw new TypeError("Private accessor was defined without a setter");
  if (typeof state === "function" ? receiver !== state || !f : !state.has(receiver)) throw new TypeError("Cannot write private member to an object whose class did not declare it");
  return kind === "a" ? f.call(receiver, value) : f ? f.value = value : state.set(receiver, value), value;
};
var _AppReadyEvent_detail;
var wallets = void 0;
var registeredWalletsSet = /* @__PURE__ */ new Set();
function addRegisteredWallet(wallet) {
  cachedWalletsArray = void 0;
  registeredWalletsSet.add(wallet);
}
function removeRegisteredWallet(wallet) {
  cachedWalletsArray = void 0;
  registeredWalletsSet.delete(wallet);
}
var listeners = {};
function getWallets() {
  if (wallets)
    return wallets;
  wallets = Object.freeze({ register, get, on });
  if (typeof window === "undefined")
    return wallets;
  const api = Object.freeze({ register });
  try {
    window.addEventListener("wallet-standard:register-wallet", ({ detail: callback }) => callback(api));
  } catch (error) {
    console.error("wallet-standard:register-wallet event listener could not be added\n", error);
  }
  try {
    window.dispatchEvent(new AppReadyEvent(api));
  } catch (error) {
    console.error("wallet-standard:app-ready event could not be dispatched\n", error);
  }
  return wallets;
}
function register(...wallets3) {
  wallets3 = wallets3.filter((wallet) => !registeredWalletsSet.has(wallet));
  if (!wallets3.length)
    return () => {
    };
  wallets3.forEach((wallet) => addRegisteredWallet(wallet));
  listeners["register"]?.forEach((listener) => guard(() => listener(...wallets3)));
  return function unregister() {
    wallets3.forEach((wallet) => removeRegisteredWallet(wallet));
    listeners["unregister"]?.forEach((listener) => guard(() => listener(...wallets3)));
  };
}
var cachedWalletsArray;
function get() {
  if (!cachedWalletsArray) {
    cachedWalletsArray = [...registeredWalletsSet];
  }
  return cachedWalletsArray;
}
function on(event, listener) {
  listeners[event]?.push(listener) || (listeners[event] = [listener]);
  return function off() {
    listeners[event] = listeners[event]?.filter((existingListener) => listener !== existingListener);
  };
}
function guard(callback) {
  try {
    callback();
  } catch (error) {
    console.error(error);
  }
}
var AppReadyEvent = class extends Event {
  get detail() {
    return __classPrivateFieldGet(this, _AppReadyEvent_detail, "f");
  }
  get type() {
    return "wallet-standard:app-ready";
  }
  constructor(api) {
    super("wallet-standard:app-ready", {
      bubbles: false,
      cancelable: false,
      composed: false
    });
    _AppReadyEvent_detail.set(this, void 0);
    __classPrivateFieldSet(this, _AppReadyEvent_detail, api, "f");
  }
  /** @deprecated */
  preventDefault() {
    throw new Error("preventDefault cannot be called");
  }
  /** @deprecated */
  stopImmediatePropagation() {
    throw new Error("stopImmediatePropagation cannot be called");
  }
  /** @deprecated */
  stopPropagation() {
    throw new Error("stopPropagation cannot be called");
  }
};
_AppReadyEvent_detail = /* @__PURE__ */ new WeakMap();

// client.js
var wallets2 = getWallets();
var el = (id) => document.getElementById(id);
var revision;
var signedAttempt;
var busy = false;
var stateNames = { prepared: "\u5DF2\u51C6\u5907 \xB7 \u5C1A\u672A\u4E0A\u94FE", submitted: "\u5DF2\u63D0\u4EA4\u5C1D\u8BD5 \xB7 \u5C1A\u672A\u6838\u9A8C", finalized: "\u5DF2\u5728 Solana devnet \u6700\u7EC8\u786E\u8BA4" };
function reset() {
  revision = void 0;
  signedAttempt = void 0;
  el("details").textContent = "";
}
for (const id of ["kind", "object-id"]) el(id).addEventListener("change", reset);
async function request(path, body) {
  const headers = {};
  if (body !== void 0) {
    headers["Authorization"] = `Bearer ${el("operator-token").value}`;
    headers["Content-Type"] = "application/json";
  }
  const response = await fetch(path, {
    method: body === void 0 ? "GET" : "POST",
    headers,
    body: body === void 0 ? void 0 : JSON.stringify(body),
    cache: "no-store"
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
  return data;
}
var target = () => {
  const id = Number(el("object-id").value);
  if (!Number.isSafeInteger(id) || id < 1) throw new Error("\u8BF7\u8F93\u5165\u6709\u6548\u7684\u62A5\u544A\u6216\u4E8B\u4EF6\u7F16\u53F7");
  return `/provenance/${el("kind").value}/${id}`;
};
function show(data) {
  el("details").textContent = JSON.stringify(data, null, 2);
}
async function load() {
  const data = await request(target());
  revision = data.revisions[0];
  show(data);
  el("state").textContent = data.current_version_anchored ? "\u5F53\u524D\u7248\u672C\u5DF2\u6709 devnet \u5B58\u8BC1" : "\u5F53\u524D\u7248\u672C\u5C1A\u672A\u4E0A\u94FE";
}
function action(id, fn) {
  el(id).addEventListener("click", async () => {
    if (busy) return;
    busy = true;
    document.querySelectorAll("button,input,select").forEach((b) => b.disabled = true);
    try {
      await fn();
    } catch (error) {
      el("state").textContent = error.message;
    } finally {
      busy = false;
      document.querySelectorAll("button,input,select").forEach((b) => b.disabled = false);
    }
  });
}
action("read", load);
action("prepare", async () => {
  revision = await request(`${target()}/prepare`, {});
  signedAttempt = void 0;
  show(revision);
  el("state").textContent = stateNames[revision.status];
});
action("publish", async () => {
  if (!revision) throw new Error("\u5148\u51C6\u5907\u5F53\u524D\u7248\u672C");
  const health = await request("/provenance/health");
  if (!health.writes_enabled) throw new Error("\u7BA1\u7406\u5458\u5C1A\u672A\u542F\u7528 devnet \u5199\u5165\uFF1B\u76EE\u524D\u53EA\u80FD\u67E5\u770B\u548C\u51C6\u5907");
  if (revision.signature && !signedAttempt) {
    revision = await request(`/provenance/revisions/${revision.id}/retry`, {});
    show(revision);
    el("state").textContent = stateNames[revision.status];
    return;
  }
  if (!signedAttempt) {
    const wallet = wallets2.get().find((w) => w.name === "Phantom" && w.features["standard:connect"] && w.features["solana:signTransaction"]);
    if (!wallet) throw new Error("\u8BF7\u5728\u5B89\u88C5 Phantom \u6269\u5C55\u7684\u6D4F\u89C8\u5668\u4E2D\u6253\u5F00\u6B64\u672C\u5730\u9875\u9762");
    const { accounts } = await wallet.features["standard:connect"].connect();
    const account = accounts.find((a) => a.address === health.publisher && a.chains.includes("solana:devnet"));
    if (!account) throw new Error("\u5F53\u524D\u94B1\u5305\u4E0D\u662F\u6307\u5B9A\u53D1\u5E03\u8005\uFF0C\u6216\u4E0D\u652F\u6301 devnet");
    const transaction = await request(`/provenance/revisions/${revision.id}/transaction`, {});
    show(transaction);
    if (!window.confirm("\u4EC5\u5728 Solana devnet \u63D0\u4EA4\u8FD9\u4EFD\u54C8\u5E0C\u5B58\u8BC1\uFF0C\u6D88\u8017\u6D4B\u8BD5 SOL \u624B\u7EED\u8D39\u3002\u7EE7\u7EED\u7531\u94B1\u5305\u7B7E\u540D\uFF1F")) return;
    const [signed] = await wallet.features["solana:signTransaction"].signTransaction({
      account,
      chain: "solana:devnet",
      transaction: Uint8Array.from(atob(transaction.transaction), (c) => c.charCodeAt(0))
    });
    signedAttempt = btoa(String.fromCharCode(...signed.signedTransaction));
  }
  revision = await request(`/provenance/revisions/${revision.id}/submit`, { transaction: signedAttempt });
  show(revision);
  el("state").textContent = "\u5DF2\u63D0\u4EA4\uFF0C\u5C1A\u672A\u786E\u8BA4\u3002\u8BF7\u70B9\u51FB\u6838\u9A8C\uFF1B\u91CD\u590D\u63D0\u4EA4\u53EA\u91CD\u53D1\u540C\u4E00\u7B7E\u540D\u3002";
});
action("verify", async () => {
  if (!revision) throw new Error("\u5148\u67E5\u8BE2\u6216\u51C6\u5907\u8BB0\u5F55");
  const data = await request(`/provenance/revisions/${revision.id}/verify`, {});
  revision = data.record;
  show(data);
  el("state").textContent = data.verification.state === "finalized" ? stateNames.finalized : data.verification.note || "\u672A\u63D0\u4EA4\uFF0C\u4E0D\u80FD\u663E\u793A\u5DF2\u4E0A\u94FE";
});
var query = new URLSearchParams(location.search);
if (["event", "report"].includes(query.get("kind"))) el("kind").value = query.get("kind");
if (/^[1-9]\d*$/.test(query.get("id") || "")) el("object-id").value = query.get("id");
request("/provenance/health").then((data) => {
  el("mode").textContent = data.writes_enabled ? "Devnet \u53D1\u5E03\u5DF2\u542F\u7528 \xB7 \u6307\u5B9A\u94B1\u5305\u7B7E\u540D" : "Devnet \u5199\u5165\u5173\u95ED \xB7 \u53EF\u67E5\u770B\u5B58\u8BC1\u72B6\u6001";
}).catch(() => el("mode").textContent = "\u72B6\u6001\u6682\u4E0D\u53EF\u7528");
