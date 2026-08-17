import { NavLink } from "react-router-dom";

import { cn } from "@/lib/utils";
import { useLocale } from "@/context/LocaleContext";

/*
 * Secondary navigation for the accountability module.
 *
 * The same six destinations as the navbar dropdown, repeated in the page because
 * the module is a database a reader moves around inside: someone reading the RTI
 * register wants the reply register next, and sending them back up to a dropdown
 * to get there loses them. Horizontally scrollable on small screens rather than
 * wrapped to three lines -- most of this module's readers arrive on a phone (§22).
 */
export const MODULE_LINKS = [
  { to: "/manifesto", key: "manifesto.nav.election", end: true },
  { to: "/manifesto/promises", key: "manifesto.nav.promises" },
  { to: "/manifesto/rti", key: "manifesto.nav.rti" },
  { to: "/manifesto/replies", key: "manifesto.nav.replies" },
  { to: "/manifesto/documents", key: "manifesto.nav.evidence" },
  { to: "/manifesto/dashboard", key: "manifesto.nav.dashboard" },
];

export default function ModuleNav({ className }) {
  const { t } = useLocale();

  return (
    <nav
      aria-label="Manifesto accountability sections"
      className={cn("border-b border-border bg-background", className)}
      data-testid="manifesto-module-nav"
    >
      <div className="mx-auto w-full max-w-7xl px-6 md:px-12">
        <ul className="-mb-px flex gap-1 overflow-x-auto">
          {MODULE_LINKS.map((link) => (
            <li key={link.to} className="shrink-0">
              <NavLink
                to={link.to}
                end={link.end}
                className={({ isActive }) =>
                  cn(
                    "block whitespace-nowrap border-b-2 px-3 py-3 text-[0.8rem] font-medium transition-colors",
                    isActive
                      ? "border-secondary text-secondary"
                      : "border-transparent text-foreground/60 hover:text-foreground"
                  )
                }
              >
                {t(link.key)}
              </NavLink>
            </li>
          ))}
        </ul>
      </div>
    </nav>
  );
}
