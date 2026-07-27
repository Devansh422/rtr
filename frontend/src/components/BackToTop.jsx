import { ArrowUp } from "lucide-react";
import { useLenis } from "lenis/react";
import { useScrollToggle } from "@/lib/motion";

/*
 * Back-to-top affordance. Stays mounted and is shown/hidden by GSAP autoAlpha
 * (which pairs visibility with opacity, so it is properly removed from the
 * a11y tree and hit-testing while hidden) rather than being conditionally
 * rendered -- that lets GSAP own the transition in both directions.
 */
export default function BackToTop() {
  const ref = useScrollToggle({ threshold: 600, from: { autoAlpha: 0, scale: 0.8 } });
  const lenis = useLenis();

  // Route the scroll through Lenis so it animates with the page's easing
  // instead of fighting it; fall back to native for the no-Lenis case.
  const toTop = () =>
    lenis ? lenis.scrollTo(0, { duration: 1.1 }) : window.scrollTo({ top: 0, behavior: "smooth" });

  return (
    <button
      ref={ref}
      data-testid="back-to-top"
      onClick={toTop}
      aria-label="Back to top"
      className="fixed bottom-6 left-6 z-50 flex h-12 w-12 items-center justify-center rounded border border-border bg-card text-foreground transition-transform duration-200 hover:scale-110"
    >
      <ArrowUp className="h-5 w-5" />
    </button>
  );
}
