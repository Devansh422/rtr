import { useEffect, useRef } from "react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

/*
 * Single place where GSAP plugins get registered. Importing gsap from here
 * rather than from "gsap" directly guarantees ScrollTrigger is available and
 * that registerPlugin runs exactly once.
 */
gsap.registerPlugin(ScrollTrigger);

/** Matches the cubic-bezier the design system used previously: [0.76,0,0.24,1]. */
export const EASE = "power4.inOut";
/** For enter/exit transitions that should decelerate into place. */
export const EASE_OUT = "power3.out";

export const prefersReducedMotion = () =>
  typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

/**
 * Runs a GSAP setup function inside a scoped context and reverts it on unmount.
 *
 * Returns a ref to attach to the scope element. Selector strings inside `setup`
 * are scoped to that element, so `gsap.to(".card", ...)` only touches this
 * component's cards. The context revert is what prevents leaked ScrollTriggers
 * and elements stranded mid-tween across route changes.
 *
 *   const ref = useGsap(() => { gsap.from(".row", { opacity: 0 }); });
 *   return <div ref={ref}>...</div>;
 */
export function useGsap(setup, deps = []) {
  const scope = useRef(null);

  useEffect(() => {
    if (!scope.current) return;
    const ctx = gsap.context(setup, scope);
    return () => ctx.revert();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return scope;
}

/**
 * Animates an element in and out of view based on a scroll-position threshold.
 * Used by the floating CTA and back-to-top affordances.
 *
 * Returns a ref for the element. `from` is the hidden state.
 */
export function useScrollToggle({ threshold = 600, from = { autoAlpha: 0, y: 20 } } = {}) {
  const ref = useRef(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    gsap.set(el, from);
    let shown = false;

    const evaluate = () => {
      const past = window.scrollY > threshold;
      if (past === shown) return;
      shown = past;
      gsap.to(el, {
        autoAlpha: past ? 1 : 0,
        y: past ? 0 : (from.y ?? 0),
        duration: 0.4,
        ease: EASE_OUT,
        overwrite: true,
      });
    };

    evaluate();
    window.addEventListener("scroll", evaluate, { passive: true });
    return () => window.removeEventListener("scroll", evaluate);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [threshold]);

  return ref;
}

export { gsap, ScrollTrigger };
