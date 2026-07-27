import { useJoin } from "@/context/JoinContext";
import { useScrollToggle } from "@/lib/motion";

/*
 * Persistent join prompt that surfaces once the reader is past the hero.
 * Shown/hidden via GSAP autoAlpha so it leaves the a11y tree while hidden.
 */
export default function FloatingCTA() {
  const { openJoin } = useJoin();
  const ref = useScrollToggle({ threshold: 600, from: { autoAlpha: 0, y: 20 } });

  return (
    <button
      ref={ref}
      data-testid="floating-join-cta"
      onClick={openJoin}
      className="fixed bottom-6 right-6 z-50 rounded bg-primary px-6 py-3.5 font-heading text-body font-semibold text-primary-foreground transition-transform duration-200 hover:scale-105 active:scale-95"
    >
      Join Movement
    </button>
  );
}
