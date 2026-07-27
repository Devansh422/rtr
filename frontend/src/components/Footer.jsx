import { useState, useRef, useEffect } from "react";
import { Link } from "react-router-dom";
import { Send } from "lucide-react";
import Marquee from "react-fast-marquee";
import { toast } from "sonner";
import { gsap, EASE_OUT, prefersReducedMotion } from "@/lib/motion";
import { subscribeNewsletter } from "@/lib/api";
import { SOCIAL_LINKS } from "@/lib/social";
import DynamicButton from "@/components/DynamicButton";

const NAV_GROUPS = [
  {
    heading: "Movement",
    links: [
      { to: "/about", label: "About" },
      { to: "/campaigns", label: "Campaigns" },
      { to: "/volunteer", label: "Volunteer" },
    ],
  },
  {
    heading: "Learn",
    links: [
      { to: "/blog", label: "Blog & News" },
      { to: "/knowledge", label: "Knowledge Hub" },
      { to: "/resources", label: "Resources" },
    ],
  },
  {
    heading: "Connect",
    links: [
      { to: "/contact", label: "Contact" },
      { to: "/join", label: "Join the movement" },
    ],
  },
];

export default function Footer() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const linksRef = useRef(null);

  // Nudge links right on hover. Listeners are cleaned up on unmount, which the
  // earlier version omitted.
  useEffect(() => {
    const root = linksRef.current;
    if (!root || prefersReducedMotion()) return;

    const links = Array.from(root.querySelectorAll("a"));
    const cleanups = links.map((link) => {
      const enter = () => gsap.to(link, { x: 4, duration: 0.25, ease: EASE_OUT });
      const leave = () => gsap.to(link, { x: 0, duration: 0.25, ease: EASE_OUT });
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

  const subscribe = async (e) => {
    e.preventDefault();
    if (!email) return toast.error("Enter your email");
    setLoading(true);
    try {
      const res = await subscribeNewsletter(email);
      toast.success(res.message);
      setEmail("");
    } catch {
      toast.error("Could not subscribe. Try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <footer data-testid="footer" className="relative z-10 border-t border-border bg-background">
      <div className="mx-auto max-w-7xl px-6 pt-20 md:px-12">
        <div className="grid gap-12 lg:grid-cols-12">
          <div className="lg:col-span-5">
            <h3 className="text-title-2 font-bold leading-tight">Get movement updates.</h3>
            <p className="mt-3 max-w-md text-body text-muted-foreground leading-relaxed">
              Facts, campaigns, and civic tools in your inbox. No spam, no noise, no party lines.
            </p>
            <form
              onSubmit={subscribe}
              className="mt-6 flex max-w-md gap-2"
              data-testid="newsletter-form"
            >
              <input
                data-testid="newsletter-email-input"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@email.com"
                className="h-10 flex-1 rounded border border-input bg-card px-4 text-body outline-none focus:ring-1 focus:ring-secondary transition-colors"
              />
              <DynamicButton
                type="submit"
                loading={loading}
                variant="default"
                size="icon"
                aria-label="Subscribe"
                data-testid="newsletter-submit"
              >
                <Send className="h-4 w-4" />
              </DynamicButton>
            </form>
          </div>

          <div
            ref={linksRef}
            className="grid grid-cols-2 gap-8 sm:grid-cols-4 lg:col-span-7 lg:pl-8"
          >
            {NAV_GROUPS.map((group) => (
              <nav key={group.heading} aria-label={group.heading}>
                <p className="mb-3 text-label font-bold uppercase text-muted-foreground">
                  {group.heading}
                </p>
                <ul className="space-y-2">
                  {group.links.map((link) => (
                    <li key={link.to}>
                      <Link
                        to={link.to}
                        className="inline-block text-body text-foreground/70 transition-colors hover:text-foreground"
                      >
                        {link.label}
                      </Link>
                    </li>
                  ))}
                </ul>
              </nav>
            ))}

            <div>
              <p className="mb-3 text-label font-bold uppercase text-muted-foreground">Follow</p>
              {/* Solid brand fills. See SOCIAL_LINKS for why the hexes are inline. */}
              <div className="flex flex-wrap gap-2">
                {SOCIAL_LINKS.map(({ label, href, Icon, brand, onBrand }) => (
                  <a
                    key={label}
                    href={href}
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label={label}
                    data-testid={`social-${label.toLowerCase().split(" ")[0]}`}
                    className="flex h-9 w-9 items-center justify-center rounded transition-opacity hover:opacity-85 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                    style={{ backgroundColor: brand, color: onBrand }}
                  >
                    <Icon className="h-4 w-4" aria-hidden="true" />
                  </a>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/*
         * Oversized wordmark, now scrolling.
         *
         * Marquee rather than static text: at this size a single copy either got
         * clipped or left a large dead gap depending on viewport width. Scrolling
         * it means the phrase always fills the band regardless of width, and the
         * repetition reinforces it.
         *
         * aria-hidden because it repeats the movement's message decoratively; the
         * same words are already in the copy above.
         */}
        {/*
         * overflow-hidden on the wrapper: react-fast-marquee's own container is
         * overflow-x auto/scroll, so at this type size the oversized track exposed
         * a horizontal scrollbar under the band.
         */}
        <div className="marquee-clip mt-20 overflow-hidden" aria-hidden="true">
          <div className="tricolor-bar mb-6 h-1 w-full opacity-80" />
          <Marquee speed={28} gradient={false} autoFill>
            <p className="select-none whitespace-nowrap px-6 font-heading text-[clamp(2.5rem,11vw,9rem)] font-black leading-[0.9] tracking-tightest text-foreground/[0.07]">
              THE FUTURE IS OURS
            </p>
          </Marquee>
        </div>

        <div className="flex flex-col items-start justify-between gap-3 border-t border-border py-8 text-meta text-muted-foreground md:flex-row md:items-center">
          <p>
            © {new Date().getFullYear()} #RightToRecall Movement. A non-partisan civic initiative.
          </p>
          <p>Built for democratic accountability.</p>
        </div>
      </div>
    </footer>
  );
}
