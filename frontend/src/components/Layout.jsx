import { useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";
import { useLenis } from "lenis/react";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import ScrollProgress from "@/components/ScrollProgress";
import BackToTop from "@/components/BackToTop";
import FloatingCTA from "@/components/FloatingCTA";
import { ScrollTrigger } from "@/lib/motion";
import { trackPageview } from "@/lib/api";

const SESSION_KEY = "rtr_session_id";

/*
 * One id per browser tab session, not per visitor -- it only exists to group a
 * single visit's pages into a "flow" for the admin analytics view, so it lives
 * in sessionStorage (cleared when the tab closes) rather than anywhere more
 * persistent or identifying.
 */
const getSessionId = () => {
  let id = sessionStorage.getItem(SESSION_KEY);
  if (!id) {
    id = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
    sessionStorage.setItem(SESSION_KEY, id);
  }
  return id;
};

export default function Layout({ children }) {
  const { pathname } = useLocation();
  const lenis = useLenis();
  const prevPathRef = useRef(null);

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

  useEffect(() => {
    trackPageview(pathname, prevPathRef.current, getSessionId());
    prevPathRef.current = pathname;
  }, [pathname]);

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
