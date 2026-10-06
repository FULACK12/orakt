"use client";
import { useEffect, useRef, useState } from "react";

/** No rendering loop while a scene is off-screen or the tab is hidden. */
export function useSceneActivity() {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);
  const [reduced, setReduced] = useState(true);
  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    let frame = 0;
    const preference = window.matchMedia("(prefers-reduced-motion: reduce)");
    const sync = () => {
      const bounds = node.getBoundingClientRect();
      setVisible(bounds.bottom > 0 && bounds.top < window.innerHeight && !document.hidden);
      setReduced(preference.matches);
    };
    const onScroll = () => { cancelAnimationFrame(frame); frame = requestAnimationFrame(sync); };
    const observer = "IntersectionObserver" in window ? new IntersectionObserver(sync, { threshold: 0.06 }) : null;
    observer?.observe(node);
    sync();
    document.addEventListener("visibilitychange", sync);
    preference.addEventListener("change", sync);
    // A resize or an animated ancestor can move a scene without an IO threshold
    // transition in embedded browsers. Verify bounds on actual viewport moves.
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => { observer?.disconnect(); cancelAnimationFrame(frame); window.removeEventListener("scroll", onScroll); window.removeEventListener("resize", onScroll); document.removeEventListener("visibilitychange", sync); preference.removeEventListener("change", sync); };
  }, []);
  return { ref, visible, reduced, running: visible && !reduced };
}
