// A cancelled/older read must never populate a different account or query.
export function createReadSequence() {
  let current;
  return {
    begin() {
      current?.abort();
      const controller = new AbortController();
      current = controller;
      return {signal: controller.signal, isCurrent: () => current === controller && !controller.signal.aborted, cancel: () => controller.abort()};
    },
    cancel() { current?.abort(); current = undefined; },
  };
}

/** Display-only fail-closed guard; server authorization remains authoritative. */
export function accountAccessView(membership, now = Date.now()) {
  const expiresAt = membership.expiresAt ? Date.parse(membership.expiresAt) : NaN;
  const inactiveGrant = Boolean(membership.expired || (Number.isFinite(expiresAt) && expiresAt <= now));
  const active = membership.status === "active";
  const admin = membership.role === "admin";
  const reports = active && (admin || !inactiveGrant) && Boolean(membership.permissions.reports);
  const research = active && (admin || !inactiveGrant) && Boolean(membership.permissions.research);
  return {
    inactiveGrant,
    plan: admin ? "ADMIN" : active && !inactiveGrant ? membership.effectivePlan.toUpperCase() : "EXPLORER",
    map: active && Boolean(membership.permissions.map), reports, research,
    manageUsers: active && Boolean(membership.permissions.manageUsers),
  };
}

// Recheck at the nearest future session/grant expiry. Long timers are bounded.
export function nextAccountCheck(account, now = Date.now()) {
  const future = [account?.expiresAt, account?.membership?.expiresAt]
    .map(value => value ? Date.parse(value) : NaN).filter(value => Number.isFinite(value) && value > now);
  return Math.min(60000, ...(future.map(value => Math.max(1, value - now + 25))));
}
