// Authentication writes must never be retried automatically. These deadlines
// cover read-only setup requests and *waiting* for a cross-tab lock only.
function deadline(parent, timeoutMs, message = "auth_request_timeout") {
  const controller = new AbortController();
  const abort = () => controller.abort(parent.reason);
  const timer = setTimeout(() => controller.abort(new DOMException(message, "TimeoutError")), timeoutMs);
  if (parent?.aborted) abort();
  else parent?.addEventListener("abort", abort, {once: true});
  return {
    signal: controller.signal,
    dispose() { clearTimeout(timer); parent?.removeEventListener("abort", abort); },
  };
}

/** A read deadline includes the body, and ignores late results after cancellation.
 * @param {string} url
 * @param {{signal?: AbortSignal, timeoutMs?: number, fetchImpl?: typeof fetch}} options
 */
export async function authJsonGet(url, {signal, timeoutMs = 12000, fetchImpl = fetch} = {}) {
  const wait = deadline(signal, timeoutMs);
  let onAbort;
  try {
    wait.signal.throwIfAborted();
    const cancelled = new Promise((_, reject) => {
      onAbort = () => reject(wait.signal.reason);
      wait.signal.addEventListener("abort", onAbort, {once: true});
    });
    return await Promise.race([
      (async () => {
        const response = await fetchImpl(url, {credentials: "same-origin", cache: "no-store", signal: wait.signal});
        if (!response.ok) throw Object.assign(new Error("auth_setup_unavailable"), {status: response.status});
        const data = await response.json();
        wait.signal.throwIfAborted();
        return data;
      })(),
      cancelled,
    ]);
  } finally {
    wait.signal.removeEventListener("abort", onAbort);
    wait.dispose();
  }
}

/** @template T
 * @param {LockManager} locks
 * @param {string} name
 * @param {() => Promise<T>} action
 * @param {{signal?: AbortSignal, timeoutMs?: number}} options
 * @returns {Promise<T>}
 */
export async function withAuthLock(locks, name, action, {signal, timeoutMs = 10000} = {}) {
  const wait = deadline(signal, timeoutMs, "auth_lock_timeout");
  try {
    wait.signal.throwIfAborted();
    return await locks.request(name, {signal: wait.signal}, () => {
      wait.signal.throwIfAborted();
      // Once acquired, the write owns its existing lifecycle. Neither the queue
      // timer nor an unmount releases this lock before the action completes.
      wait.dispose();
      return action();
    });
  } finally { wait.dispose(); }
}
