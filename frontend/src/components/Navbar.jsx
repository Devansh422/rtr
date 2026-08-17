import { useEffect, useState, useRef } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import { ChevronDown, Menu, Search, X } from "lucide-react";
import { gsap, EASE_OUT, prefersReducedMotion } from "@/lib/motion";
import ThemeToggle from "@/components/ThemeToggle";
import LanguageSwitcher from "@/components/LanguageSwitcher";
import DynamicButton from "@/components/DynamicButton";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useJoin } from "@/context/JoinContext";

/*
 * The platform has ~20 public sections, which will not fit in one row.
 *
 * The five in LINKS are the ones the landing page's calls to action point at, so
 * they stay top-level; everything else is grouped behind "More" on desktop and
 * listed in full, still grouped, on mobile. Grouping by what a visitor is trying to
 * DO ("Take part", "Learn") rather than by module name is deliberate -- nobody
 * arrives wanting the "corrections module".
 */
const LINKS = [
  // The national petition leads: it is the one action this whole platform is
  // asking for, and the directory of member-started petitions sits under "Take
  // part" with everything else somebody might browse.
  { to: "/petition", label: "Sign the petition" },
  { to: "/constitution", label: "Constitution" },
  { to: "/representatives", label: "Representatives" },
  { to: "/states", label: "States" },
  { to: "/tools", label: "Civic tools" },
];

const MORE = [
  {
    group: "Take part",
    items: [
      { to: "/petitions", label: "All petitions" },
      { to: "/forum", label: "Discuss" },
      { to: "/reports", label: "Citizen report cards" },
      { to: "/volunteer-portal", label: "Volunteer task board" },
      { to: "/events", label: "Events" },
      { to: "/promises", label: "Promise tracker" },
    ],
  },
  {
    group: "Learn",
    items: [
      { to: "/academy", label: "Learning Academy" },
      { to: "/research", label: "Research Centre" },
      { to: "/knowledge", label: "Knowledge Hub" },
      { to: "/ask", label: "Ask the assistant" },
    ],
  },
  {
    group: "The movement",
    items: [
      { to: "/docs", label: "How this site works" },
      { to: "/about", label: "About" },
      { to: "/campaigns", label: "Campaigns" },
      { to: "/blog", label: "Blog" },
      { to: "/resources", label: "Resources" },
      { to: "/contact", label: "Contact" },
    ],
  },
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

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                data-testid="nav-more"
                className="flex items-center gap-1 rounded px-3 py-1.5 text-[0.8rem] font-medium text-foreground/70 transition-colors duration-200 hover:bg-muted"
              >
                More
                <ChevronDown className="h-3.5 w-3.5" aria-hidden="true" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              {MORE.map((section, index) => (
                <div key={section.group}>
                  {index ? <DropdownMenuSeparator /> : null}
                  <DropdownMenuLabel>{section.group}</DropdownMenuLabel>
                  {section.items.map((item) => (
                    <DropdownMenuItem key={item.to} asChild>
                      <Link to={item.to}>{item.label}</Link>
                    </DropdownMenuItem>
                  ))}
                </div>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        <div className="flex items-center gap-2">
          <Link
            to="/search"
            aria-label="Search the site"
            data-testid="nav-search"
            className="flex h-8 w-8 items-center justify-center rounded border border-border text-foreground/70 transition-colors hover:bg-muted"
          >
            <Search className="h-4 w-4" aria-hidden="true" />
          </Link>
          <LanguageSwitcher compact />
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
          {MORE.map((section) => (
            <div key={section.group} className="mt-3">
              <p className="px-4 pb-1 text-label font-bold uppercase text-muted-foreground">
                {section.group}
              </p>
              {section.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    `block rounded px-4 py-2.5 text-body font-medium transition-colors ${
                      isActive ? "bg-muted text-secondary" : "text-foreground/75"
                    }`
                  }
                >
                  {item.label}
                </NavLink>
              ))}
            </div>
          ))}

          <NavLink
            to="/search"
            className="mt-3 block rounded px-4 py-2.5 text-body font-medium text-foreground/75"
          >
            Search
          </NavLink>

          <DynamicButton
            data-testid="mobile-join-button"
            onClick={openJoin}
            variant="default"
            className="mt-3 w-full"
          >
            Join Movement
          </DynamicButton>
        </div>
      </div>
    </header>
  );
}
