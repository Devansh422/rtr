import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import { useLenis } from "lenis/react";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import ScrollProgress from "@/components/ScrollProgress";
import BackToTop from "@/components/BackToTop";
import FloatingCTA from "@/components/FloatingCTA";
import { ScrollTrigger } from "@/lib/motion";

export default function Layout({ children }) {
  const { pathname } = useLocation();
  const lenis = useLenis();

  /*
   * Reset scroll on navigation, then re-measure ScrollTriggers.
   *
   * Lenis owns the scroll position, so a bare window.scrollTo(0, 0) does not
   * reliably take effect -- Lenis's own animation loop overwrites it on the next
   * frame. Route through lenis.scrollTo with immediate:true instead, and keep the
   * native call only as a no-Lenis fallback.
   *
   * The refresh afterwards matters because each route has a different document
   * height. Without it, triggers keep the previous page's measurements and
   * reveal animations fire at the wrong scroll offsets (or never fire, leaving
   * elements stuck at opacity 0). It is deferred one frame so React has
   * committed the new page's DOM before anything is measured.
   */
  useEffect(() => {
    if (lenis) lenis.scrollTo(0, { immediate: true });
    else window.scrollTo(0, 0);

    const frame = requestAnimationFrame(() => ScrollTrigger.refresh());
    return () => cancelAnimationFrame(frame);
  }, [pathname, lenis]);

  return (
    <div className="relative min-h-screen bg-background text-foreground">
      <div className="grain-overlay" aria-hidden="true" />
      <ScrollProgress />
      <Navbar />
      <main className="relative z-10">{children}</main>
      <Footer />
      <FloatingCTA />
      <BackToTop />
    </div>
  );
}
