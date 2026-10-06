/** A single pausable clock drives both the displayed progress and stage changes. */
export function createSceneClock(duration = 4200) {
  let elapsed = 0;
  let previous = 0;
  let active = false;
  return {
    resume(now) { previous = now; active = true; },
    pause() { active = false; },
    reset() { elapsed = 0; active = false; },
    tick(now) {
      if (!active) return { progress: elapsed / duration, completed: false };
      elapsed += Math.max(0, now - previous);
      previous = now;
      const completed = elapsed >= duration;
      if (completed) elapsed %= duration;
      return { progress: elapsed / duration, completed };
    },
  };
}

/** Do not let a corrupt asset or an HTML error page reach the canvas renderer. */
export function validateLandPoints(value) {
  if (!Array.isArray(value) || value.length === 0 || value.length > 25000 || !value.every(point =>
    Array.isArray(point) && point.length === 2 && point.every(Number.isFinite) &&
    point[0] >= -180 && point[0] <= 180 && point[1] >= -90 && point[1] <= 90
  )) throw new Error("Invalid geographic outline asset");
  return value;
}
