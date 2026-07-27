import { useEffect, useRef } from "react";
import { gsap, ScrollTrigger } from "@/lib/motion";

/*
 * Fixed reading-progress rail. Scrubs scaleX from 0 to 1 across the document.
 * `scrub: 0.3` gives the bar a little easing lag, which reads like the spring the
 * framer-motion version used without needing a physics model.
 */
export default function ScrollProgress() {
  const ref = useRef(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const ctx = gsap.context(() => {
      gsap.fromTo(
        el,
        { scaleX: 0 },
        {
          scaleX: 1,
          ease: "none",
          scrollTrigger: {
            trigger: document.documentElement,
            start: "top top",
            end: "bottom bottom",
            scrub: 0.3,
          },
        }
      );
    }, el);

    // Viewport changes alter document height; re-measure so the rail stays true.
    const refresh = () => ScrollTrigger.refresh();
    window.addEventListener("resize", refresh);

    return () => {
      window.removeEventListener("resize", refresh);
      ctx.revert();
    };
  }, []);

  return (
    <div
      ref={ref}
      data-testid="scroll-progress"
      className="fixed left-0 top-0 z-[60] h-1 w-full origin-left bg-primary"
      style={{ transform: "scaleX(0)" }}
      aria-hidden="true"
    />
  );
}
