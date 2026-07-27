import { useEffect, useState, useRef } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import { Menu, X } from "lucide-react";
import { gsap, EASE_OUT, prefersReducedMotion } from "@/lib/motion";
import ThemeToggle from "@/components/ThemeToggle";
import DynamicButton from "@/components/DynamicButton";
import { useJoin } from "@/context/JoinContext";

const LINKS = [
  { to: "/", label: "Home" },
  { to: "/about", label: "About" },
  { to: "/campaigns", label: "Campaigns" },
  { to: "/blog", label: "Blog" },
  { to: "/volunteer", label: "Volunteer" },
  { to: "/knowledge", label: "Knowledge" },
  { to: "/contact", label: "Contact" },
];

export default function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);
  const { openJoin } = useJoin();
  const location = useLocation();
  const linksRef = useRef(null);
  const mobilePanelRef = useRef(null);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    setOpen(false);
  }, [location.pathname]);

  // Subtle lift on hover. Listeners are removed on unmount, unlike the earlier
  // version which registered them without cleanup.
  useEffect(() => {
    const root = linksRef.current;
    if (!root || prefersReducedMotion()) return;

    const links = Array.from(root.querySelectorAll("a"));
    const cleanups = links.map((link) => {
      const enter = () => gsap.to(link, { y: -2, duration: 0.2, ease: EASE_OUT });
      const leave = () => gsap.to(link, { y: 0, duration: 0.2, ease: EASE_OUT });
      link.addEventListener("mouseenter", enter);
      link.addEventListener("mouseleave", leave);
      return () => {
        link.removeEventListener("mouseenter", enter);
        link.removeEventListener("mouseleave", leave);
        gsap.killTweensOf(link);
      };
    });

    return () => cleanups.forEach((fn) => fn());
  }, []);

  /*
   * Mobile menu open/close. The panel stays mounted so GSAP owns both
   * directions; height auto is animated explicitly because CSS cannot
   * transition to/from `auto`.
   */
  useEffect(() => {
    const panel = mobilePanelRef.current;
    if (!panel) return;

    const reduce = prefersReducedMotion();
    const duration = reduce ? 0 : 0.35;

    if (open) {
      gsap.set(panel, { display: "block" });
      gsap.fromTo(
        panel,
        { height: 0, autoAlpha: 0 },
        { height: "auto", autoAlpha: 1, duration, ease: EASE_OUT }
      );
    } else {
      gsap.to(panel, {
        height: 0,
        autoAlpha: 0,
        duration,
        ease: EASE_OUT,
        onComplete: () => gsap.set(panel, { display: "none" }),
      });
    }
  }, [open]);

  return (
    // Solid at all times -- no transparency or blur. The border is the only thing
    // that changes on scroll, so the bar never sits ambiguously over content.
    <header
      data-testid="navbar"
      className={`fixed inset-x-0 top-0 z-50 bg-background transition-colors duration-200 ${
        scrolled ? "border-b border-border" : "border-b border-transparent"
      }`}
    >
      <nav className="mx-auto flex max-w-7xl items-center justify-between px-6 py-2 md:px-12">
        <Link to="/" data-testid="logo-link" className="flex items-center gap-2">
          <img
            src="/logo.png"
            alt="Right to Recall Movement logo"
            className="h-8 w-8 shrink-0 rounded object-cover"
          />
          <span className="flex flex-col leading-none">
            <span className="font-heading text-lead font-bold">
              Right<span className="text-secondary">ToRecall</span>
            </span>
            <span className="text-[0.55rem] font-semibold uppercase tracking-[0.22em] text-muted-foreground">
              Movement
            </span>
          </span>
        </Link>

        <div ref={linksRef} className="hidden items-center gap-1 lg:flex">
          {LINKS.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              data-testid={`nav-${l.label.toLowerCase()}`}
              className={({ isActive }) =>
                `rounded px-3 py-1.5 text-[0.8rem] font-medium transition-colors duration-200 hover:bg-muted ${
                  isActive ? "text-secondary" : "text-foreground/70"
                }`
              }
            >
              {l.label}
            </NavLink>
          ))}
        </div>

        <div className="flex items-center gap-3">
          <ThemeToggle />
          <DynamicButton
            data-testid="nav-join-button"
            onClick={openJoin}
            variant="default"
            size="sm"
            className="hidden md:inline-flex"
          >
            Join Movement
          </DynamicButton>
          <button
            data-testid="mobile-menu-toggle"
            onClick={() => setOpen(!open)}
            className="flex h-8 w-8 items-center justify-center rounded border border-border lg:hidden"
            aria-label={open ? "Close menu" : "Open menu"}
            aria-expanded={open}
            aria-controls="mobile-menu"
          >
            {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
      </nav>

      <div
        ref={mobilePanelRef}
        id="mobile-menu"
        className="overflow-hidden border-t border-border bg-background lg:hidden"
        style={{ display: "none", height: 0 }}
      >
        <div className="flex flex-col gap-1 px-6 py-4">
          {LINKS.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              data-testid={`mobile-nav-${l.label.toLowerCase()}`}
              className={({ isActive }) =>
                `rounded px-4 py-3 text-lead font-medium transition-colors ${
                  isActive ? "bg-muted text-secondary" : "text-foreground/80"
                }`
              }
            >
              {l.label}
            </NavLink>
          ))}
          <DynamicButton
            data-testid="mobile-join-button"
            onClick={openJoin}
            variant="default"
            className="mt-2 w-full"
          >
            Join Movement
          </DynamicButton>
        </div>
      </div>
    </header>
  );
}
