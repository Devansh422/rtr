import { ReactLenis, useLenis } from "lenis/react";
import { useEffect } from "react";
import { ScrollTrigger } from "@/lib/motion";

/*
 * Lenis smooth scrolling, wired into GSAP's ScrollTrigger.
 *
 * Lenis owns the scroll position, so ScrollTrigger cannot observe it through
 * native scroll events -- without `lenis.on("scroll", ScrollTrigger.update)`,
 * scroll-triggered animations fire at the wrong offset or not at all.
 *
 * Lenis drives its own requestAnimationFrame loop (autoRaf, on by default) and
 * that is deliberately left alone. Handing the loop to gsap.ticker with
 * autoRaf:false is a common optimisation, but it makes scrolling depend on that
 * wiring attaching successfully -- if the instance isn't ready when the effect
 * runs, nothing ever calls lenis.raf() and the page cannot scroll at all. The
 * shared-ticker micro-optimisation is not worth that failure mode.
 */
function ScrollTriggerBridge() {
  const lenis = useLenis();

  useEffect(() => {
    if (!lenis) return;

    const update = () => ScrollTrigger.update();
    lenis.on("scroll", update);

    // Content height differs per route; measure once this has mounted.
    ScrollTrigger.refresh();

    return () => lenis.off("scroll", update);
  }, [lenis]);

  return null;
}

export default function SmoothScroll({ children }) {
  return (
    <ReactLenis root options={{ lerp: 0.09, duration: 1.2, smoothWheel: true }}>
      {/*
        The bridge is a child rather than an effect in this component so it can
        read the instance via useLenis() from inside the provider, instead of
        depending on ref-population timing.
      */}
      <ScrollTriggerBridge />
      {children}
    </ReactLenis>
  );
}
