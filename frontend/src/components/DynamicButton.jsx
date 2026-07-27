import { forwardRef, useCallback, useEffect, useRef, useState } from "react";
import { Loader2 } from "lucide-react";
import { gsap, EASE_OUT, prefersReducedMotion } from "@/lib/motion";
import { buttonClasses } from "@/lib/buttonStyles";

/*
 * Button with built-in pending feedback.
 *
 * Two ways to drive the spinner:
 *
 *   1. Controlled -- pass `loading`. The caller owns the state.
 *   2. Automatic  -- return a promise from `onClick`. The button tracks it and
 *      shows the spinner until it settles, so callers don't have to thread a
 *      loading boolean through for one-off actions.
 *
 * While pending the button is disabled and aria-busy, so a double submit cannot
 * fire and screen readers announce the wait.
 *
 * The spinner is driven by GSAP rather than the CSS `animate-spin` class so its
 * rotation shares a ticker with the rest of the page's motion.
 */

const DynamicButton = forwardRef(function DynamicButton(
  {
    children,
    loading,
    onClick,
    className = "",
    variant = "default",
    size = "default",
    disabled = false,
    type = "button",
    loadingLabel,
    ...props
  },
  forwardedRef
) {
  const [autoPending, setAutoPending] = useState(false);
  const spinnerRef = useRef(null);
  const localRef = useRef(null);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  // `loading` wins when provided; otherwise fall back to promise tracking.
  const pending = loading !== undefined ? loading : autoPending;
  const isDisabled = disabled || pending;

  // Merge the forwarded ref with the local one we need for the press animation.
  const setRef = useCallback(
    (node) => {
      localRef.current = node;
      if (typeof forwardedRef === "function") forwardedRef(node);
      else if (forwardedRef) forwardedRef.current = node;
    },
    [forwardedRef]
  );

  // Continuous spin while pending, killed when it stops so the tween never
  // outlives the spinner element.
  useEffect(() => {
    const el = spinnerRef.current;
    if (!el || !pending) return;

    const tween = gsap.to(el, { rotation: 360, duration: 0.8, repeat: -1, ease: "none" });
    return () => tween.kill();
  }, [pending]);

  // Press feedback, skipped entirely under reduced-motion.
  useEffect(() => {
    const el = localRef.current;
    if (!el || isDisabled || prefersReducedMotion()) return;

    const down = () => gsap.to(el, { scale: 0.97, duration: 0.12, ease: EASE_OUT });
    const up = () => gsap.to(el, { scale: 1, duration: 0.22, ease: EASE_OUT });

    el.addEventListener("pointerdown", down);
    el.addEventListener("pointerup", up);
    el.addEventListener("pointerleave", up);

    return () => {
      el.removeEventListener("pointerdown", down);
      el.removeEventListener("pointerup", up);
      el.removeEventListener("pointerleave", up);
      gsap.killTweensOf(el);
      gsap.set(el, { scale: 1 });
    };
  }, [isDisabled]);

  const handleClick = async (event) => {
    if (isDisabled || !onClick) return;

    const result = onClick(event);
    // Only manage state for thenables, and only when uncontrolled.
    if (loading === undefined && result && typeof result.then === "function") {
      setAutoPending(true);
      try {
        await result;
      } finally {
        // The button may have unmounted while the promise was in flight.
        if (mounted.current) setAutoPending(false);
      }
    }
  };

  return (
    <button
      ref={setRef}
      type={type}
      onClick={handleClick}
      disabled={isDisabled}
      aria-busy={pending || undefined}
      className={buttonClasses({ variant, size, className })}
      {...props}
    >
      {pending && <Loader2 ref={spinnerRef} className="h-4 w-4 shrink-0" aria-hidden="true" />}
      {pending && loadingLabel ? loadingLabel : children}
    </button>
  );
});

export default DynamicButton;
